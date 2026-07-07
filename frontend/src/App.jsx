// App: the top-level shell.
//  1. PinGate collects the 4-digit PIN.
//  2. On submit, useWebSocket opens the socket and sends the hello+PIN frame.
//  3. On auth_ok, we render the main Genie UI (orb + chat + voice bar).
//  4. assistant_audio messages are routed to the audio player.
//
// One store (Zustand) holds everything; the WS hook is the only writer of
// connection/transcript state.
import { useEffect, useState, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import PinGate from "./components/PinGate";
import StatusBar from "./components/StatusBar";
import GlowOrb from "./components/GlowOrb";
import ChatPanel from "./components/ChatPanel";
import VoiceBar from "./components/VoiceBar";
import { useWebSocket } from "./hooks/useWebSocket";
import { useAudioPlayer } from "./hooks/useAudioPlayer";
import { useAppStore, ORB_STATES } from "./store/appStore";

export default function App() {
  const [pin, setPin] = useState(null);          // null = still on the PIN gate
  const [authed, setAuthed] = useState(false);

  const wsStatus = useAppStore((s) => s.wsStatus);
  const orbState = useAppStore((s) => s.orbState);
  const amplitude = useAppStore((s) => s.amplitude);   // published by the mic recorder

  const { sendText, sendAudioChunk, endAudio, cancel: wsCancel } = useWebSocket(pin);
  const { queueAudioChunk, stopAudio } = useAudioPlayer();

  const cancel = useCallback(() => {
    wsCancel();
    stopAudio();
  }, [wsCancel, stopAudio]);

  // Watch the store for the auth_ok transition and inbound audio.
  // We subscribe explicitly so audio playback happens outside React render.
  useEffect(() => {
    if (wsStatus === "authed") setAuthed(true);
    if (wsStatus === "error" && pin && !authed) {
      // Wrong PIN: bounce back to the gate with an error flash.
      setAuthed(false);
    }
  }, [wsStatus, pin, authed]);

  // Hook the WebSocket's inbound messages to also play assistant_audio_chunk.
  // We do this by subscribing to the raw ws in the store.
  useEffect(() => {
    const ws = useAppStore.getState().ws;
    if (!ws) return;
    const original = ws.onmessage;
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === "assistant_audio_chunk" && msg.audio) {
          queueAudioChunk(msg.audio);
        } else if (msg.type === "assistant_audio_end") {
          // The backend signals the end of chunks; the audio queue handles transitioning to idle.
        } else if (msg.type === "cancel") {
          stopAudio();
        }
      } catch { /* ignore */ }
      if (original) original(evt);
    };
    return () => { if (ws) ws.onmessage = original; };
  }, [wsStatus, queueAudioChunk, stopAudio]);

  // ---- PIN gate (unauthenticated) --------------------------------------
  if (!authed) {
    return (
      <Shell>
        <PinGate key={pin ? "retry" : "fresh"} onSubmit={setPin} />
      </Shell>
    );
  }

  // ---- Main Genie UI ----------------------------------------------------
  return (
    <Shell>
      <StatusBar />
      <div className="flex flex-col flex-1 min-h-0">
        {/* Orb up top */}
        <div className="flex-shrink-0 pt-6 pb-2">
          <GlowOrb state={orbState} amplitude={amplitude} />
          <p className="text-center text-xs uppercase tracking-[0.3em] text-gray-500 mt-1">
            {labelFor(orbState)}
          </p>
        </div>

        {/* Chat transcript */}
        <ChatPanel />

        {/* Text + voice controls */}
        <VoiceBar
          sendText={sendText}
          sendAudioChunk={sendAudioChunk}
          endAudio={endAudio}
          cancel={cancel}
        />
      </div>
    </Shell>
  );
}

function labelFor(state) {
  return {
    [ORB_STATES.IDLE]: "Ready",
    [ORB_STATES.LISTENING]: "Listening",
    [ORB_STATES.THINKING]: "Thinking",
    [ORB_STATES.SPEAKING]: "Speaking",
  }[state] || "Ready";
}

// Shell: the outer frameless window chrome with a draggable top region.
function Shell({ children }) {
  return (
    <motion.div
      className="h-screen w-screen flex flex-col overflow-hidden bg-transparent"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      <div
        className="flex-1 flex flex-col m-2 md:m-3 glass-strong overflow-hidden"
        style={{ WebkitAppRegion: "drag" } /* allow dragging the frameless window */}
      >
        <div style={{ WebkitAppRegion: "no-drag" }} className="flex-1 flex flex-col min-h-0">
          <AnimatePresence mode="wait">
            <motion.div
              key="content"
              className="flex-1 flex flex-col min-h-0"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
