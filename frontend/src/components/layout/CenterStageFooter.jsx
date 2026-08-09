/**
 * CenterStageFooter.jsx — Floating bottom controls overlay over center 3D avatar stage
 * Displays Voice waveform, live transcript card, and interactive text/voice input bar.
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import MicrophoneButton from '../MicrophoneButton';

function stripCueTags(text) {
  return (text || "").replace(/\[\[[a-z]+\]\]/gi, "").trim();
}

function SpeakingWaveform() {
  const BARS = [0.4, 0.7, 1.0, 0.8, 0.6, 0.9, 0.5, 0.75, 0.45, 0.65];
  return (
    <div className="flex items-center justify-center gap-[3px]" style={{ height: 20 }}>
      {BARS.map((h, i) => (
        <motion.span
          key={i}
          className="rounded-full inline-block"
          style={{
            width: 3,
            background: 'linear-gradient(to top, #34d399, #22d3ee)',
          }}
          animate={{ height: [3, 6 + h * 14, 3] }}
          transition={{ duration: 0.55 + h * 0.15, repeat: Infinity, delay: i * 0.07, ease: 'easeInOut' }}
        />
      ))}
    </div>
  );
}

function ListeningDots() {
  return (
    <div className="flex items-center gap-1.5">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="inline-block rounded-full"
          style={{ width: 6, height: 6, background: '#22d3ee' }}
          animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 0.65, repeat: Infinity, delay: i * 0.16 }}
        />
      ))}
    </div>
  );
}

export default function CenterStageFooter() {
  const genieState = useAppStore((s) => s.genieState);
  const liveTranscript = useAppStore((s) => s.liveTranscript);
  const pushUserMessage = useAppStore((s) => s.pushUserMessage);
  const ws = useAppStore((s) => s.ws);

  const [inputVal, setInputVal] = useState('');

  const isSpeaking = genieState === 'speaking';
  const isListening = genieState === 'listening' || genieState === 'follow_up_listening';

  const handleSendText = (e) => {
    e.preventDefault();
    const trimmed = inputVal.trim();
    if (!trimmed) return;

    pushUserMessage(trimmed);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'user_text_input', text: trimmed }));
    }
    setInputVal('');
  };

  return (
    <footer className="absolute bottom-0 left-0 right-0 z-20 p-4 pointer-events-none flex flex-col items-center gap-3">
      {/* ── LIVE TRANSCRIPT / WAVEFORM BANNER ──────────────────────────── */}
      <AnimatePresence>
        {(isListening || (isSpeaking && liveTranscript && liveTranscript.length > 0)) && (
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.96 }}
            transition={{ duration: 0.22 }}
            className="pointer-events-auto max-w-lg w-full flex items-center gap-3 px-4 py-2.5 rounded-2xl shadow-xl"
            style={{
              background: isListening ? 'rgba(15, 23, 42, 0.85)' : 'rgba(6, 78, 59, 0.85)',
              border: `1px solid ${isListening ? 'rgba(34, 211, 238, 0.3)' : 'rgba(52, 211, 153, 0.3)'}`,
              backdropFilter: 'blur(20px)',
              boxShadow: isListening ? '0 0 24px rgba(34,211,238,0.15)' : '0 0 24px rgba(52,211,153,0.15)',
            }}
          >
            {isListening ? <ListeningDots /> : <SpeakingWaveform />}
            <p
              className="text-xs font-medium flex-1 truncate"
              style={{ color: isListening ? '#22d3ee' : '#34d399' }}
            >
              {isListening
                ? (liveTranscript && liveTranscript !== 'Listening...' ? stripCueTags(liveTranscript) : 'Listening for command…')
                : stripCueTags(liveTranscript)}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── INPUT BAR OVERLAY (Text Input + Mic Toggle) ─────────────────── */}
      <div className="pointer-events-auto max-w-xl w-full flex items-center gap-3">
        {/* Interactive Text Prompt Input Box */}
        <form
          onSubmit={handleSendText}
          className="flex-1 flex items-center gap-2 px-4 py-2.5 rounded-2xl border bg-black/50 backdrop-blur-2xl shadow-2xl transition-all focus-within:border-cyan-500/50"
          style={{ borderColor: 'rgba(255, 255, 255, 0.12)' }}
        >
          <span className="text-slate-400 text-sm">💬</span>
          <input
            type="text"
            placeholder="Ask Genie anything or type a command..."
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            className="w-full bg-transparent text-xs text-white placeholder-slate-400 focus:outline-none"
          />
          {inputVal.trim() && (
            <button
              type="submit"
              className="px-3 py-1 rounded-xl text-xs font-semibold bg-cyan-500 text-slate-950 hover:bg-cyan-400 transition-colors shadow-md"
            >
              Send
            </button>
          )}
        </form>

        {/* Microphone Button */}
        <div className="flex-shrink-0">
          <MicrophoneButton />
        </div>
      </div>
    </footer>
  );
}
