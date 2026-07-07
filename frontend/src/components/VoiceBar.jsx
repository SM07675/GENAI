// VoiceBar: push-to-talk microphone control + text input. Sends audio frames
// while held (or toggled), then signals audio_end so the backend transcribes.
// Also hosts the text input for typed commands.
import { useState, useRef } from "react";
import { motion } from "framer-motion";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import { useAppStore, ORB_STATES } from "../store/appStore";

export default function VoiceBar({ sendAudioChunk, endAudio, sendText, cancel }) {
  const [text, setText] = useState("");
  const orbState = useAppStore((s) => s.orbState);
  const setOrbState = useAppStore((s) => s.setOrbState);
  const pushUserMessage = useAppStore((s) => s.pushUserMessage);
  const heldRef = useRef(false);

  const { recording, start, stop } = useAudioRecorder({
    onChunk: (bytes) => sendAudioChunk(bytes),
  });
  const amplitude = useAppStore((s) => s.amplitude);   // drives the PTT ring

  const beginRecording = async () => {
    heldRef.current = true;
    setOrbState(ORB_STATES.LISTENING);
    await start();
  };

  const finishRecording = () => {
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
    pushUserMessage(t);
    sendText(t);
    setText("");
  };

  const busy = orbState === ORB_STATES.THINKING || orbState === ORB_STATES.SPEAKING;

  return (
    <div className="px-4 pb-4 pt-2 space-y-3">
      {/* Text input */}
      <form onSubmit={submitText} className="flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type a command…"
          className="flex-1 glass px-4 py-2.5 text-sm outline-none focus:shadow-glow placeholder-gray-500"
        />
        <button
          type="submit"
          className="px-4 py-2.5 rounded-2xl bg-gradient-to-r from-neon-cyan to-neon-violet text-space-900 font-semibold text-sm hover:opacity-90 transition"
        >
          Send
        </button>
      </form>

      {/* Voice control row */}
      <div className="flex items-center justify-center gap-4">
        {/* Push-to-talk */}
        <motion.button
          onPointerDown={beginRecording}
          onPointerUp={finishRecording}
          onPointerLeave={finishRecording}
          whileTap={{ scale: 0.95 }}
          className={`relative w-16 h-16 rounded-full flex items-center justify-center transition-colors
            ${recording
              ? "bg-neon-pink shadow-[0_0_30px_rgba(236,72,153,0.7)]"
              : "bg-gradient-to-br from-neon-cyan to-neon-violet shadow-glow"}`}
          title="Hold to talk"
        >
          {recording && (
            <motion.span
              className="absolute inset-0 rounded-full border-2 border-neon-pink"
              animate={{ scale: 1 + amplitude * 0.6, opacity: 1 - amplitude }}
              transition={{ duration: 0.1 }}
            />
          )}
          <MicIcon active={recording} />
        </motion.button>

        {/* Cancel button when the assistant is busy */}
        {busy && (
          <motion.button
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={cancel}
            className="px-4 py-2 rounded-xl glass text-sm text-gray-300 hover:text-white"
          >
            Stop
          </motion.button>
        )}
      </div>
      <p className="text-center text-[11px] text-gray-600">
        {recording ? "Listening… release to send" : "Hold the mic to speak"}
      </p>
    </div>
  );
}

function MicIcon({ active }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
      stroke={active ? "#fff" : "#05060f"} strokeWidth="2.2"
      strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <line x1="12" y1="17" x2="12" y2="22" />
    </svg>
  );
}
