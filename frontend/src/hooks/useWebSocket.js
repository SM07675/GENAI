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

export function useWebSocket(pin) {
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
          if (msg.state === ORB_STATES.IDLE) clearActiveTools();
          break;
        case "wake_word_detected":
          useAppStore.setState({ shouldAutoRecord: true });
          break;
        case "transcript":
          pushUserMessage(msg.text);
          break;
        case "assistant_text":
          if (msg.delta) {
            if (!useAppStore.getState().currentAssistantId) {
              beginAssistantMessage();
            }
            appendAssistantDelta(msg.delta);
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
    [
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
      handlePong,
    ],
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
      stopHeartbeat();
      setWsStatus("disconnected");
      wsRef.current = null;
      if (shouldRun.current && pin) {
        const delay = Math.min(MAX_BACKOFF_MS, 500 * 2 ** reconnectRef.current++);
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      setWsStatus("error");
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
