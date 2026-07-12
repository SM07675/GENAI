// App: the top-level shell.
//  1. PinGate collects the 4-digit PIN.
//  2. On submit, useWebSocket opens the socket and sends the hello+PIN frame.
//  3. On auth_ok, we render the main Genie UI (orb + chat + voice bar).
//  4. assistant_audio messages are routed to the audio player.
//
// Enterprise additions (Phase 1):
//  - Reconnecting banner: shown when wsStatus === "reconnecting" so the user
//    knows the backend dropped and Genie is auto-recovering.
//  - sendConfirm exposed for Phase 2 confirmation flow.
//
// One store (Zustand) holds everything; the WS hook is the only writer of
// connection/transcript state.
import { useEffect, useState, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import PinGate from "./components/PinGate";
import StatusBar from "./components/StatusBar";
import SiriOrb from "./components/SiriOrb";
import ChatPanel from "./components/ChatPanel";
import VoiceBar from "./components/VoiceBar";
import BackgroundPlayer from "./components/BackgroundPlayer";
import { useWebSocket } from "./hooks/useWebSocket";
import { useAudioPlayer } from "./hooks/useAudioPlayer";
import { useAppStore, ORB_STATES } from "./store/appStore";

export default function App() {
  const [pin, setPin] = useState(null);          // null = still on the PIN gate
  const [authed, setAuthed] = useState(false);
  const [continuousMode, setContinuousMode] = useState(false); // hands-free mode
  const [showSettings, setShowSettings] = useState(false);
  const [wakeWordMode, setWakeWordMode] = useState(false); // wake word listening

  const wsStatus = useAppStore((s) => s.wsStatus);
  const orbState = useAppStore((s) => s.orbState);
  const amplitude = useAppStore((s) => s.amplitude);   // published by the mic recorder

  const { sendText, sendAudioChunk, endAudio, cancel: wsCancel, sendConfirm } = useWebSocket(pin);
  const { queueAudioChunk, stopAudio, isPlaying } = useAudioPlayer();

  const cancel = useCallback(() => {
    wsCancel();
    stopAudio();
  }, [wsCancel, stopAudio]);

  // Auto-reactivate listening in continuous mode after assistant finishes speaking
  useEffect(() => {
    if (continuousMode && orbState === ORB_STATES.IDLE && !isPlaying.current) {
      // Small delay to avoid immediately re-triggering
      const timer = setTimeout(() => {
        if (useAppStore.getState().orbState === ORB_STATES.IDLE) {
          // Signal to VoiceBar that it should auto-start recording
          useAppStore.setState({ shouldAutoRecord: true });
        }
      }, 800);
      return () => clearTimeout(timer);
    }
  }, [continuousMode, orbState, isPlaying]);

  // Watch the store for the auth_ok transition and inbound audio.
  // We subscribe explicitly so audio playback happens outside React render.
  useEffect(() => {
    if (wsStatus === "authed") setAuthed(true);
    if (wsStatus === "error" && pin && !authed) {
      // Wrong PIN: bounce back to the gate with an error flash.
      setAuthed(false);
    }
    // If we were authed but the connection dropped, stay on main UI
    // (the reconnecting banner will show instead of the PIN gate).
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
          queueAudioChunk(msg.audio, msg.mime || "audio/mpeg");
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
      {/* Reconnecting Banner — shown when backend connection drops */}
      <AnimatePresence>
        {(wsStatus === "reconnecting" || wsStatus === "disconnected") && authed && (
          <motion.div
            initial={{ opacity: 0, y: -30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }}
            className="absolute top-0 left-0 right-0 z-50 flex items-center justify-center gap-2 py-1.5 text-xs font-medium"
            style={{
              background: "linear-gradient(90deg, rgba(234,179,8,0.15), rgba(234,179,8,0.08))",
              borderBottom: "1px solid rgba(234,179,8,0.3)",
            }}
          >
            <motion.span
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ duration: 1.2, repeat: Infinity }}
              className="inline-block w-1.5 h-1.5 rounded-full bg-yellow-400"
            />
            <span className="text-yellow-300">Reconnecting to Genie…</span>
          </motion.div>
        )}
      </AnimatePresence>

      <StatusBar 
        continuousMode={continuousMode}
        onToggleContinuous={() => setContinuousMode(!continuousMode)}
        onSettings={() => setShowSettings(!showSettings)}
      />
      <BackgroundPlayer />
      {showSettings && (
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mx-4 mt-2 p-3 glass rounded-2xl text-xs text-gray-400 space-y-2"
        >
          <div className="flex items-center justify-between">
            <span>Continuous Conversation Mode</span>
            <button
              onClick={() => setContinuousMode(!continuousMode)}
              className={`px-3 py-1 rounded-full text-xs transition ${
                continuousMode 
                  ? 'bg-neon-cyan text-space-900' 
                  : 'bg-gray-700 text-gray-300'
              }`}
            >
              {continuousMode ? 'ON' : 'OFF'}
            </button>
          </div>
          <p className="text-[10px] text-gray-500">
            When enabled, Genie automatically listens after responding (like Alexa/Google)
          </p>
          
          <div className="flex items-center justify-between pt-2 border-t border-white/5">
            <span>Wake Word Mode (Auto-Listen)</span>
            <button
              onClick={() => setWakeWordMode(!wakeWordMode)}
              className={`px-3 py-1 rounded-full text-xs transition ${
                wakeWordMode 
                  ? 'bg-neon-pink text-white' 
                  : 'bg-gray-700 text-gray-300'
              }`}
            >
              {wakeWordMode ? 'ON' : 'OFF'}
            </button>
          </div>
          <p className="text-[10px] text-gray-500">
            When enabled, always listens for "Hey Genie" or "Okay Genie" (uses more battery)
          </p>
          
          {wakeWordMode && (
            <div className="pt-2 border-t border-white/5">
              <p className="text-[10px] text-neon-cyan mb-1">
                🎙️ Wake Word Active
              </p>
              <p className="text-[9px] text-gray-600">
                Say: "Hey Genie" or "Okay Genie"
              </p>
              <p className="text-[9px] text-gray-600">
                Check backend console for detection logs
              </p>
            </div>
          )}
        </motion.div>
      )}
      <div className="flex flex-col flex-1 min-h-0">
        {/* Modern Siri-style orb visualization */}
        <div className="flex-shrink-0 pt-4 pb-2">
          <SiriOrb state={orbState} amplitude={amplitude} />
          <motion.p 
            className="text-center text-sm font-medium tracking-wide mt-2"
            animate={{
              color: orbState === ORB_STATES.LISTENING ? "#22d3ee" :
                     orbState === ORB_STATES.THINKING ? "#a855f7" :
                     orbState === ORB_STATES.SPEAKING ? "#ec4899" :
                     "#6b7280"
            }}
            transition={{ duration: 0.3 }}
          >
            {labelFor(orbState)}
          </motion.p>
          {continuousMode && orbState === ORB_STATES.IDLE && (
            <motion.p 
              className="text-center text-[10px] text-neon-cyan mt-1"
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              Continuous mode active
            </motion.p>
          )}
        </div>

        {/* Chat transcript */}
        <ChatPanel />

        {/* Text + voice controls */}
        <VoiceBar
          sendText={sendText}
          sendAudioChunk={sendAudioChunk}
          endAudio={endAudio}
          cancel={cancel}
          continuousMode={continuousMode}
          wakeWordMode={wakeWordMode}
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
      className="h-screen w-screen flex flex-col overflow-hidden bg-transparent p-[2px]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {/* Outer Cyberpunk Glowing Frame */}
      <div className="absolute inset-0 pointer-events-none z-50">
        {/* Glow */}
        <div className="absolute inset-0 border-[2px] border-neon-cyan opacity-50 blur-[4px] m-1 cyber-panel" />
        {/* Sharp Border */}
        <div className="absolute inset-0 border-[2px] border-t-neon-cyan border-b-neon-pink border-l-neon-cyan border-r-neon-purple m-1 cyber-panel" />
        
        {/* Decorative corner cutouts & circuit lines (pseudo-elements via HTML) */}
        <div className="absolute top-0 left-[20%] w-16 h-1 bg-neon-cyan" />
        <div className="absolute bottom-0 right-[20%] w-16 h-1 bg-neon-pink" />
        <div className="absolute top-[20%] left-0 w-1 h-16 bg-neon-cyan" />
        <div className="absolute bottom-[20%] right-0 w-1 h-16 bg-neon-pink" />
        
        {/* Grid / Tech details */}
        <div className="absolute top-2 left-6 text-[8px] font-mono text-neon-cyan opacity-70">SYS_0X44</div>
        <div className="absolute bottom-2 right-6 text-[8px] font-mono text-neon-pink opacity-70">ONLINE</div>
      </div>

      <div
        className="flex-1 flex flex-col cyber-panel bg-[#0a0b1e]/20 overflow-hidden relative"
        style={{ WebkitAppRegion: "drag" }}
      >
        <div className="scanlines" />
        <div className="flex-1 flex flex-col min-h-0 relative z-10 p-2 md:p-3">
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
