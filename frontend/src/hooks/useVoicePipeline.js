/**
 * useVoicePipeline — v12: Full-Duplex Barge-In.
 *
 * v12 adds automatic barge-in: the user can interrupt Genie mid-sentence
 * just by talking. The backend's VADGate fires a `barge_in` (or `stop_audio`)
 * WS event which this hook catches to immediately halt audio playback on the
 * frontend without waiting for a server round-trip.
 *
 * Principles unchanged from v11:
 * 1. Backend owns the microphone — no getUserMedia in the frontend.
 * 2. Manual mic button sends cancel / manual_wake over WebSocket.
 *
 * New in v12:
 * 3. `barge_in` / `stop_audio` messages stop active audio immediately.
 * 4. NO activation sound is played for a barge-in — only wake-word detection
 *    plays the chime.
 */
import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "../store/appStore";
import { glog } from "../utils/logger";

// #region debug-point C:frontend-voice-pipeline
const DEBUG_SERVER_URL = "http://127.0.0.1:7777/event";
const DEBUG_SESSION_ID = "genie-voice-loop";

function reportVoiceDebug(hypothesisId, location, msg, data = {}) {
  // Disabled: The debug telemetry server is no longer running.
  // fetch(DEBUG_SERVER_URL, {
  //   method: "POST",
  //   headers: { "Content-Type": "application/json" },
  //   body: JSON.stringify({
  //     sessionId: DEBUG_SESSION_ID,
  //     runId: "pre-fix",
  //     hypothesisId,
  //     location,
  //     msg: `[DEBUG] ${msg}`,
  //     data,
  //     ts: Date.now(),
  //   }),
  // }).catch(() => {});
}
// #endregion

let _audioCtxSingleton = null;
function playActivationSound() {
  try {
    if (!_audioCtxSingleton) _audioCtxSingleton = new (window.AudioContext || window.webkitAudioContext)();
    const ctx = _audioCtxSingleton;
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
    const t = ctx.currentTime;
    [[880, 0, 0.10], [1100, 0.08, 0.10]].forEach(([freq, delay, dur]) => {
      const osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.type = "sine"; osc.frequency.value = freq;
      gain.gain.setValueAtTime(0, t + delay);
      gain.gain.linearRampToValueAtTime(0.18, t + delay + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, t + delay + dur);
      osc.connect(gain); gain.connect(ctx.destination);
      osc.start(t + delay); osc.stop(t + delay + dur + 0.01);
    });
  } catch (_) {}
}

/**
 * v12: Stop all active audio elements and the Web Audio context immediately.
 * Called on barge_in / stop_audio events so the user's voice isn't drowned out.
 * Does NOT play the activation sound.
 */
function stopAllAudio() {
  try {
    // Suspend the shared audio context (stops any oscillator / buffer sources)
    if (_audioCtxSingleton && _audioCtxSingleton.state === "running") {
      _audioCtxSingleton.suspend().catch(() => {});
    }
    // Stop all <audio> elements on the page (e.g. the TTS audio element)
    document.querySelectorAll("audio").forEach((el) => {
      try { el.pause(); el.currentTime = 0; } catch (_) {}
    });
  } catch (_) {}
}

export function useVoicePipeline() {
  const setToggleListening = useAppStore((s) => s.setToggleListening);
  
  const mountedRef  = useRef(true);
  const initDoneRef = useRef(false);

  // ════════════════════════════════════════════════════════════════════════
  // ZUSTAND SUBSCRIPTION — respond to backend state changes
  // (transcript updates are handled by useWebSocket via engine_state)
  // ════════════════════════════════════════════════════════════════════════
  useEffect(() => {
    const unsubscribe = useAppStore.subscribe((state, prevState) => {
      const vs     = state.voiceState;
      const prevVs = prevState.voiceState;
      if (vs === prevVs) return;
      glog(`[GENIE-VOICE] Backend state: ${prevVs} -> ${vs}`);

      if (vs === "wake_detected") {
        // Resume audio context before playing activation sound
        if (_audioCtxSingleton && _audioCtxSingleton.state === "suspended") {
          _audioCtxSingleton.resume().catch(() => {});
        }
        playActivationSound();
      }

      // v12: barge_in — stop audio immediately, NO activation sound
      if (vs === "barge_in") {
        glog("[GENIE-VOICE] ⚡ Barge-in detected — stopping audio immediately");
        stopAllAudio();
      }
    });

    // v12: barge_in / stop_audio is handled by useWebSocket.js (stopAudio call).
    // This subscription catches the voiceState -> "barge_in" edge for any
    // future state machine integrations.

    return () => {
      unsubscribe();
    };
  }, []);

  // ════════════════════════════════════════════════════════════════════════
  // MANUAL MIC BUTTON
  // ════════════════════════════════════════════════════════════════════════
  const toggleListening = useCallback(() => {
    const voiceState = useAppStore.getState().voiceState;
    const genieState = useAppStore.getState().genieState;
    const ws = useAppStore.getState().ws;

    // Active/cancellable states — check both voiceState AND genieState for reliability
    const isCancellable = [
      "active_listening", "recording", "follow_up_listening",
      "speaking", "transcribing", "processing",
    ].includes(voiceState) || [
      "listening", "transcribing", "thinking", "executing",
      "speaking", "follow_up_listening",
    ].includes(genieState);

    if (isCancellable) {
      glog("[GENIE-VOICE] ⚡ Manual cancel — stopping audio and resetting UI state instantly");
      // Fast local stop — kill audio playback and state immediately (<1ms)
      stopAllAudio();
      useAppStore.setState({
        isTTSPlaying: false,
        genieState: "sleeping",
        voiceState: "idle",
        liveTranscript: "",
      });
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "cancel" }));
      }
    } else if (voiceState === "idle" || voiceState === "wake_listening" || genieState === "sleeping" || genieState === "idle") {
      glog("[GENIE-VOICE] Manual mic → start active listening");
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "manual_wake" }));
      }
    }
  }, []);


  // ════════════════════════════════════════════════════════════════════════
  // MOUNT / UNMOUNT
  // ════════════════════════════════════════════════════════════════════════
  useEffect(() => {
    mountedRef.current = true;
    if (initDoneRef.current) return;
    initDoneRef.current = true;

    useAppStore.setState({ genieState: "sleeping" });
    glog("[GENIE-VOICE] ✅ Voice pipeline v12 mounted (backend-driven, full-duplex barge-in)");
    setToggleListening(toggleListening);

    return () => {
      mountedRef.current  = false;
      initDoneRef.current = false;
      setToggleListening(null);
      glog("[GENIE-VOICE] Voice pipeline unmounted");
    };
  }, [setToggleListening, toggleListening]);

  return { toggleListening };
}

