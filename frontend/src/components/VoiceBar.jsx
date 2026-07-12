// VoiceBar: push-to-talk microphone control + text input. Sends audio frames
// while held (or toggled), then signals audio_end so the backend transcribes.
// Also hosts the text input for typed commands.
// Supports wake word mode: continuous listening with keyword detection
import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import { useAppStore, ORB_STATES } from "../store/appStore";

export default function VoiceBar({ sendAudioChunk, endAudio, sendText, cancel, continuousMode, wakeWordMode }) {
  const [text, setText] = useState("");
  const orbState = useAppStore((s) => s.orbState);
  const setOrbState = useAppStore((s) => s.setOrbState);
  const pushUserMessage = useAppStore((s) => s.pushUserMessage);
  const shouldAutoRecord = useAppStore((s) => s.shouldAutoRecord);
  const heldRef = useRef(false);

  const { recording, start, stop, setOnSilenceEnd } = useAudioRecorder({
    onChunk: (bytes) => sendAudioChunk(bytes),
    autoEndOnSilence: wakeWordMode,
    silenceThreshold: 2000, // 2 seconds of silence
  });
  const amplitude = useAppStore((s) => s.amplitude);   // drives the PTT ring

  // Set up silence end callback for wake word mode
  useEffect(() => {
    if (wakeWordMode && setOnSilenceEnd) {
      setOnSilenceEnd(() => {
        finishRecording();
      });
    }
  }, [wakeWordMode]);

  // Wake word detection is now handled by the backend.
  // The backend sends a "wake_word_detected" WebSocket message which sets shouldAutoRecord=true.
  const wakeWordListening = wakeWordMode && !recording && orbState === ORB_STATES.IDLE;

  // Show browser notification when wake word mode starts
  useEffect(() => {
    if (wakeWordMode) {
      // Check mic permissions first
      navigator.permissions?.query({ name: 'microphone' }).then((result) => {
        if (result.state === 'denied') {
          alert('⚠️ Microphone permission denied!\n\nPlease allow microphone access to use wake word mode.\n\n1. Click the 🎤 icon in your address bar\n2. Select "Always allow"\n3. Refresh the page');
        } else {
          console.log('✅ Wake word mode enabled - Say "Hey Genie" or "Okay Genie"');
        }
      }).catch(() => {
        // Permissions API not available, just log
        console.log('✅ Wake word mode enabled - Say "Hey Genie" or "Okay Genie"');
      });
    } else {
      console.log('⏹️ Wake word mode disabled');
    }
  }, [wakeWordMode]);

  // Auto-record in continuous mode or when wake word is detected by backend
  useEffect(() => {
    if (shouldAutoRecord && !recording && (continuousMode || wakeWordMode)) {
      useAppStore.setState({ shouldAutoRecord: false });
      beginRecording();
    }
  }, [shouldAutoRecord, recording, continuousMode, wakeWordMode]);

  const beginRecording = async () => {
    cancel(); // Halt any ongoing task/audio immediately
    heldRef.current = wakeWordMode ? false : true; // In wake word mode, don't hold
    setOrbState(ORB_STATES.LISTENING);
    await start();
  };

  const finishRecording = () => {
    // In wake word mode, auto-end after silence
    if (wakeWordMode) {
      // Will be triggered by silence detection or manual stop
      stop();
      endAudio();
      setOrbState(ORB_STATES.IDLE);
      return;
    }
    
    if (!heldRef.current) return;
    heldRef.current = false;
    stop();
    setOrbState(ORB_STATES.IDLE);
    endAudio(); // tell the backend to transcribe the buffered audio
  };

  const submitText = (e) => {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;
    cancel(); // Halt any ongoing task/audio immediately
    pushUserMessage(t);
    sendText(t);
    setText("");
  };

  const busy = orbState === ORB_STATES.THINKING || orbState === ORB_STATES.SPEAKING;

  return (
    <motion.div 
      className="px-4 pb-4 pt-2 space-y-3"
      style={{ WebkitAppRegion: "no-drag" }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Modern text input with Siri-style design */}
      <form onSubmit={submitText} className="flex gap-3">
        <motion.div className="flex-1 neon-border-wrapper cyber-pill" whileFocus={{ scale: 1.01 }}>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Ask me anything..."
            className="w-full h-full neon-border-content cyber-pill px-5 py-3 text-sm outline-none placeholder-gray-500 bg-[#0a0b1e] text-neon-cyan"
          />
        </motion.div>
        <motion.button
          type="submit"
          className="px-6 py-3 cyber-pill bg-gradient-to-r from-neon-cyan via-neon-blue to-neon-violet text-white font-bold text-sm shadow-[0_0_20px_rgba(34,211,238,0.4)]"
          whileHover={{ scale: 1.05, boxShadow: "0 0 30px rgba(59, 130, 246, 0.8)" }}
          whileTap={{ scale: 0.95 }}
        >
          Send
        </motion.button>
      </form>

      {/* Voice control row with Siri-style mic button */}
      <div className="flex items-center justify-center gap-4">
        {/* Enhanced push-to-talk button */}
        <motion.button
          onPointerDown={wakeWordMode ? undefined : beginRecording}
          onPointerUp={wakeWordMode ? undefined : finishRecording}
          onPointerLeave={wakeWordMode ? undefined : finishRecording}
          onClick={wakeWordMode && recording ? finishRecording : undefined}
          className={`relative w-20 h-20 rounded-full flex items-center justify-center transition-all
            ${wakeWordListening && !recording
              ? "bg-[#0a0b1e] border-2 border-neon-cyan shadow-[0_0_20px_rgba(34,211,238,0.4)]"
              : recording
              ? "bg-[#1a0b1e] border-2 border-neon-pink shadow-[0_0_40px_rgba(236,72,153,0.8)]"
              : "bg-[#0a0b1e] border border-white/20"}`}
          whileHover={{ scale: 1.1 }}
          whileTap={wakeWordMode ? {} : { scale: 0.9 }}
          title={wakeWordMode ? (recording ? "Click to stop" : "Say 'Hey Genie'") : "Hold to talk"}
        >
          {/* Animated rings for listening state */}
          {(recording || wakeWordListening) && (
            <>
              <motion.span
                className="absolute inset-0 rounded-full border-2"
                style={{ borderColor: recording ? "#ec4899" : "#22d3ee" }}
                animate={{ 
                  scale: [1, 1.4, 1], 
                  opacity: [0.6, 0, 0.6] 
                }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
              <motion.span
                className="absolute inset-0 rounded-full border-2"
                style={{ borderColor: recording ? "#ec4899" : "#22d3ee" }}
                animate={{ 
                  scale: [1, 1.7, 1], 
                  opacity: [0.4, 0, 0.4] 
                }}
                transition={{ duration: 1.5, repeat: Infinity, delay: 0.3 }}
              />
            </>
          )}
          
          {/* Amplitude-reactive ring */}
          {recording && (
            <motion.span
              className="absolute inset-0 rounded-full bg-neon-pink/30"
              animate={{ scale: 1 + amplitude * 0.5 }}
              transition={{ duration: 0.1 }}
            />
          )}
          
          <MicIcon active={recording || wakeWordListening} />
        </motion.button>

        {/* Cancel button when the assistant is busy */}
        <AnimatePresence>
          {busy && (
            <motion.button
              initial={{ opacity: 0, scale: 0.8, x: -20 }}
              animate={{ opacity: 1, scale: 1, x: 0 }}
              exit={{ opacity: 0, scale: 0.8, x: -20 }}
              onClick={cancel}
              className="px-6 py-2.5 cyber-pill bg-[#1a0b1e] border border-neon-pink text-sm text-neon-pink shadow-[0_0_15px_rgba(236,72,153,0.3)] transition-all"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              Stop
            </motion.button>
          )}
        </AnimatePresence>
      </div>
      
      {/* Status text with smooth transitions */}
      <motion.p 
        className="text-center text-xs text-gray-400"
        animate={{ 
          opacity: [0.7, 1, 0.7],
          color: wakeWordMode && wakeWordListening ? "#22d3ee" : "#9ca3af"
        }}
        transition={{ duration: 2, repeat: wakeWordMode && wakeWordListening ? Infinity : 0 }}
      >
        {wakeWordMode 
          ? wakeWordListening && !recording
            ? "🎙️ Listening for 'Hey Genie' or 'Okay Genie'..." 
            : recording
            ? "Speak your command (auto-ends on silence)"
            : "Wake word mode active"
          : recording 
            ? "Listening… release to send" 
            : continuousMode 
              ? "Say something or hold mic to talk" 
              : "Hold the mic to speak"}
      </motion.p>
    </motion.div>
  );
}

function MicIcon({ active }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
      stroke={active ? "#22d3ee" : "#3b82f6"} strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <line x1="12" y1="17" x2="12" y2="22" />
    </svg>
  );
}
