import { motion } from 'framer-motion';
import { AssistantState } from '../../types';
import { VoiceWave } from './VoiceWave';

interface MicrophoneButtonProps {
  state: AssistantState;
  onClick: () => void;
  audioLevel?: number;
}

export function MicrophoneButton({ state, onClick, audioLevel = 0.5 }: MicrophoneButtonProps) {
  // Glow / Color configuration for each state
  const getStateStyles = () => {
    switch (state) {
      case 'listening':
        return {
          glow: 'rgba(6, 182, 212, 0.6)',
          ring: 'border-cyan-400',
          bg: 'from-cyan-600/90 to-blue-600/90',
          iconColor: 'text-cyan-100',
          label: 'Listening...'
        };
      case 'recording':
        return {
          glow: 'rgba(239, 68, 68, 0.65)',
          ring: 'border-red-500',
          bg: 'from-red-600/90 to-rose-700/90',
          iconColor: 'text-red-100',
          label: 'Recording'
        };
      case 'processing':
        return {
          glow: 'rgba(168, 85, 247, 0.65)',
          ring: 'border-purple-400',
          bg: 'from-purple-600/90 to-indigo-600/90',
          iconColor: 'text-purple-100',
          label: 'Processing...'
        };
      case 'speaking':
        return {
          glow: 'rgba(59, 130, 246, 0.7)',
          ring: 'border-blue-400',
          bg: 'from-blue-600/90 to-cyan-500/90',
          iconColor: 'text-blue-100',
          label: 'Speaking'
        };
      case 'muted':
        return {
          glow: 'rgba(100, 116, 139, 0.3)',
          ring: 'border-slate-500/40',
          bg: 'from-slate-800/90 to-slate-900/90',
          iconColor: 'text-slate-400',
          label: 'Muted'
        };
      case 'idle':
      default:
        return {
          glow: 'rgba(56, 189, 248, 0.35)',
          ring: 'border-sky-400/50',
          bg: 'from-slate-900/95 via-sky-950/80 to-slate-900/95',
          iconColor: 'text-sky-300',
          label: 'Genie'
        };
    }
  };

  const styleConfig = getStateStyles();

  return (
    <div className="relative flex flex-col items-center justify-center">
      {/* Voice Wave visualizer above mic when speaking or recording */}
      <VoiceWave isActive={state === 'speaking' || state === 'recording'} audioLevel={audioLevel} />

      {/* Expanding Ripple Rings for active listening / recording / processing */}
      {(state === 'listening' || state === 'recording' || state === 'speaking') && (
        <motion.div
          className={`absolute rounded-full border ${styleConfig.ring}`}
          style={{ width: 90, height: 90 }}
          animate={{ scale: [1, 1.5, 1.8], opacity: [0.8, 0.4, 0] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeOut' }}
        />
      )}

      {/* Outer Glow Halo */}
      <motion.div
        className="absolute rounded-full pointer-events-none blur-xl"
        style={{
          width: 80,
          height: 80,
          backgroundColor: styleConfig.glow
        }}
        animate={{
          scale: state === 'speaking' || state === 'recording' ? [1.1, 1.35, 1.1] : [1, 1.15, 1]
        }}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Main Large Circular Microphone Button */}
      <motion.button
        onClick={onClick}
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.94 }}
        className={`relative z-20 flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-b ${styleConfig.bg} border-2 ${styleConfig.ring} shadow-2xl backdrop-blur-xl transition-colors duration-300 cursor-pointer group`}
        title={`Microphone state: ${state}`}
      >
        {/* Processing Spinner Overlay */}
        {state === 'processing' && (
          <motion.div
            className="absolute inset-0 rounded-full border-2 border-purple-400/20 border-t-purple-300"
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          />
        )}

        {/* Dynamic Icon */}
        <div className={`transition-transform duration-300 group-hover:scale-110 ${styleConfig.iconColor}`}>
          {state === 'muted' ? (
            // Mic Off SVG Icon
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              <line x1="1" y1="1" x2="23" y2="23" stroke="currentColor" strokeWidth={2} />
            </svg>
          ) : (
            // Mic SVG Icon
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 10v2a7 7 0 01-14 0v-2m7 9v4m-4 0h8" />
            </svg>
          )}
        </div>
      </motion.button>

      {/* Subtitle Badge */}
      <span className="mt-2 text-xs font-medium tracking-widest text-cyan-200/70 uppercase">
        {styleConfig.label}
      </span>
    </div>
  );
}
