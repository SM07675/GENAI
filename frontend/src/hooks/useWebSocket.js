// useWebSocket: manages the WebSocket lifecycle and routes inbound messages
// into the Zustand store. Reconnects with backoff.
import { useEffect, useRef, useCallback } from "react";
import { useAppStore, ORB_STATES } from "../store/appStore";

// Resolve the backend WS URL. In Electron/desktop dev the FastAPI server is
// local. On mobile (loaded via ngrok) we connect back to the same origin.
function resolveWsUrl() {
  if (typeof window === "undefined") return "ws://127.0.0.1:8765/ws";
  const { protocol, hostname } = window.location;
  // Desktop dev: served by Vite on 5173, backend is on 8765 -> use localhost.
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "ws://127.0.0.1:8765/ws";
  }
  // Mobile via ngrok: same host, upgrade https->wss.
  const wsProto = protocol === "https:" ? "wss" : "ws";
  return `${wsProto}://${window.location.host}/ws`;
}

export function useWebSocket(pin) {
  const wsRef = useRef(null);
  const reconnectRef = useRef(0);
  const shouldRun = useRef(false);

  const {
    setWs, setWsStatus, setPublicUrl, setOrbState,
    beginAssistantMessage, appendAssistantDelta, endAssistantMessage,
    addToolEvent, clearActiveTools, pushUserMessage,
  } = useAppStore();

  // Central inbound message handler. Pure routing into the store.
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
        case "orb_state":
          setOrbState(msg.state);
          if (msg.state === ORB_STATES.IDLE) clearActiveTools();
          break;
        case "transcript":
          // Echo the user's spoken words into the transcript.
          pushUserMessage(msg.text);
          break;
        case "assistant_text":
          if (msg.delta) {
            // Lazily create an assistant bubble on first delta.
            if (!useAppStore.getState().currentAssistantId) {
              beginAssistantMessage();
            }
            appendAssistantDelta(msg.delta);
          }
          if (msg.final) endAssistantMessage();
          break;
        case "tool_start":
          // Begin an assistant bubble if none exists yet (pure tool turn).
          if (!useAppStore.getState().currentAssistantId) beginAssistantMessage();
          addToolEvent({ type: "tool_start", name: msg.name, args: msg.args });
          break;
        case "tool_end":
          addToolEvent({ type: "tool_end", name: msg.name, result: msg.result });
          break;
        case "error":
          // Surface backend errors as a system assistant note.
          useAppStore.getState().messages.push({
            id: crypto.randomUUID(),
            role: "assistant",
            text: `⚠️ ${msg.message}`,
            ts: Date.now(),
            isError: true,
          });
          break;
        default:
          break;
      }
    },
    [setWsStatus, setPublicUrl, setOrbState, beginAssistantMessage,
     appendAssistantDelta, endAssistantMessage, addToolEvent, clearActiveTools, pushUserMessage]
  );

  // Open the socket and authenticate.
  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= 1) return; // CONNECTING/OPEN
    setWsStatus("connecting");
    const ws = new WebSocket(resolveWsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      setWsStatus("connected");
      reconnectRef.current = 0;
      // Send the PIN handshake immediately.
      ws.send(JSON.stringify({ type: "hello", pin }));
    };

    ws.onmessage = handleMessage;

    ws.onclose = () => {
      setWsStatus("disconnected");
      wsRef.current = null;
      // Exponential backoff reconnect (cap 15s), only if we still have a PIN.
      if (shouldRun.current && pin) {
        const delay = Math.min(15000, 1000 * 2 ** reconnectRef.current++);
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => setWsStatus("error");
    setWs(ws);
  }, [pin, handleMessage, setWs, setWsStatus]);

  useEffect(() => {
    shouldRun.current = true;
    if (pin) connect();
    return () => {
      shouldRun.current = false;
      if (wsRef.current) wsRef.current.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pin]);

  // Public send helpers used by the rest of the UI.
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

  return { sendText, sendAudioChunk, endAudio, cancel };
}
