import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../store/appStore';

const MicIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width={22} height={22}>
    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
  </svg>
);

const StopIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width={20} height={20}>
    <rect x="6" y="6" width="12" height="12" rx="3" />
  </svg>
);

const MicOffIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width={22} height={22}>
    <path d="M19 11h-2c0 .91-.25 1.76-.68 2.5l1.49 1.49C18.57 13.82 19 12.46 19 11zM14.97 14.97l-2.02-2.02L12 12 9.03 9.03 7.01 7.01 4.22 4.22 2.81 5.63l1.83 1.83C4.24 8.53 4 9.74 4 11h2c0-1.66.68-3.15 1.76-4.24l2.25 2.25V11c0 1.11.89 2 2 2 .39 0 .74-.11 1.05-.29l3.32 3.32c-1.31.74-2.82 1.16-4.38 1.16-3.39 0-6-2.61-6-6H4c0 3.53 2.61 6.43 6 6.92V21h4v-3.08c3.39-.49 6-3.39 6-6.92 0-.25-.03-.49-.07-.73l1.44 1.44 1.41-1.41-5.81-5.81zM12 14c.48 0 .9-.18 1.25-.47L8.47 8.75A2.98 2.98 0 009 11v3zM15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v1.17l2 2V5c0-.55.45-1 1-1s1 .45 1 1v4.17l2 2V5z" />
  </svg>
);

export default function MicrophoneButton() {
  const toggleListening = useAppStore((s) => s.toggleListening);
  const genieState      = useAppStore((s) => s.genieState);
  const amplitude       = useAppStore((s) => s.amplitude);

  const isListening = ['listening', 'follow_up_listening', 'waking'].includes(genieState);
  const isActive    = ['thinking', 'executing', 'transcribing', 'speaking'].includes(genieState);
  const isSleeping  = genieState === 'sleeping' || genieState === 'idle';

  // ── Per-state styles ─────────────────────────────────────────────────────
  let buttonBg, iconEl, shadowColor, ringColor, label;

  if (isActive) {
    // Red stop — clear and prominent
    buttonBg    = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
    shadowColor = 'rgba(239,68,68,0.5)';
    ringColor   = 'rgba(239,68,68,0.3)';
    iconEl      = <StopIcon />;
    label       = 'Stop';
  } else if (isListening) {
    // Cyan-to-indigo gradient — "listening" feel
    buttonBg    = 'linear-gradient(135deg, #22d3ee 0%, #6366f1 100%)';
    shadowColor = 'rgba(34,211,238,0.55)';
    ringColor   = 'rgba(34,211,238,0.35)';
    iconEl      = <MicIcon />;
    label       = 'Listening';
  } else if (isSleeping) {
    // Dark glass — subtle, not calling attention
    buttonBg    = 'rgba(22,28,52,0.80)';
    shadowColor = 'rgba(99,102,241,0.2)';
    ringColor   = 'transparent';
    iconEl      = <MicOffIcon />;
    label       = 'Wake';
  } else {
    // Indigo-violet — "ready" feel
    buttonBg    = 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)';
    shadowColor = 'rgba(99,102,241,0.5)';
    ringColor   = 'rgba(99,102,241,0.3)';
    iconEl      = <MicIcon />;
    label       = 'Speak';
  }

  const SIZE = 68;
  const ampScale = isListening ? 1 + amplitude * 0.25 : 1;

  return (
    <div className="relative flex flex-col items-center gap-2.5">

      {/* ── Ambient glow behind button ─────────────────────────────── */}
      <motion.div
        className="absolute rounded-full pointer-events-none"
        animate={{
          scale:   isListening ? [1, 1.3, 1] : [1, 1.05, 1],
          opacity: isListening ? [0.4, 0.7, 0.4] : isActive ? [0.3, 0.5, 0.3] : 0.2,
        }}
        transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          width: SIZE + 24,
          height: SIZE + 24,
          background: shadowColor,
          filter: 'blur(18px)',
        }}
      />

      {/* ── Ripple rings (listening) ───────────────────────────────── */}
      <AnimatePresence>
        {isListening && (
          <>
            <motion.div
              className="absolute rounded-full pointer-events-none"
              initial={{ opacity: 0.5, scale: 1 }}
              animate={{ opacity: 0, scale: 2.1 }}
              transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut' }}
              style={{ width: SIZE, height: SIZE, background: ringColor }}
            />
            <motion.div
              className="absolute rounded-full pointer-events-none"
              initial={{ opacity: 0.3, scale: 1 }}
              animate={{ opacity: 0, scale: 2.7 }}
              transition={{ duration: 1.6, repeat: Infinity, delay: 0.45, ease: 'easeOut' }}
              style={{ width: SIZE, height: SIZE, background: ringColor }}
            />
          </>
        )}
      </AnimatePresence>

      {/* ── Amplitude ring ────────────────────────────────────────── */}
      {isListening && amplitude > 0.04 && (
        <motion.div
          className="absolute rounded-full pointer-events-none"
          animate={{ width: SIZE + amplitude * 55, height: SIZE + amplitude * 55, opacity: 0.45 }}
          transition={{ type: 'tween', duration: 0.07 }}
          style={{ background: ringColor }}
        />
      )}

      {/* ── Main button ───────────────────────────────────────────── */}
      <motion.button
        id="genie-mic-button"
        whileHover={{ scale: 1.06 }}
        whileTap={{ scale: 0.91 }}
        animate={{ scale: ampScale }}
        transition={{ type: 'spring', stiffness: 200, damping: 18 }}
        onClick={() => toggleListening?.()}
        aria-label={label}
        title={isActive ? 'Stop Genie' : isListening ? 'Listening…' : 'Talk to Genie'}
        className="relative z-10 flex items-center justify-center"
        style={{
          width: SIZE,
          height: SIZE,
          borderRadius: SIZE / 2,
          background: buttonBg,
          border: '1px solid rgba(255,255,255,0.12)',
          boxShadow: `0 8px 32px ${shadowColor}, 0 2px 8px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.15)`,
          cursor: 'pointer',
          color: '#fff',
        }}
      >
        <AnimatePresence mode="wait">
          <motion.span
            key={genieState}
            initial={{ opacity: 0, scale: 0.65, rotate: -10 }}
            animate={{ opacity: 1, scale: 1, rotate: 0 }}
            exit={{ opacity: 0, scale: 0.65, rotate: 10 }}
            transition={{ duration: 0.18 }}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            {iconEl}
          </motion.span>
        </AnimatePresence>
      </motion.button>

      {/* ── Stop label ────────────────────────────────────────────── */}
      <AnimatePresence>
        {isActive && (
          <motion.span
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="text-xs font-semibold tracking-widest uppercase"
            style={{ color: '#f87171', letterSpacing: '0.12em' }}
          >
            tap to stop
          </motion.span>
        )}
      </AnimatePresence>
    </div>
  );
}
