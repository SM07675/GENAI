import React, { useEffect, useRef, useState } from "react";
import { useAppStore } from "./store/appStore";
import { useVoicePipeline } from "./hooks/useVoicePipeline";
import { useWebSocket } from "./hooks/useWebSocket";
import { useAudioPlayer } from "./hooks/useAudioPlayer";
import GenieFace from "./components/GenieFace/GenieFace";
import MicrophoneButton from "./components/MicrophoneButton";
import MinimalControls from "./components/MinimalControls";
import PinGate from "./components/PinGate";
import BackgroundPlayer from "./components/BackgroundPlayer";
import { AnimatePresence, motion } from "framer-motion";

/* ─── Aurora background ─────────────────────────────────────────────────── */
function AuroraBackground() {
  return (
    <div className="genie-bg fixed inset-0 pointer-events-none" style={{ zIndex: 0 }} />
  );
}

/* ─── System note toast ─────────────────────────────────────────────────── */
function SystemNoteToast() {
  const systemNote = useAppStore((s) => s.systemNote);
  return (
    <AnimatePresence>
      {systemNote && (
        <motion.div
          key="system-note"
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          className="absolute bottom-36 left-1/2 -translate-x-1/2 z-50 pointer-events-none"
        >
          <div
            className="flex items-center gap-2 px-4 py-2.5 rounded-2xl text-sm font-medium"
            style={{
              background: 'rgba(251,191,36,0.10)',
              border: '1px solid rgba(251,191,36,0.25)',
              color: '#fbbf24',
              backdropFilter: 'blur(16px)',
              maxWidth: '88vw',
              boxShadow: '0 4px 20px rgba(251,191,36,0.15)',
            }}
          >
            <span>⚡</span>
            <span>{systemNote}</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ─── Status pill ───────────────────────────────────────────────────────── */
const STATUS_CONFIG = {
  sleeping:            { label: 'Say "Hey Genie"', color: '#64748b', pulse: false },
  waking:              { label: 'Waking up…',       color: '#38bdf8', pulse: true  },
  idle:                { label: 'Ready',             color: '#64748b', pulse: false },
  listening:           { label: 'Listening',         color: '#22d3ee', pulse: true  },
  transcribing:        { label: 'Processing…',       color: '#a78bfa', pulse: true  },
  thinking:            { label: 'Thinking…',         color: '#c084fc', pulse: true  },
  executing:           { label: 'Working…',          color: '#f59e0b', pulse: true  },
  speaking:            { label: 'Speaking',          color: '#34d399', pulse: true  },
  follow_up_listening: { label: 'Listening…',        color: '#22d3ee', pulse: true  },
  interrupted:         { label: 'Stopped',           color: '#fb923c', pulse: false },
  error:               { label: 'Error',             color: '#f87171', pulse: false },
};

function StatusPill({ state }) {
  const c = STATUS_CONFIG[state] || STATUS_CONFIG.sleeping;
  return (
    <motion.div
      key={state}
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -6 }}
      transition={{ duration: 0.2 }}
      className="flex items-center gap-2 px-3 py-1.5 rounded-full"
      style={{
        background: `${c.color}14`,
        border: `1px solid ${c.color}30`,
        backdropFilter: 'blur(12px)',
      }}
    >
      <span className="relative flex items-center justify-center" style={{ width: 7, height: 7 }}>
        {c.pulse && (
          <span
            className="absolute inline-flex h-full w-full rounded-full"
            style={{ backgroundColor: c.color, opacity: 0.6, animation: 'ping 1.4s cubic-bezier(0,0,0.2,1) infinite' }}
          />
        )}
        <span className="relative inline-flex rounded-full" style={{ width: 5, height: 5, backgroundColor: c.color }} />
      </span>
      <span className="text-xs font-semibold tracking-wide" style={{ color: c.color }}>
        {c.label}
      </span>
    </motion.div>
  );
}

/* ─── Genie orb avatar ──────────────────────────────────────────────────── */
function GenieOrb({ state }) {
  const isSpeaking = state === 'speaking';
  const isListening = state === 'listening' || state === 'follow_up_listening';
  const isThinking = ['thinking', 'transcribing', 'executing'].includes(state);

  let glowColor = 'rgba(99,102,241,0.4)';
  if (isSpeaking)  glowColor = 'rgba(52,211,153,0.5)';
  if (isListening) glowColor = 'rgba(34,211,238,0.5)';
  if (isThinking)  glowColor = 'rgba(168,85,247,0.5)';

  return (
    <motion.div
      animate={isSpeaking || isListening ? { scale: [1, 1.06, 1] } : { scale: 1 }}
      transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
      className="relative flex-shrink-0"
      style={{ width: 36, height: 36 }}
    >
      {/* Glow ring */}
      <motion.div
        className="absolute inset-0 rounded-full"
        animate={{ opacity: (isSpeaking || isListening) ? [0.4, 0.8, 0.4] : 0.3 }}
        transition={{ duration: 1.5, repeat: Infinity }}
        style={{ background: glowColor, filter: 'blur(8px)', borderRadius: '50%' }}
      />
      {/* Orb */}
      <div
        className="absolute inset-0 rounded-full flex items-center justify-center"
        style={{
          background: 'conic-gradient(from 0deg, #22d3ee, #6366f1, #a855f7, #22d3ee)',
          boxShadow: `0 0 16px ${glowColor}`,
        }}
      >
        <div
          className="w-full h-full rounded-full flex items-center justify-center"
          style={{ background: 'rgba(7,11,20,0.4)', fontSize: 14, color: '#fff', fontWeight: 700 }}
        >
          G
        </div>
      </div>
    </motion.div>
  );
}

/* ─── Chat bubble ───────────────────────────────────────────────────────── */
function ChatBubble({ role, text, isStreaming }) {
  const isUser = role === 'user';
  return (
    <motion.div
      initial={{ opacity: 0, y: 14, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} w-full items-end gap-2`}
    >
      {!isUser && (
        <div className="flex-shrink-0 mb-0.5"
          style={{
            width: 26, height: 26, borderRadius: '50%',
            background: 'conic-gradient(from 0deg,#22d3ee,#6366f1,#a855f7,#22d3ee)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 11, fontWeight: 700, color: '#fff',
            boxShadow: '0 0 12px rgba(99,102,241,0.4)',
          }}
        >G</div>
      )}

      <div
        className={`max-w-[78%] px-4 py-3 text-sm leading-relaxed ${
          isUser ? 'rounded-2xl rounded-br-sm' : 'rounded-2xl rounded-bl-sm'
        } ${isUser ? 'bubble-user' : 'bubble-assistant'}`}
      >
        {text}
        {isStreaming && (
          <motion.span
            className="inline-block ml-1"
            animate={{ opacity: [1, 0, 1] }}
            transition={{ duration: 0.8, repeat: Infinity }}
            style={{ color: '#34d399' }}
          >▋</motion.span>
        )}
      </div>
    </motion.div>
  );
}

/* ─── Waveform (speaking) ───────────────────────────────────────────────── */
function SpeakingWaveform() {
  const BARS = [0.4, 0.7, 1.0, 0.8, 0.6, 0.9, 0.5, 0.75, 0.45, 0.65];
  return (
    <div className="flex items-center justify-center gap-[3px]" style={{ height: 28 }}>
      {BARS.map((h, i) => (
        <motion.span
          key={i}
          className="rounded-full"
          style={{
            width: 3,
            background: 'linear-gradient(to top, #34d399, #22d3ee)',
            display: 'inline-block',
            borderRadius: 99,
          }}
          animate={{ height: [3, 8 + h * 18, 3] }}
          transition={{ duration: 0.55 + h * 0.15, repeat: Infinity, delay: i * 0.07, ease: 'easeInOut' }}
        />
      ))}
    </div>
  );
}

/* ─── Listening dots ────────────────────────────────────────────────────── */
function ListeningDots() {
  return (
    <div className="flex items-center gap-1.5">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="inline-block rounded-full"
          style={{ width: 6, height: 6, background: '#22d3ee' }}
          animate={{ y: [0, -5, 0], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 0.65, repeat: Infinity, delay: i * 0.16 }}
        />
      ))}
    </div>
  );
}

/* ─── Thinking indicator (in chat) ─────────────────────────────────────── */
function ThinkingBubble() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 8 }}
      className="flex items-end gap-2"
    >
      <div style={{
        width: 26, height: 26, borderRadius: '50%',
        background: 'conic-gradient(from 0deg,#22d3ee,#6366f1,#a855f7,#22d3ee)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 11, fontWeight: 700, color: '#fff',
        flexShrink: 0,
      }}>G</div>
      <div
        className="bubble-assistant px-4 py-3 rounded-2xl rounded-bl-sm flex items-center gap-1.5"
      >
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="inline-block rounded-full"
            style={{ width: 6, height: 6, background: '#a78bfa' }}
            animate={{ y: [0, -4, 0], opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 0.55, repeat: Infinity, delay: i * 0.14 }}
          />
        ))}
      </div>
    </motion.div>
  );
}

/* ─── Empty state ───────────────────────────────────────────────────────── */
function EmptyState({ state }) {
  const messages = {
    sleeping: { icon: '🌙', title: 'Hey Genie', sub: 'Say "Hey Genie" to start a conversation' },
    waking:   { icon: '✨', title: 'Hi there!', sub: 'Listening for your command…' },
    idle:     { icon: '💫', title: 'Ready',     sub: 'Tap the mic or say "Hey Genie"' },
  };
  const m = messages[state] || messages.idle;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5 }}
      className="flex flex-col items-center justify-center gap-4 py-16 pointer-events-none select-none"
    >
      <motion.div
        animate={{ y: [0, -6, 0] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        style={{ fontSize: 48 }}
      >{m.icon}</motion.div>
      <div className="text-center">
        <p className="text-lg font-semibold shimmer-text mb-1">{m.title}</p>
        <p className="text-sm text-slate-500">{m.sub}</p>
      </div>
    </motion.div>
  );
}

/* ─── Main App ──────────────────────────────────────────────────────────── */
export default function App() {
  const [pin, setPin] = useState(null);
  const wsStatus = useAppStore((s) => s.wsStatus);
  const authed = wsStatus === "authed";

  useEffect(() => {
    if (wsStatus === "error") setPin(null);
  }, [wsStatus]);

  const audioRef = useRef(null);
  const setAssistantAudioElement = useAppStore((s) => s.setAssistantAudioElement);

  useEffect(() => {
    setAssistantAudioElement(audioRef.current);
    return () => setAssistantAudioElement(null);
  }, [setAssistantAudioElement]);

  const { queueAudioChunk, stopAudio, notifyTtsDone } = useAudioPlayer(audioRef);
  useWebSocket(pin, queueAudioChunk, stopAudio, notifyTtsDone);
  useVoicePipeline();

  const genieState    = useAppStore((s) => s.genieState);
  const liveTranscript = useAppStore((s) => s.liveTranscript);
  const messages      = useAppStore((s) => s.messages);
  const currentAssistantId = useAppStore((s) => s.currentAssistantId);

  const scrollRef = useRef(null);
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, liveTranscript]);

  const recentMessages = messages.slice(-10);
  const isSpeaking  = genieState === 'speaking';
  const isListening = genieState === 'listening' || genieState === 'follow_up_listening';
  const isThinking  = ['thinking', 'transcribing', 'executing'].includes(genieState);
  const isActive    = isSpeaking || isListening || isThinking;
  const hasConversation = recentMessages.length > 0;

  /* ─── PIN gate ─────────────────────────────────── */
  if (!authed) {
    return (
      <div className="relative flex flex-col items-center justify-center h-screen w-screen overflow-hidden">
        <AuroraBackground />
        <div className="relative z-10">
          <MinimalControls />
          <PinGate key={pin ? "retry" : "fresh"} onSubmit={setPin} />
        </div>
      </div>
    );
  }

  /* ─── Main UI ──────────────────────────────────── */
  return (
    <div className="relative flex flex-col h-screen w-screen overflow-hidden" style={{ zIndex: 1 }}>
      <AuroraBackground />

      {/* ── TOP BAR ───────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative z-20 flex-shrink-0 flex items-center justify-between px-4 pt-4 pb-3"
        style={{
          background: 'linear-gradient(to bottom, rgba(7,11,20,0.8) 0%, transparent 100%)',
        }}
      >
        {/* Left: avatar + name + status */}
        <div className="flex items-center gap-2.5">
          <GenieOrb state={genieState} />
          <div className="flex flex-col">
            <span className="text-sm font-bold shimmer-text leading-none mb-0.5">Genie</span>
            <AnimatePresence mode="wait">
              <StatusPill key={genieState} state={genieState} />
            </AnimatePresence>
          </div>
        </div>

        {/* Right: controls */}
        <MinimalControls embedded />
      </motion.div>

      {/* ── DIVIDER ───────────────────────────────── */}
      <div className="relative z-10 flex-shrink-0 mx-4 h-px" style={{ background: 'rgba(255,255,255,0.05)' }} />

      {/* ── CONVERSATION AREA ─────────────────────── */}
      <div
        ref={scrollRef}
        className="relative z-10 flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3"
        style={{ scrollbarWidth: 'thin' }}
      >
        {!hasConversation ? (
          <div className="flex-1 flex items-center justify-center">
            <AnimatePresence mode="wait">
              <EmptyState key={genieState} state={genieState} />
            </AnimatePresence>
          </div>
        ) : (
          <>
            {recentMessages.map((msg) => (
              <ChatBubble
                key={msg.id}
                role={msg.role}
                text={msg.text}
                isStreaming={msg.id === currentAssistantId && isSpeaking}
              />
            ))}

            <AnimatePresence>
              {isThinking && !currentAssistantId && (
                <ThinkingBubble key="thinking" />
              )}
            </AnimatePresence>
          </>
        )}
      </div>

      {/* ── BOTTOM BAR ────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative z-20 flex-shrink-0 px-4 pt-2 pb-6"
        style={{
          background: 'linear-gradient(to top, rgba(7,11,20,0.95) 0%, rgba(7,11,20,0.6) 60%, transparent 100%)',
        }}
      >
        {/* Live transcript / speaking bar */}
        <AnimatePresence>
          {(isListening || (isSpeaking && liveTranscript && liveTranscript.length > 0)) && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.97 }}
              transition={{ duration: 0.22 }}
              className="mb-3 mx-2 flex items-center gap-3 px-4 py-2.5 rounded-2xl"
              style={{
                background: isListening ? 'rgba(34,211,238,0.07)' : 'rgba(52,211,153,0.07)',
                border: `1px solid ${isListening ? 'rgba(34,211,238,0.18)' : 'rgba(52,211,153,0.18)'}`,
                backdropFilter: 'blur(16px)',
                boxShadow: isListening
                  ? '0 0 20px rgba(34,211,238,0.08)'
                  : '0 0 20px rgba(52,211,153,0.08)',
              }}
            >
              {isListening ? <ListeningDots /> : <SpeakingWaveform />}
              <p
                className="text-sm font-medium flex-1 truncate"
                style={{ color: isListening ? '#22d3ee' : '#34d399' }}
              >
                {isListening
                  ? (liveTranscript && liveTranscript !== 'Listening...' ? liveTranscript : 'Listening…')
                  : liveTranscript}
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Mic button */}
        <div className="flex justify-center">
          <MicrophoneButton />
        </div>
      </motion.div>

      {/* ── Extras ────────────────────────────────── */}
      <audio ref={audioRef} className="hidden" />
      <SystemNoteToast />
      <BackgroundPlayer />
    </div>
  );
}
