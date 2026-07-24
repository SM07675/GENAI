// useWebSocket: manages the WebSocket lifecycle and routes inbound messages
// into the Zustand store.
//
// Enterprise additions (Phase 1)
// --------------------------------
// - Heartbeat/pong: sends {"type":"heartbeat"} every 30 s and tracks the pong.
//   If no pong arrives within 10 s the socket is considered dead and
//   reconnect is triggered immediately.
// - Reconnect state: wsStatus = "reconnecting" is published to the store so
//   the UI can show a "Reconnecting…" banner.
// - Backoff cap raised to 30 s (was 15 s) to align with enterprise SLAs.
// - Audio + text are blocked when the socket is not OPEN so bytes are never
//   dropped silently on a stale reference.

import { useEffect, useRef, useCallback } from "react";
import { useAppStore, ORB_STATES } from "../store/appStore";

// #region debug-point B:frontend-websocket
const DEBUG_SERVER_URL = "http://127.0.0.1:7777/event";
const DEBUG_SESSION_ID = "genie-voice-loop";

function reportWsDebug(hypothesisId, location, msg, data = {}) {
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

const HEARTBEAT_INTERVAL_MS = 30_000;   // send ping every 30 s
const HEARTBEAT_TIMEOUT_MS  = 10_000;   // wait 10 s for pong before reconnecting
const MAX_BACKOFF_MS        = 30_000;   // cap reconnect delay at 30 s

/** Resolve the backend WS URL. */
function resolveWsUrl() {
  if (typeof window === "undefined") return "ws://127.0.0.1:8765/ws";
  const { protocol, hostname } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "ws://127.0.0.1:8765/ws";
  }
  const wsProto = protocol === "https:" ? "wss" : "ws";
  return `${wsProto}://${window.location.host}/ws`;
}

export function useWebSocket(pin, queueAudioChunk, stopAudio, notifyTtsDone) {
  const wsRef            = useRef(null);
  const reconnectRef     = useRef(0);      // consecutive reconnect attempts
  const shouldRun        = useRef(false);
  const heartbeatTimer   = useRef(null);   // setInterval id
  const pongTimer        = useRef(null);   // setTimeout id for pong deadline

  const {
    setWs,
    setWsStatus,
    setPublicUrl,
    setOrbState,
    beginAssistantMessage,
    appendAssistantDelta,
    endAssistantMessage,
    addToolEvent,
    clearActiveTools,
    pushUserMessage,
    pushAssistantError,
    setIsTTSPlaying,
    setVoiceState,
    setLiveTranscript,
    forceGenieState,
  } = useAppStore();

  // ── Heartbeat helpers ─────────────────────────────────────────────────────
  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);
    if (pongTimer.current)      clearTimeout(pongTimer.current);
    heartbeatTimer.current = null;
    pongTimer.current      = null;
  }, []);

  const handlePong = useCallback(() => {
    // Server responded — cancel the dead-connection timer.
    if (pongTimer.current) {
      clearTimeout(pongTimer.current);
      pongTimer.current = null;
    }
  }, []);

  // ── Inbound message router ────────────────────────────────────────────────
  const handleMessage = useCallback(
    (raw) => {
      let msg;
      try {
        msg = JSON.parse(raw.data ?? raw);
      } catch {
        return;
      }

      switch (msg.type) {
        case "auth_ok":
          setWsStatus("authed");
          break;
        case "auth_fail":
          setWsStatus("error");
          break;
        case "public_url":
          setPublicUrl(msg.url);
          break;
        case "pong":
          handlePong();
          break;
        case "orb_state":
          setOrbState(msg.state);
          if (msg.state === ORB_STATES.IDLE) {
            clearActiveTools();
          }
          break;

        // ── New pipeline: engine_state (authoritative state from VoicePipeline) ──
        case "engine_state": {
          const engineStateMap = {
            "idle":                "idle",
            "wait_wake":           "sleeping",
            "listening":           "listening",
            "understanding":       "transcribing",
            "thinking":            "thinking",
            "streaming_response":  "speaking",
            "speaking":            "speaking",
            "return_to_listening": "follow_up_listening",
          };
          const mapped = engineStateMap[msg.state] || "idle";
          forceGenieState(mapped);

          // Also update voiceState for mic button compatibility
          const voiceMap = {
            "idle":                "idle",
            "wait_wake":           "wake_listening",
            "listening":           "active_listening",
            "understanding":       "transcribing",
            "thinking":            "processing",
            "streaming_response":  "speaking",
            "speaking":            "speaking",
            "return_to_listening": "follow_up_listening",
          };
          setVoiceState(voiceMap[msg.state] || "idle");

          // SAFETY NET: When pipeline transitions back to listening/idle states,
          // force-clear isTTSPlaying so the mic isn't permanently muted.
          // This prevents the "dead after speaking" bug where TTS flag stays stuck.
          if (["wait_wake", "listening", "return_to_listening", "idle"].includes(msg.state)) {
            setIsTTSPlaying(false);
          }

          // Update live transcript based on state
          switch (msg.state) {
            case "wait_wake":
              setLiveTranscript("");
              break;
            case "listening":
            case "return_to_listening":
              setLiveTranscript("Listening...");
              break;
            case "understanding":
              setLiveTranscript("Processing speech...");
              break;
            case "thinking":
              setLiveTranscript("Thinking...");
              break;
            case "speaking":
            case "streaming_response":
              // Don't clear — keep showing assistant text
              break;
            default:
              break;
          }
          break;
        }

        // ── New pipeline: user transcript from STT ──
        case "user_text": {
          const userText = msg.text || "";
          if (userText) {
            pushUserMessage(userText);
            setLiveTranscript(userText);
          }
          break;
        }

        // ── New pipeline: stop_audio (barge-in) ──
        case "stop_audio": {
          console.log("[WS] stop_audio received — stopping playback");
          if (stopAudio) stopAudio();
          setIsTTSPlaying(false);
          break;
        }

        case "wake_word_detected": {
          // Backend Vosk detected wake word.
          const currentVS = useAppStore.getState().voiceState;
          const currentTTS = useAppStore.getState().isTTSPlaying;
          const allowedStates = ["idle", "wake_listening", "speaking"];
          if (allowedStates.includes(currentVS) || currentTTS) {
            console.log("[WS] wake_word_detected -> wake_detected (Barge-in allowed)");
            if (currentTTS && stopAudio) {
               stopAudio();
            }
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ type: "cancel" }));
            }
          } else {
            console.log(`[WS] wake_word_detected ignored - state=${currentVS}`);
          }
          break;
        }
        case "voice_state": {
          // Backend voice controller state update - authoritative
          const backendState = msg.state;
          console.log(`[WS] Backend voice state: ${backendState}`);
          reportWsDebug("B", "useWebSocket.js:voice_state", "backend voice state received", {
            backendState,
          });
          setVoiceState(backendState);
          
          // L6 fix: route through setGenieState with transition validation
          // instead of raw setState that bypasses the state machine
          const genieStateMap = {
            "idle": "idle",
            "wake_listening": "sleeping",
            "wake_detected": "waking",
            "active_listening": "listening",
            "speech_detected": "listening",
            "recording": "listening",
            "transcribing": "transcribing",
            "processing": "thinking",
            "speaking": "speaking",
            "follow_up_listening": "follow_up_listening",
            "recovering": "idle",
            "interrupted": "interrupted",
            "error": "error",
          };
          const mappedGenieState = genieStateMap[backendState] || "idle";
          // Use force because backend is authoritative — always accept
          useAppStore.getState().forceGenieState(mappedGenieState);
          break;
        }
        case "interrupt": {
          // Backend requests immediate audio stop (barge-in)
          console.log("[WS] interrupt received — stopping audio");
          if (stopAudio) stopAudio();
          setIsTTSPlaying(false);
          break;
        }
        case "transcript":
          pushUserMessage(msg.text);
          break;
        case "assistant_text":
          if (msg.delta) {
            if (!useAppStore.getState().currentAssistantId) {
              beginAssistantMessage();
            }
            appendAssistantDelta(msg.delta);
            // Show what Genie is saying in the live transcript
            setLiveTranscript((useAppStore.getState().messages.find(
              m => m.id === useAppStore.getState().currentAssistantId
            )?.text || "").slice(-200));
          }
          if (msg.final) endAssistantMessage();
          break;
        case "tool_start":
          if (!useAppStore.getState().currentAssistantId) beginAssistantMessage();
          addToolEvent({ type: "tool_start", name: msg.name, args: msg.args });
          break;
        case "tool_end":
          addToolEvent({ type: "tool_end", name: msg.name, result: msg.result });
          break;
        case "error":
          pushAssistantError(`⚠️ ${msg.message}`);
          // Also clear isTTSPlaying on error so voice pipeline doesn't stay stuck
          setIsTTSPlaying(false);
          // Don't setVoiceState directly - let backend send voice_state event
          break;
        case "system_note":
          // Provider-switch / offline-mode notices from the backend.
          // Show as a subtle status hint in the store (not in the chat stream).
          console.info("[WS] system_note:", msg.message);
          useAppStore.setState({ systemNote: msg.message });
          // Auto-clear after 6 seconds
          setTimeout(() => useAppStore.setState({ systemNote: null }), 6000);
          break;
        case "assistant_audio_chunk":
          reportWsDebug("E", "useWebSocket.js:assistant_audio_chunk", "assistant audio chunk received", {
            mime: msg.mime,
            seq: msg.seq,
            audioLen: msg.audio?.length ?? 0,
          });
          if (queueAudioChunk) queueAudioChunk(msg.audio, msg.mime, msg.seq);
          break;
        case "tts_playing":
          // Backend started sending audio — mute mic to prevent echo
          console.log("[WS] TTS playing — muting mic");
          setIsTTSPlaying(true);
          // Don't setVoiceState directly - backend will send voice_state event
          break;
        case "tts_done":
          // Delegate to the audio player which knows whether audio is still draining.
          // notifyTtsDone() sends playback_complete immediately if queue is empty,
          // or sets a flag so the onended handler sends it after the last chunk.
          console.log("[WS] tts_done received — delegating to audio player");
          if (notifyTtsDone) {
            notifyTtsDone();
          } else {
            // Fallback: no audio player — complete immediately
            setIsTTSPlaying(false);
            const ws = useAppStore.getState().ws;
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "playback_complete" }));
            }
          }
          break;
        case "rate_limited":
          pushAssistantError(
            `⏳ ${msg.message} (retry in ${msg.retry_after_seconds}s)`
          );
          break;
        case "confirm_required":
          // Phase 2: confirmation dialog will handle this.
          useAppStore.setState({
            pendingConfirm: { tool: msg.tool, description: msg.description },
          });
          break;
        case "orb_gesture":
          // Store the current delivery cue + visual parameters for the orb
          useAppStore.setState({
            currentGesture: { cue: msg.cue, ...msg.gesture },
          });
          break;
        case "word_timing":
          // Store word-level timing for karaoke-style highlighting (per seq)
          useAppStore.setState((s) => ({
            wordTimings: { ...s.wordTimings, [msg.seq]: msg.words },
          }));
          break;
        case "play_media":
          useAppStore.getState().playBackgroundMedia({
            video_id: msg.video_id,
            playlist_id: msg.playlist_id,
          });
          break;
        case "stop_media":
          useAppStore.getState().stopBackgroundMedia();
          break;
        default:
          break;
      }
    },
    // M7 fix: Zustand store functions are stable references — only
    // include truly external deps to prevent unnecessary reconnections
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [handlePong, queueAudioChunk, stopAudio, notifyTtsDone],
  );

  // ── connect ───────────────────────────────────────────────────────────────
  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= 1) return; // CONNECTING/OPEN

    const attempt = reconnectRef.current;
    if (attempt > 0) {
      setWsStatus("reconnecting");
    } else {
      setWsStatus("connecting");
    }

    const ws = new WebSocket(resolveWsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      setWsStatus("connected");
      reconnectRef.current = 0;
      reportWsDebug("B", "useWebSocket.js:onopen", "websocket opened", {
        attempt,
      });
      ws.send(JSON.stringify({ type: "hello", pin }));

      // Start heartbeat loop.
      stopHeartbeat();
      heartbeatTimer.current = setInterval(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "heartbeat" }));
          // Start pong deadline timer.
          pongTimer.current = setTimeout(() => {
            console.warn("[Genie WS] Pong timeout — reconnecting");
            wsRef.current?.close();
          }, HEARTBEAT_TIMEOUT_MS);
        }
      }, HEARTBEAT_INTERVAL_MS);
    };

    ws.onmessage = handleMessage;

    ws.onclose = () => {
      // M8 fix: ignore onclose for stale sockets (e.g. from Strict Mode unmounts)
      if (wsRef.current !== ws) return;

      stopHeartbeat();
      setWsStatus("disconnected");
      reportWsDebug("B", "useWebSocket.js:onclose", "websocket closed", {
        reconnectAttempt: reconnectRef.current,
      });
      wsRef.current = null;
      if (shouldRun.current && pin) {
        const delay = Math.min(MAX_BACKOFF_MS, 500 * 2 ** reconnectRef.current++);
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      if (wsRef.current !== ws) return;
      setWsStatus("error");
      reportWsDebug("B", "useWebSocket.js:onerror", "websocket error", {});
    };

    setWs(ws);
  }, [pin, handleMessage, setWs, setWsStatus, stopHeartbeat]);

  // ── Lifecycle ─────────────────────────────────────────────────────────────
  useEffect(() => {
    shouldRun.current = true;
    if (pin) connect();
    return () => {
      shouldRun.current = false;
      stopHeartbeat();
      if (wsRef.current) wsRef.current.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pin]);

  // ── Public send helpers ───────────────────────────────────────────────────
  const sendText = useCallback((text) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "text", text }));
  }, []);

  const sendAudioChunk = useCallback((bytes) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(bytes); // binary frame
  }, []);

  const endAudio = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "audio_end" }));
  }, []);

  const cancel = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "cancel" }));
  }, []);

  const sendConfirm = useCallback((confirmed) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "confirm", confirmed }));
  }, []);

  return { sendText, sendAudioChunk, endAudio, cancel, sendConfirm };
}
