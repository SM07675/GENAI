import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { useAppStore } from '../store/appStore';

interface GenieCoreOrbProps {
  state: string; // idle, listening, processing, speaking, error
  size?: number; // default 260
}

export function GenieCoreOrb({ state = 'idle', size = 260 }: GenieCoreOrbProps) {
  const amplitude = useAppStore((s) => s.amplitude);

  // Dynamic visual configurations based on assistant state
  const config = useMemo(() => {
    switch (state) {
      case 'listening':
      case 'waking':
        return {
          coreGradient: 'radial-gradient(circle, #06b6d4 0%, #10b981 50%, #047857 100%)',
          glowColor: 'rgba(6, 182, 212, 0.6)',
          ringColor: 'rgba(16, 185, 129, 0.4)',
          pulseDuration: 1.8,
          scale: [1, 1.08, 1],
          label: 'LISTENING',
        };
      case 'processing':
      case 'transcribing':
      case 'thinking':
        return {
          coreGradient: 'radial-gradient(circle, #8b5cf6 0%, #06b6d4 60%, #3b82f6 100%)',
          glowColor: 'rgba(139, 92, 246, 0.7)',
          ringColor: 'rgba(6, 182, 212, 0.5)',
          pulseDuration: 1.2,
          scale: [1, 1.05, 1],
          label: 'THINKING',
        };
      case 'speaking':
        return {
          coreGradient: 'radial-gradient(circle, #ec4899 0%, #8b5cf6 50%, #6366f1 100%)',
          glowColor: 'rgba(236, 72, 153, 0.75)',
          ringColor: 'rgba(139, 92, 246, 0.5)',
          pulseDuration: 0.8,
          scale: [1, 1.1 + amplitude * 0.25, 1],
          label: 'SPEAKING',
        };
      case 'error':
        return {
          coreGradient: 'radial-gradient(circle, #ef4444 0%, #b91c1c 70%, #7f1d1d 100%)',
          glowColor: 'rgba(239, 68, 68, 0.7)',
          ringColor: 'rgba(239, 68, 68, 0.4)',
          pulseDuration: 0.6,
          scale: [1, 1.04, 1],
          label: 'ERROR',
        };
      case 'idle':
      default:
        return {
          coreGradient: 'radial-gradient(circle, #6366f1 0%, #3b82f6 50%, #1e1b4b 100%)',
          glowColor: 'rgba(99, 102, 241, 0.45)',
          ringColor: 'rgba(59, 130, 246, 0.25)',
          pulseDuration: 3.5,
          scale: [1, 1.04, 1],
          label: 'GENIE AI',
        };
    }
  }, [state, amplitude]);

  return (
    <div
      className="relative flex items-center justify-center select-none"
      style={{ width: size, height: size }}
    >
      {/* Outer ambient aura glow */}
      <motion.div
        animate={{
          scale: config.scale,
          opacity: [0.5, 0.8, 0.5],
        }}
        transition={{
          duration: config.pulseDuration,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        className="absolute inset-0 rounded-full blur-3xl pointer-events-none"
        style={{ background: config.glowColor }}
      />

      {/* Rotating outer orbital ring */}
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: state === 'processing' ? 6 : 20, repeat: Infinity, ease: 'linear' }}
        className="absolute inset-[-15%] rounded-full border border-dashed pointer-events-none"
        style={{ borderColor: config.ringColor }}
      />

      {/* Pulsing secondary orbital ring */}
      <motion.div
        animate={{
          rotate: -360,
          scale: [0.95, 1.05, 0.95],
        }}
        transition={{
          rotate: { duration: 25, repeat: Infinity, ease: 'linear' },
          scale: { duration: config.pulseDuration * 1.5, repeat: Infinity, ease: 'easeInOut' },
        }}
        className="absolute inset-[-30%] rounded-full border border-cyan-500/20 pointer-events-none"
      />

      {/* Main Liquid Core Glass Sphere */}
      <motion.div
        animate={{
          scale: config.scale,
        }}
        transition={{
          duration: config.pulseDuration,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        className="relative w-full h-full rounded-full shadow-2xl overflow-hidden flex items-center justify-center border border-white/20 backdrop-blur-xl"
        style={{
          background: config.coreGradient,
          boxShadow: `0 0 50px ${config.glowColor}, inset 0 0 30px rgba(255,255,255,0.3)`,
        }}
      >
        {/* Specular highlights for 3D depth effect (pure CSS, zero WebGL) */}
        <div className="absolute top-3 left-6 w-20 h-10 rounded-full bg-white/30 blur-md transform -rotate-45 pointer-events-none" />
        <div className="absolute bottom-4 right-8 w-14 h-8 rounded-full bg-cyan-300/20 blur-sm pointer-events-none" />

        {/* Audio reactive wave ripples during speech */}
        {state === 'speaking' && (
          <motion.div
            animate={{
              scale: [0.8, 1.4],
              opacity: [0.8, 0],
            }}
            transition={{
              duration: 1.0,
              repeat: Infinity,
              ease: 'easeOut',
            }}
            className="absolute inset-0 rounded-full border-2 border-white/40 pointer-events-none"
          />
        )}

        {/* Center state text badge */}
        <div className="relative z-10 text-center pointer-events-none">
          <span className="text-xs font-extrabold tracking-widest text-white/90 uppercase drop-shadow-md">
            {config.label}
          </span>
        </div>
      </motion.div>
    </div>
  );
}
