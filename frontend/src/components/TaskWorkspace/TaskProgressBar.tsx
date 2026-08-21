import React from 'react';
import { motion } from 'framer-motion';

export interface TaskProgressBarProps {
  progress: number; // 0.0 to 1.0
  status: string;
  totalSteps?: number;
  completedSteps?: number;
}

export const TaskProgressBar: React.FC<TaskProgressBarProps> = ({
  progress,
  status,
  totalSteps,
  completedSteps,
}) => {
  const pct = Math.min(100, Math.max(0, Math.round((progress || 0) * 100)));

  const isComplete = status === 'completed';
  const isFailed = status === 'failed';
  const isRunning = status === 'running' || status === 'planning' || status === 'replanning';

  const barColor = isFailed
    ? 'bg-rose-500 shadow-[0_0_12px_rgba(244,63,94,0.5)]'
    : isComplete
    ? 'bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.5)]'
    : 'bg-gradient-to-r from-cyan-500 via-indigo-500 to-purple-500 shadow-[0_0_15px_rgba(56,189,248,0.5)]';

  return (
    <div className="w-full space-y-1.5">
      <div className="flex items-center justify-between text-xs font-mono">
        <div className="flex items-center gap-2">
          <span className="text-zinc-400">Progress</span>
          {totalSteps !== undefined && completedSteps !== undefined && (
            <span className="text-zinc-500">
              ({completedSteps}/{totalSteps} steps)
            </span>
          )}
        </div>
        <span className="font-semibold text-zinc-200">{pct}%</span>
      </div>

      <div className="h-2 w-full bg-zinc-900/80 rounded-full overflow-hidden border border-white/5 p-[1px]">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
          className={`h-full rounded-full transition-all ${barColor} ${isRunning ? 'animate-pulse' : ''}`}
        />
      </div>
    </div>
  );
};
