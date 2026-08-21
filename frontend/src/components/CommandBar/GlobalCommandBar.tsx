import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export interface GlobalCommandBarProps {
  isOpen: boolean;
  onClose: () => void;
  onSendGoal: (text: string) => void;
  onSendText: (text: string) => void;
  onStartVoice?: () => void;
}

const COMMAND_SUGGESTIONS = [
  { prefix: '/goal', label: 'Run autonomous goal', desc: 'Plan and execute a multi-step objective' },
  { prefix: '/research', label: 'Research topic', desc: 'Gather web sources, compare data, and synthesize a report' },
  { prefix: '/code', label: 'Coding mission', desc: 'Debug, analyze, write, or test software in workspace' },
  { prefix: '/file', label: 'File operations', desc: 'Organize, search, or convert files' },
  { prefix: '/memory', label: 'Recall from memory', desc: 'Query long-term memory and project facts' },
];

export const GlobalCommandBar: React.FC<GlobalCommandBarProps> = ({
  isOpen,
  onClose,
  onSendGoal,
  onSendText,
  onStartVoice,
}) => {
  const [input, setInput] = useState('');
  const [isGoalMode, setIsGoalMode] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = input.trim();
    if (!clean) return;

    if (clean.startsWith('/goal ')) {
      onSendGoal(clean.replace('/goal ', ''));
    } else if (clean.startsWith('/research ')) {
      onSendGoal(`Research: ${clean.replace('/research ', '')}`);
    } else if (clean.startsWith('/code ')) {
      onSendGoal(`Code task: ${clean.replace('/code ', '')}`);
    } else if (isGoalMode) {
      onSendGoal(clean);
    } else {
      onSendText(clean);
    }

    setInput('');
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4 bg-black/60 backdrop-blur-md">
          {/* Backdrop click */}
          <div className="absolute inset-0" onClick={onClose} />

          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="relative w-full max-w-2xl bg-zinc-950/90 border border-cyan-500/30 rounded-2xl shadow-[0_0_50px_rgba(6,182,212,0.2)] overflow-hidden backdrop-blur-2xl"
          >
            <form onSubmit={handleSubmit} className="flex items-center gap-3 px-4 py-3.5 border-b border-white/10">
              <span className="text-cyan-400 text-lg">✦</span>
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Give Genie a goal, command, or question... (e.g. 'Research quantum computing and prepare a summary')"
                className="flex-1 bg-transparent text-sm text-white placeholder-zinc-500 outline-none font-medium"
              />

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsGoalMode(!isGoalMode)}
                  className={`px-2 py-1 rounded text-[11px] font-mono transition-all border ${
                    isGoalMode
                      ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                      : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                  }`}
                  title="Toggle Autonomous Goal vs Direct Chat mode"
                >
                  {isGoalMode ? '⚡ Goal Mode' : '💬 Chat Mode'}
                </button>

                <button
                  type="submit"
                  disabled={!input.trim()}
                  className="px-3 py-1 rounded-lg text-xs font-semibold bg-gradient-to-r from-cyan-500 to-indigo-500 text-white disabled:opacity-30 transition-all shadow-md shadow-cyan-500/20"
                >
                  Run
                </button>
              </div>
            </form>

            {/* Suggestions */}
            <div className="p-3 bg-zinc-950/50 space-y-1">
              <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 px-2 py-1">
                Suggested Commands
              </div>
              {COMMAND_SUGGESTIONS.map((cmd) => (
                <div
                  key={cmd.prefix}
                  onClick={() => {
                    setInput(`${cmd.prefix} `);
                    inputRef.current?.focus();
                  }}
                  className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-white/5 cursor-pointer transition-all text-xs group"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-cyan-400 font-semibold">{cmd.prefix}</span>
                    <span className="text-zinc-300 font-medium">{cmd.label}</span>
                  </div>
                  <span className="text-zinc-500 text-[11px] group-hover:text-zinc-400">{cmd.desc}</span>
                </div>
              ))}
            </div>

            {/* Footer tips */}
            <div className="px-4 py-2 bg-black/40 border-t border-white/5 flex items-center justify-between text-[11px] text-zinc-500 font-mono">
              <div className="flex items-center gap-3">
                <span><kbd className="px-1 py-0.5 rounded bg-zinc-800 text-zinc-400">Esc</kbd> close</span>
                <span><kbd className="px-1 py-0.5 rounded bg-zinc-800 text-zinc-400">Enter</kbd> execute</span>
              </div>
              <span>Genie Autonomous Agent OS</span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
