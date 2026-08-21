import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../store/appStore';

export default function MicrophoneButton({ size = 40 }) {
  const toggleListening = useAppStore((s) => s.toggleListening);
  const genieState = useAppStore((s) => s.genieState);
  const amplitude = useAppStore((s) => s.amplitude);
  const wsStatus = useAppStore((s) => s.wsStatus);

  const isConnected = wsStatus === 'authed' || wsStatus === 'connected';

  const isActive = ['thinking', 'executing', 'transcribing', 'speaking'].includes(genieState);
  const isListening = ['listening', 'follow_up_listening', 'waking'].includes(genieState);

  const handleClick = () => {
    if (!isConnected) return;
    if (toggleListening) {
      toggleListening();
    } else {
      const ws = useAppStore.getState().ws;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'manual_wake' }));
      }
    }
  };

  const buttonStyle = !isConnected
    ? 'bg-zinc-800 text-zinc-500 border-zinc-700 cursor-not-allowed'
    : isActive
    ? 'bg-gradient-to-r from-rose-500 to-red-600 text-white shadow-[0_0_20px_rgba(244,63,94,0.5)] border-rose-400/50'
    : isListening
    ? 'bg-gradient-to-r from-cyan-400 to-blue-500 text-white shadow-[0_0_25px_rgba(34,211,238,0.6)] border-cyan-300'
    : 'bg-gradient-to-r from-indigo-500 via-purple-500 to-cyan-500 text-white hover:shadow-[0_0_20px_rgba(129,140,248,0.4)] border-white/20';

  return (
    <div className="relative flex items-center justify-center">
      {/* Listening Pulse Waves */}
      <AnimatePresence>
        {isListening && (
          <>
            <motion.div
              initial={{ scale: 1, opacity: 0.8 }}
              animate={{ scale: 1.8 + amplitude * 0.5, opacity: 0 }}
              transition={{ repeat: Infinity, duration: 1.4, ease: 'easeOut' }}
              className="absolute inset-0 rounded-full bg-cyan-400/30 pointer-events-none"
            />
            <motion.div
              initial={{ scale: 1, opacity: 0.6 }}
              animate={{ scale: 2.2 + amplitude * 0.8, opacity: 0 }}
              transition={{ repeat: Infinity, duration: 1.8, delay: 0.4, ease: 'easeOut' }}
              className="absolute inset-0 rounded-full bg-blue-500/20 pointer-events-none"
            />
          </>
        )}
      </AnimatePresence>

      <motion.button
        type="button"
        onClick={handleClick}
        disabled={!isConnected}
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.92 }}
        className={`relative flex items-center justify-center rounded-xl border transition-all duration-200 ${buttonStyle}`}
        style={{ width: size, height: size }}
        title={!isConnected ? 'Offline' : isActive ? 'Stop Action' : isListening ? 'Listening… (click to finish)' : 'Click or say "Hey Genie"'}
      >
        {isActive ? (
          <span className="w-3.5 h-3.5 rounded-sm bg-white" />
        ) : isListening ? (
          <motion.div
            animate={{ scale: [1, 1.25, 1] }}
            transition={{ repeat: Infinity, duration: 0.8 }}
            className="flex items-center gap-0.5"
          >
            <span className="w-1 h-3.5 bg-white rounded-full animate-bounce" />
            <span className="w-1 h-5 bg-white rounded-full animate-bounce delay-75" />
            <span className="w-1 h-3 bg-white rounded-full animate-bounce delay-150" />
          </motion.div>
        ) : (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        )}
      </motion.button>
    </div>
  );
}
