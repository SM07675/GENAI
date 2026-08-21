import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { TimelineEntry } from '../../store/taskStore';
import { AgentBadge } from '../AgentActivity/AgentBadge';

export interface ActivityTimelineProps {
  timeline: TimelineEntry[];
}

export const ActivityTimeline: React.FC<ActivityTimelineProps> = ({ timeline }) => {
  const [filter, setFilter] = useState<string | null>(null);

  if (!timeline || timeline.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center text-zinc-500 text-xs">
        <span>No activity recorded yet</span>
      </div>
    );
  }

  const entries = filter ? timeline.filter((e) => e.status === filter) : timeline;

  const statusIcons = {
    info: '•',
    success: '✓',
    warning: '⚠',
    error: '✕',
  };

  const statusColors = {
    info: 'text-cyan-400 bg-cyan-950/40 border-cyan-500/30',
    success: 'text-emerald-400 bg-emerald-950/40 border-emerald-500/30',
    warning: 'text-amber-400 bg-amber-950/40 border-amber-500/30',
    error: 'text-rose-400 bg-rose-950/40 border-rose-500/30',
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs font-mono uppercase tracking-wider text-zinc-400 font-semibold">
          Execution Timeline ({timeline.length})
        </span>
        <div className="flex items-center gap-1 text-[11px] font-mono">
          <button
            onClick={() => setFilter(null)}
            className={`px-2 py-0.5 rounded transition ${!filter ? 'bg-white/10 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            All
          </button>
          <button
            onClick={() => setFilter('error')}
            className={`px-2 py-0.5 rounded transition ${filter === 'error' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            Errors
          </button>
          <button
            onClick={() => setFilter('warning')}
            className={`px-2 py-0.5 rounded transition ${filter === 'warning' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            Warnings
          </button>
        </div>
      </div>

      <div className="relative pl-5 space-y-2.5 max-h-[420px] overflow-y-auto custom-scrollbar pr-1 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-[1px] before:bg-white/10">
        {entries.map((entry, idx) => {
          const colorClass = statusColors[entry.status] || statusColors.info;
          return (
            <motion.div
              key={entry.entry_id || idx}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className="relative rounded-lg border border-white/5 bg-zinc-950/60 p-2.5 backdrop-blur-md space-y-1 hover:border-white/15 transition-all text-xs"
            >
              {/* Timeline Pin */}
              <div
                className={`absolute -left-[17px] top-3 w-3 h-3 rounded-full flex items-center justify-center text-[8px] font-bold border ${colorClass}`}
              >
                {statusIcons[entry.status]}
              </div>

              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <AgentBadge agent={entry.agent} size="sm" />
                  <span className="font-semibold text-zinc-200">{entry.action}</span>
                </div>
                <div className="flex items-center gap-1.5 font-mono text-[10px] text-zinc-400">
                  {entry.duration_ms && <span>{entry.duration_ms}ms</span>}
                  <span>{entry.timestamp}</span>
                </div>
              </div>

              {entry.detail && (
                <p className="text-zinc-400 pl-1 text-[11px] leading-relaxed break-words whitespace-pre-wrap">
                  {entry.detail}
                </p>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
