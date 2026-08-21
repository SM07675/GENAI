import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export interface ToolCallCardProps {
  toolName: string;
  args?: any;
  result?: any;
  durationMs?: number | null;
  status?: 'running' | 'ok' | 'error';
}

export const ToolCallCard: React.FC<ToolCallCardProps> = ({
  toolName,
  args,
  result,
  durationMs,
  status = 'ok',
}) => {
  const [expanded, setExpanded] = useState(false);

  const statusColor = {
    running: 'text-cyan-400 border-cyan-500/30 bg-cyan-950/20',
    ok: 'text-emerald-400 border-emerald-500/30 bg-emerald-950/20',
    error: 'text-rose-400 border-rose-500/30 bg-rose-950/20',
  }[status];

  return (
    <div className="rounded-lg border border-white/10 bg-black/40 backdrop-blur-md overflow-hidden text-xs my-1.5 transition-all hover:border-white/20">
      <div
        className="flex items-center justify-between px-3 py-2 cursor-pointer select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span className="font-mono font-semibold text-cyan-300">⚙ {toolName}</span>
          {durationMs !== undefined && durationMs !== null && (
            <span className="text-[10px] text-zinc-400 font-mono">({durationMs}ms)</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-mono font-medium border ${statusColor}`}>
            {status}
          </span>
          <span className="text-zinc-400 text-[10px]">{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-white/5 px-3 py-2 bg-black/60 space-y-2"
          >
            {args && (
              <div>
                <div className="text-[10px] text-zinc-400 font-mono mb-1 uppercase tracking-wider">Arguments</div>
                <pre className="p-2 rounded bg-zinc-950/80 text-zinc-300 font-mono text-[11px] overflow-x-auto custom-scrollbar border border-white/5">
                  {typeof args === 'object' ? JSON.stringify(args, null, 2) : String(args)}
                </pre>
              </div>
            )}
            {result && (
              <div>
                <div className="text-[10px] text-zinc-400 font-mono mb-1 uppercase tracking-wider">Result</div>
                <pre className="p-2 rounded bg-zinc-950/80 text-emerald-300 font-mono text-[11px] overflow-x-auto custom-scrollbar border border-white/5">
                  {typeof result === 'object' ? JSON.stringify(result, null, 2) : String(result)}
                </pre>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
