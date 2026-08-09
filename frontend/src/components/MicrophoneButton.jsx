import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../store/appStore';

// ── Icons ─────────────────────────────────────────────────────────────────────
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

// ── Size ──────────────────────────────────────────────────────────────────────
const SIZE = 68;

export default function MicrophoneButton() {
  const toggleListening = useAppStore((s) => s.toggleListening);
  const genieState      = useAppStore((s) => s.genieState);
  const amplitude       = useAppStore((s) => s.amplitude);
  const wsStatus        = useAppStore((s) => s.wsStatus);

  const isConnected = wsStatus === 'authed' || wsStatus === 'connected';

  // ── Derive display state ────────────────────────────────────────────────────
  // Active (cancellable)
  const isActive = ['thinking', 'executing', 'transcribing', 'speaking'].includes(genieState);
  // Listening (mic live)
  const isListening = ['listening', 'follow_up_listening', 'waking'].includes(genieState);
  // Ready (waiting for wake word or manual press)
  const isReady = ['idle', 'sleeping'].includes(genieState) || !genieState;

  // ── Per-state appearance ──────────────────────────────────────────────────
  let buttonBg, iconEl, shadowColor, ringColor, label, pulse;

  if (!isConnected) {
    // Offline — grey, no interaction
    buttonBg    = 'rgba(30,36,60,0.80)';
    shadowColor = 'rgba(100,116,139,0.15)';
    ringColor   = 'transparent';
    iconEl      = <MicIcon />;
    label       = 'Offline';
    pulse       = false;
  } else if (isActive) {
    // Red stop button — tap to cancel
    buttonBg    = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
    shadowColor = 'rgba(239,68,68,0.55)';
    ringColor   = 'rgba(239,68,68,0.35)';
    iconEl      = <StopIcon />;
    label       = 'Stop';
    pulse       = true;
  } else if (isListening) {
    // Cyan-to-indigo — actively listening
    buttonBg    = 'linear-gradient(135deg, #22d3ee 0%, #6366f1 100%)';
    shadowColor = 'rgba(34,211,238,0.55)';
    ringColor   = 'rgba(34,211,238,0.35)';
    iconEl      = <MicIcon />;
    label       = 'Listening';
    pulse       = true;
  } else {
    // Indigo — ready for wake word / tap to activate
    buttonBg    = 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)';
    shadowColor = 'rgba(99,102,241,0.45)';
    ringColor   = 'rgba(99,102,241,0.3)';
    iconEl      = <MicIcon />;
    label       = 'Tap to speak';
    pulse       = false;
  }

  // Amplitude ring scale (only while listening)
  const ampScale = isListening ? 1 + amplitude * 0.22 : 1;

  const handleClick = () => {
    if (!isConnected) return;
    if (toggleListening) {
      toggleListening();
    } else {
      // Fallback: send manual_wake directly via WS
      const ws = useAppStore.getState().ws;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'manual_wake' }));
      }
    }
  };

  return (
    <div className="relative flex flex-col items-center gap-2.5">

      {/* Ambient glow */}
      <motion.div
        className="absolute rounded-full pointer-events-none"
        animate={{
          scale:   pulse ? [1, 1.35, 1] : [1, 1.06, 1],
          opacity: isActive ? [0.35, 0.6, 0.35] : isListening ? [0.4, 0.75, 0.4] : [0.2, 0.3, 0.2],
        }}
        transition={{ duration: isListening ? 1.4 : 2.2, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          width: SIZE + 26,
          height: SIZE + 26,
          background: shadowColor,
          filter: 'blur(20px)',
        }}
      />

      {/* Ripple rings (listening / active) */}
      <AnimatePresence>
        {(isListening || isActive) && (
          <>
            <motion.div
              className="absolute rounded-full pointer-events-none"
              initial={{ opacity: 0.55, scale: 1 }}
              animate={{ opacity: 0, scale: 2.2 }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
              style={{ width: SIZE, height: SIZE, background: ringColor }}
            />
            <motion.div
              className="absolute rounded-full pointer-events-none"
              initial={{ opacity: 0.35, scale: 1 }}
              animate={{ opacity: 0, scale: 2.8 }}
              transition={{ duration: 1.5, repeat: Infinity, delay: 0.5, ease: 'easeOut' }}
              style={{ width: SIZE, height: SIZE, background: ringColor }}
            />
          </>
        )}
      </AnimatePresence>

      {/* Amplitude ring (voice level visualization) */}
      {isListening && amplitude > 0.03 && (
        <motion.div
          className="absolute rounded-full pointer-events-none"
          animate={{ width: SIZE + amplitude * 60, height: SIZE + amplitude * 60, opacity: 0.45 }}
          transition={{ type: 'tween', duration: 0.06 }}
          style={{ background: ringColor }}
        />
      )}

      {/* Main button */}
      <motion.button
        id="genie-mic-button"
        whileHover={isConnected ? { scale: 1.07 } : {}}
        whileTap={isConnected ? { scale: 0.90 } : {}}
        animate={{ scale: ampScale }}
        transition={{ type: 'spring', stiffness: 220, damping: 18 }}
        onClick={handleClick}
        aria-label={label}
        title={
          !isConnected ? 'Backend offline'
          : isActive   ? 'Tap to stop Genie'
          : isListening ? 'Listening…'
          : 'Tap to speak to Genie'
        }
        className="relative z-10 flex items-center justify-center"
        style={{
          width: SIZE,
          height: SIZE,
          borderRadius: SIZE / 2,
          background: buttonBg,
          border: '1px solid rgba(255,255,255,0.14)',
          boxShadow: `0 8px 32px ${shadowColor}, 0 2px 8px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.16)`,
          cursor: isConnected ? 'pointer' : 'not-allowed',
          color: '#fff',
          opacity: isConnected ? 1 : 0.45,
          transition: 'background 0.25s, box-shadow 0.25s, opacity 0.2s',
        }}
      >
        <AnimatePresence mode="wait">
          <motion.span
            key={genieState ?? 'default'}
            initial={{ opacity: 0, scale: 0.6, rotate: -12 }}
            animate={{ opacity: 1, scale: 1, rotate: 0 }}
            exit={{ opacity: 0, scale: 0.6, rotate: 12 }}
            transition={{ duration: 0.16 }}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            {iconEl}
          </motion.span>
        </AnimatePresence>
      </motion.button>

      {/* State label */}
      <AnimatePresence>
        {(isActive || isListening) && (
          <motion.span
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="text-xs font-semibold tracking-widest uppercase"
            style={{
              color: isActive ? '#f87171' : '#22d3ee',
              letterSpacing: '0.12em',
            }}
          >
            {isActive ? 'tap to stop' : 'listening…'}
          </motion.span>
        )}
      </AnimatePresence>

      {/* Connection hint */}
      {!isConnected && (
        <motion.span
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-xs font-medium"
          style={{ color: '#f87171', letterSpacing: '0.08em' }}
        >
          connecting…
        </motion.span>
      )}
    </div>
  );
}
