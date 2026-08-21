import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import MicrophoneButton from '../MicrophoneButton';
import { SendIcon, SparklesIcon, CameraIcon } from '../UI/Icons';

export interface FloatingDockProps {
  onSendGoal: (goal: string) => void;
  onSendText: (text: string) => void;
  onTriggerCamera: () => void;
  isBackendConnected: boolean;
}

export type AssistantMode = 'goal' | 'chat' | 'research' | 'code';

export const FloatingDock: React.FC<FloatingDockProps> = ({
  onSendGoal,
  onSendText,
  onTriggerCamera,
  isBackendConnected,
}) => {
  const [input, setInput] = useState('');
  const [mode, setMode] = useState<AssistantMode>('goal');
  const [isModeMenuOpen, setIsModeMenuOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const modeConfigs: Record<AssistantMode, { label: string; icon: string; color: string; placeholder: string }> = {
    goal: {
      label: 'Autonomous Mission',
      icon: '⚡',
      color: 'text-cyan-300 border-cyan-500/40 bg-cyan-950/40',
      placeholder: 'Describe a multi-step mission to execute autonomously...',
    },
    chat: {
      label: 'Direct Dialogue',
      icon: '💬',
      color: 'text-indigo-300 border-indigo-500/40 bg-indigo-950/40',
      placeholder: 'Ask Genie a question or chat...',
    },
    research: {
      label: 'Deep Research',
      icon: '🔍',
      color: 'text-sky-300 border-sky-500/40 bg-sky-950/40',
      placeholder: 'Topic to research, synthesize, and compare...',
    },
    code: {
      label: 'Coding Agent',
      icon: '💻',
      color: 'text-emerald-300 border-emerald-500/40 bg-emerald-950/40',
      placeholder: 'Code problem to analyze, debug, or implement...',
    },
  };

  const currentMode = modeConfigs[mode];

  const handleSend = () => {
    const clean = input.trim();
    if (!clean) return;

    if (mode === 'goal') {
      onSendGoal(clean);
    } else if (mode === 'research') {
      onSendGoal(`Research and prepare a summary for: ${clean}`);
    } else if (mode === 'code') {
      onSendGoal(`Code task: ${clean}`);
    } else {
      onSendText(clean);
    }

    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="relative w-full max-w-3xl mx-auto px-4 select-none">
      {/* Mode Selection Popover Menu */}
      <AnimatePresence>
        {isModeMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="absolute bottom-16 left-6 z-50 p-2 rounded-2xl bg-zinc-950/95 border border-white/15 backdrop-blur-2xl shadow-[0_20px_50px_rgba(0,0,0,0.8)] space-y-1 w-64"
          >
            <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 px-3 py-1.5 font-semibold">
              Select Operating Mode
            </div>
            {(Object.keys(modeConfigs) as AssistantMode[]).map((m) => {
              const cfg = modeConfigs[m];
              const isSelected = mode === m;
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => {
                    setMode(m);
                    setIsModeMenuOpen(false);
                    inputRef.current?.focus();
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                    isSelected
                      ? 'bg-gradient-to-r from-cyan-500/20 to-indigo-500/20 text-cyan-300 border border-cyan-500/30'
                      : 'text-zinc-300 hover:bg-white/5 hover:text-white'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span>{cfg.icon}</span>
                    <span>{cfg.label}</span>
                  </div>
                  {isSelected && <span className="text-cyan-400 font-bold text-xs">✓</span>}
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Floating Capsule Dock */}
      <div className="glass-dock rounded-2xl p-2 flex items-center gap-2.5 shadow-2xl">
        {/* Voice Reactive Microphone Button */}
        <MicrophoneButton size={38} />

        {/* Mode Selector Pill Button */}
        <button
          type="button"
          onClick={() => setIsModeMenuOpen(!isModeMenuOpen)}
          className={`px-3 py-1.5 rounded-xl text-xs font-mono font-semibold border flex items-center gap-1.5 transition-all shadow-sm ${currentMode.color}`}
          title="Change Assistant Mode"
        >
          <span>{currentMode.icon}</span>
          <span className="hidden sm:inline">{currentMode.label}</span>
          <span className="text-[9px] opacity-70">▼</span>
        </button>

        {/* Natural Language Goal / Message Input */}
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={currentMode.placeholder}
          className="flex-1 bg-transparent outline-none border-none text-sm text-white placeholder-zinc-500 px-1 font-medium"
        />

        {/* Camera / Vision Snapshot Trigger */}
        <button
          type="button"
          onClick={onTriggerCamera}
          className="p-2 rounded-xl text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent hover:border-white/10 transition-all"
          title="Attach Screen or Camera Frame"
        >
          <CameraIcon size={16} />
        </button>

        {/* Radiant Gradient Run Button */}
        <motion.button
          type="button"
          onClick={handleSend}
          disabled={!input.trim() || !isBackendConnected}
          whileHover={input.trim() ? { scale: 1.05 } : {}}
          whileTap={input.trim() ? { scale: 0.95 } : {}}
          className="px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 bg-gradient-to-r from-cyan-500 via-indigo-500 to-purple-600 text-white disabled:opacity-30 disabled:cursor-not-allowed shadow-[0_0_20px_rgba(0,242,254,0.3)] transition-all font-mono tracking-wide"
        >
          <SendIcon size={13} />
          <span>Execute</span>
        </motion.button>
      </div>
    </div>
  );
};
