import React from 'react';
import { motion } from 'framer-motion';

export interface StepStatusIndicatorProps {
  status: 'pending' | 'ready' | 'running' | 'completed' | 'failed' | 'skipped' | 'retrying' | 'cancelled';
  size?: number;
}

export const StepStatusIndicator: React.FC<StepStatusIndicatorProps> = ({ status, size = 20 }) => {
  switch (status) {
    case 'completed':
      return (
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="flex items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
          style={{ width: size, height: size }}
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </motion.div>
      );

    case 'running':
    case 'retrying':
      return (
        <div
          className="relative flex items-center justify-center rounded-full bg-cyan-500/20 text-cyan-400 border border-cyan-500/50"
          style={{ width: size, height: size }}
        >
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
            className="w-3 h-3 border-2 border-cyan-400 border-t-transparent rounded-full"
          />
          <span className="absolute w-full h-full rounded-full bg-cyan-400/20 animate-ping" />
        </div>
      );

    case 'failed':
      return (
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="flex items-center justify-center rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/40"
          style={{ width: size, height: size }}
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </motion.div>
      );

    case 'skipped':
      return (
        <div
          className="flex items-center justify-center rounded-full bg-zinc-500/20 text-zinc-400 border border-zinc-500/30 text-[10px]"
          style={{ width: size, height: size }}
        >
          —
        </div>
      );

    case 'ready':
      return (
        <div
          className="flex items-center justify-center rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/40"
          style={{ width: size, height: size }}
        >
          <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
        </div>
      );

    case 'pending':
    default:
      return (
        <div
          className="flex items-center justify-center rounded-full bg-zinc-800/80 text-zinc-500 border border-zinc-700/60"
          style={{ width: size, height: size }}
        >
          <div className="w-1.5 h-1.5 rounded-full bg-zinc-600" />
        </div>
      );
  }
};
