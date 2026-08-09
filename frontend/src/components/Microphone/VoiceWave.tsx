import { motion } from 'framer-motion';

interface VoiceWaveProps {
  isActive: boolean;
  audioLevel?: number;
  barCount?: number;
}

export function VoiceWave({ isActive, audioLevel = 0.5, barCount = 7 }: VoiceWaveProps) {
  if (!isActive) return null;

  const bars = Array.from({ length: barCount });

  return (
    <div className="absolute -top-14 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-4 py-2 rounded-full bg-slate-950/70 border border-cyan-500/30 backdrop-blur-md shadow-lg shadow-cyan-500/20 pointer-events-none">
      {bars.map((_, i) => {
        const factor = 1 - Math.abs(i - (barCount - 1) / 2) * 0.2;
        return (
          <motion.div
            key={i}
            className="w-1 bg-gradient-to-t from-cyan-500 via-blue-400 to-cyan-200 rounded-full"
            animate={{
              height: isActive
                ? [
                    `${Math.max(8, factor * 28 * audioLevel)}px`,
                    `${Math.max(12, factor * 42 * (audioLevel + 0.3))}px`,
                    `${Math.max(6, factor * 20 * audioLevel)}px`
                  ]
                : '8px'
            }}
            transition={{
              duration: 0.4 + i * 0.05,
              repeat: Infinity,
              repeatType: 'reverse',
              ease: 'easeInOut'
            }}
          />
        );
      })}
    </div>
  );
}
