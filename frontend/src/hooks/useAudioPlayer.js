// useAudioPlayer — v14
//
// Plays back base64-encoded audio chunks streamed from the backend.
//
// Architecture:
// - Blob URLs instead of data: URIs (avoids Chrome/Electron CORS issues)
// - isPlayingRef (not state) prevents stale-closure bugs
// - endedGuardRef: single-fire guard that prevents handleEnded() from
//   double-triggering via ontimeupdate while onended hasn't arrived yet
//   (Chromium MP3 blob bug workaround)
// - playbackCompleteRef: prevents sending playback_complete twice in a turn
// - Safety timer: ensures playback_complete fires within 5s of tts_done
//   even if audio events are missed (fixes pipeline stuck bug)

import { useCallback, useEffect, useRef } from "react";
import { useAppStore } from "../store/appStore";
import { resumeAnalyser } from "../services/audioAnalyser";
import { glog } from "../utils/logger";

const MIN_AUDIO_B64_LENGTH = 100; // Minimum base64 length for a valid MP3 frame

export function useAudioPlayer(externalAudioRef) {
  const queueRef            = useRef([]);     // [{blobUrl, seq}]
  const isPlayingRef        = useRef(false);
  const ttsDoneRef          = useRef(false);  // set when backend sends tts_done
  const endedGuardRef       = useRef(false);  // prevents handleEnded double-fire
  const playbackSentRef     = useRef(false);  // prevents double playback_complete
  const safetyTimerRef      = useRef(null);   // safety timer for stuck prevention

  // ── Clear safety timer ─────────────────────────────────────────────────────
  const clearSafetyTimer = useCallback(() => {
    if (safetyTimerRef.current) {
      clearTimeout(safetyTimerRef.current);
      safetyTimerRef.current = null;
    }
  }, []);

  // ── Blob URL creation ──────────────────────────────────────────────────────
  const createBlobUrl = useCallback((base64, mime) => {
    try {
      const binary = atob(base64);
      const bytes  = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      return URL.createObjectURL(new Blob([bytes], { type: mime }));
    } catch (e) {
      console.error("[AudioPlayer] Failed to create blob URL:", e);
      return null;
    }
  }, []);

  // ── Notify from backend that all TTS chunks have been enqueued ─────────────
  const notifyTtsDone = useCallback(() => {
    ttsDoneRef.current = true;

    if (!isPlayingRef.current && queueRef.current.length === 0) {
      // Nothing is queued or playing — complete immediately
      glog("[AudioPlayer] tts_done with empty queue → playback_complete immediately");
      _sendPlaybackComplete();
      return;
    }

    // Audio is still playing — let it drain naturally.
    // Set a generous safety timer in case the onended event never fires (Electron bug).
    // 12s gives even long responses time to finish; the guard prevents double-firing.
    glog("[AudioPlayer] tts_done received — audio still playing, will complete on drain");
    clearSafetyTimer();
    safetyTimerRef.current = setTimeout(() => {
      if (!playbackSentRef.current) {
        console.warn("[AudioPlayer] ⚠️ Safety: audio stuck after tts_done, forcing playback_complete");
        _sendPlaybackComplete();
      }
    }, 15000);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Core effect: attach all audio element handlers ─────────────────────────
  useEffect(() => {
    const el = externalAudioRef?.current;
    if (!el) return;

    const sendPlaybackComplete = () => {
      if (playbackSentRef.current) return; // guard: never send twice per turn
      playbackSentRef.current = true;
      clearSafetyTimer();
      glog("[AudioPlayer] ✅ playback_complete sent");
      
      // Update local state instantly so UI drops 'speaking' state immediately
      const currentGenie = useAppStore.getState().genieState;
      if (currentGenie === "speaking") {
        useAppStore.setState({ isTTSPlaying: false, genieState: "sleeping", voiceState: "idle" });
      } else {
        useAppStore.setState({ isTTSPlaying: false });
      }

      ttsDoneRef.current = false;
      const ws = useAppStore.getState().ws;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "playback_complete" }));
      }
    };

    // Expose as module-level for notifyTtsDone (captured via closure)
    _sendPlaybackComplete = sendPlaybackComplete;

    const playNext = () => {
      if (queueRef.current.length > 0) {
        const next = queueRef.current.shift();
        glog("[AudioPlayer] Playing next chunk", {
          remaining: queueRef.current.length,
          seq: next.seq,
        });
        endedGuardRef.current = false; // reset guard for new track
        el.src = next.blobUrl;
        resumeAnalyser();
        el.play().catch((e) => {
          console.warn("[AudioPlayer] play() rejected:", e);
          URL.revokeObjectURL(next.blobUrl);
          playNext();
        });
      } else {
        // Queue fully drained — audio finished playing
        isPlayingRef.current = false;
        if (ttsDoneRef.current) {
          // All audio played and backend confirmed all chunks sent → complete!
          sendPlaybackComplete();
        } else {
          // Audio drained but tts_done not yet received. Safety timeout: 1.5s
          glog("[AudioPlayer] Queue empty — waiting for tts_done (safety: 8s)");
          clearSafetyTimer();
          safetyTimerRef.current = setTimeout(() => {
            if (!playbackSentRef.current) {
              console.warn("[AudioPlayer] ⚠️ Safety: tts_done never came, forcing playback_complete");
              sendPlaybackComplete();
            }
          }, 8000);
        }
      }
    };

    // handleEnded: protected by endedGuardRef so it only fires once per track
    const handleEnded = () => {
      if (endedGuardRef.current) return; // already handled for this track
      endedGuardRef.current = true;

      const url = el.src;
      el.src = "";
      if (url && url.startsWith("blob:")) {
        URL.revokeObjectURL(url);
      }
      playNext();
    };

    el.onended = handleEnded;

    el.onerror = () => {
      if (!el.src || el.src === "" || el.src === window.location.href) return;
      console.warn("[AudioPlayer] Audio element error — skipping chunk", el.error);
      // Treat errors as ended so we advance the queue
      handleEnded();
    };

    // Chromium/Electron MP3 blob bug: `ended` event sometimes doesn't fire.
    // Fall back to timeupdate: when currentTime is within 150ms of duration or audio ended.
    el.ontimeupdate = () => {
      const { duration, currentTime, ended } = el;
      if (ended) {
        handleEnded();
        return;
      }
      if (
        duration &&
        duration > 0 &&
        duration !== Infinity &&
        currentTime > 0 &&
        currentTime >= duration - 0.12
      ) {
        handleEnded();
      }
    };


    // Failsafe interval: periodically check if the audio is completely stuck
    // (e.g. paused but isPlayingRef is true, and onended never fired).
    const stuckCheckInterval = setInterval(() => {
      if (isPlayingRef.current && !endedGuardRef.current) {
        if (el.ended || (el.paused && el.currentTime > 0 && el.duration)) {
          console.warn("[AudioPlayer] Failsafe: Audio appears ended/paused but handleEnded didn't fire. Forcing next.");
          handleEnded();
        }
      }
      // Another failsafe: if tts_done arrived, queue is empty, but we've been stuck for a while
      if (ttsDoneRef.current && queueRef.current.length === 0 && isPlayingRef.current) {
         if (el.paused || el.ended || el.currentTime === 0) {
            console.warn("[AudioPlayer] Failsafe: tts_done received, queue empty, but audio is not playing. Forcing complete.");
            handleEnded();
         }
      }
    }, 1000);

    return () => {
      clearInterval(stuckCheckInterval);
      el.pause();
      if (el.src && el.src.startsWith("blob:")) URL.revokeObjectURL(el.src);
      el.src = "";
      el.onended      = null;
      el.onerror      = null;
      el.ontimeupdate = null;
      queueRef.current.forEach((item) => URL.revokeObjectURL(item.blobUrl));
      queueRef.current      = [];
      isPlayingRef.current  = false;
      ttsDoneRef.current    = false;
      endedGuardRef.current = false;
      clearSafetyTimer();
    };
  }, [externalAudioRef, clearSafetyTimer]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Enqueue an incoming audio chunk ───────────────────────────────────────
  const queueAudioChunk = useCallback((audio, mime = "audio/mpeg", seq = 0) => {
    const el = externalAudioRef?.current;
    if (!el || !audio || audio.length < MIN_AUDIO_B64_LENGTH) return;

    // New turn starting: reset all flags
    if (!isPlayingRef.current && queueRef.current.length === 0) {
      ttsDoneRef.current    = false;
      playbackSentRef.current = false;
      clearSafetyTimer();
    }

    const blobUrl = createBlobUrl(audio, mime);
    if (!blobUrl) return;

    glog("[AudioPlayer] Chunk queued", {
      seq, mime,
      isPlaying: isPlayingRef.current,
      queueLen: queueRef.current.length,
    });

    if (!isPlayingRef.current) {
      isPlayingRef.current  = true;
      endedGuardRef.current = false;
      el.src = blobUrl;
      resumeAnalyser();
      el.play().catch((e) => {
        console.warn("[AudioPlayer] Initial play() rejected:", e);
        URL.revokeObjectURL(blobUrl);
        isPlayingRef.current = false;
        // Recover: if tts_done already arrived and queue is empty, complete now
        if (ttsDoneRef.current && queueRef.current.length === 0) {
          useAppStore.setState({ isTTSPlaying: false });
          ttsDoneRef.current      = false;
          playbackSentRef.current = true;
          clearSafetyTimer();
          const ws = useAppStore.getState().ws;
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "playback_complete" }));
          }
        } else if (queueRef.current.length > 0) {
          // If there are more chunks, try to play them
          const playNext = () => {
            const next = queueRef.current.shift();
            endedGuardRef.current = false;
            el.src = next.blobUrl;
            el.play().catch(() => {
                URL.revokeObjectURL(next.blobUrl);
                if (queueRef.current.length > 0) playNext();
            });
          };
          playNext();
        }
      });
    } else {
      queueRef.current.push({ blobUrl, seq });
    }
  }, [createBlobUrl, externalAudioRef, clearSafetyTimer]);

  // ── Stop all audio immediately (barge-in / cancel) ─────────────────────────
  const stopAudio = useCallback(() => {
    glog("[AudioPlayer] stopAudio called", {
      queuedChunks: queueRef.current.length,
    });
    clearSafetyTimer();
    queueRef.current.forEach((item) => URL.revokeObjectURL(item.blobUrl));
    queueRef.current      = [];
    isPlayingRef.current  = false;
    ttsDoneRef.current    = false;
    endedGuardRef.current = false;
    playbackSentRef.current = false;
    // Immediately clear the store flag so the mic is never permanently muted
    useAppStore.setState({ isTTSPlaying: false });
    const el = externalAudioRef?.current;
    if (el) {
      if (el.src && el.src.startsWith("blob:")) URL.revokeObjectURL(el.src);
      el.pause();
      el.src = "";
    }
  }, [externalAudioRef, clearSafetyTimer]);

  return { queueAudioChunk, stopAudio, isPlaying: isPlayingRef, notifyTtsDone };
}

// Module-level mutable reference so notifyTtsDone can call sendPlaybackComplete
// without capturing a stale closure. Assigned in the useEffect.
let _sendPlaybackComplete = () => {
  // fallback: just update store if effect hasn't run yet
  useAppStore.setState({ isTTSPlaying: false });
};
