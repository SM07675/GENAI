import React from 'react';
import { motion } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import { useTaskStore } from '../../store/taskStore';
import {
  EyeIcon,
  CameraIcon,
  ChatIcon,
  SunIcon,
  MoonIcon,
  SparklesIcon,
} from '../UI/Icons';

export interface DynamicIslandProps {
  onTriggerQuickLook: () => void;
  onToggleCamera: () => void;
  isCameraOpen: boolean;
  onToggleChat: () => void;
  isChatOpen: boolean;
  onOpenCommandBar: () => void;
  isSkyTheme: boolean;
  onToggleTheme: () => void;
}

export const DynamicIsland: React.FC<DynamicIslandProps> = ({
  onTriggerQuickLook,
  onToggleCamera,
  isCameraOpen,
  onToggleChat,
  isChatOpen,
  onOpenCommandBar,
  isSkyTheme,
  onToggleTheme,
}) => {
  const wsStatus = useAppStore((s) => s.wsStatus);
  const genieState = useAppStore((s) => s.genieState);
  const amplitude = useAppStore((s) => s.amplitude);
  const activeTask = useTaskStore((s) => s.activeTask);

  const isConnected = wsStatus === 'authed' || wsStatus === 'connected';

  const stateLabels: Record<string, { label: string; color: string; border: string }> = {
    idle: { label: 'Ready', color: 'text-zinc-300', border: 'border-zinc-700/60' },
    listening: { label: 'Listening Mode', color: 'text-cyan-300 font-bold', border: 'border-cyan-400/60' },
    follow_up_listening: { label: 'Listening Mode', color: 'text-cyan-300 font-bold', border: 'border-cyan-400/60' },
    waking: { label: 'Waking up…', color: 'text-purple-300 font-bold', border: 'border-purple-400/60' },
    transcribing: { label: 'Processing Voice…', color: 'text-amber-300 font-bold', border: 'border-amber-400/60' },
    thinking: { label: 'Thinking Mode', color: 'text-purple-300 font-bold', border: 'border-purple-400/60' },
    searching: { label: 'Search Mode', color: 'text-sky-300 font-bold', border: 'border-sky-400/60' },
    planning: { label: 'Planning Mode', color: 'text-indigo-300 font-bold', border: 'border-indigo-400/60' },
    executing: { label: 'Execution Mode', color: 'text-emerald-300 font-bold', border: 'border-emerald-400/60' },
    speaking: { label: 'Speaking Mode', color: 'text-cyan-300 font-bold', border: 'border-cyan-400/60' },
    error: { label: 'Attention Needed', color: 'text-rose-300 font-bold', border: 'border-rose-400/60' },
    sleeping: { label: 'Standby ("Hey Genie")', color: 'text-zinc-400', border: 'border-zinc-800' },
  };

  const currentInfo = stateLabels[genieState] || stateLabels.idle;

  return (
    <header className="w-full max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-4 select-none">
      {/* Left: Brand & Status Pill */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-zinc-950/80 border border-white/10 backdrop-blur-2xl shadow-lg">
          <span
            className={`w-2 h-2 rounded-full ${
              isConnected
                ? 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.8)]'
                : 'bg-amber-400 animate-pulse'
            }`}
          />
          <span className="font-mono text-[11px] font-bold tracking-wider uppercase text-zinc-200">
            Genie OS
          </span>
          <span className="text-zinc-600 text-xs">•</span>
          <span className={`text-[11px] font-mono ${currentInfo.color}`}>
            {currentInfo.label}
          </span>
          {activeTask && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
              ⚡ {activeTask.status}
            </span>
          )}
        </div>
      </div>

      {/* Center: Live Waveform Visualizer or Mission Summary */}
      <div className="hidden md:flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-zinc-950/60 border border-white/5 backdrop-blur-xl">
        {genieState === 'speaking' || genieState === 'listening' ? (
          <div className="flex items-center gap-1 h-4">
            {Array.from({ length: 9 }).map((_, i) => (
              <motion.span
                key={i}
                animate={{
                  scaleY: [
                    0.2,
                    0.4 + Math.sin(i * 0.8 + Date.now() * 0.01) * 0.6 + amplitude * 1.5,
                    0.2,
                  ],
                }}
                transition={{ duration: 0.35, repeat: Infinity, ease: 'easeInOut', delay: i * 0.04 }}
                className="w-1 bg-gradient-to-t from-cyan-400 to-indigo-400 rounded-full h-full"
              />
            ))}
          </div>
        ) : (
          <span className="text-[11px] font-mono text-zinc-400">
            {activeTask ? `Mission: ${activeTask.goal.objective.slice(0, 40)}...` : 'Spatial AI Companion'}
          </span>
        )}
      </div>

      {/* Right: Quick Action Capsule */}
      <div className="flex items-center gap-2">
        <IconButton
          icon={<EyeIcon size={14} />}
          onClick={onTriggerQuickLook}
          title="Quick Look (Ctrl+Shift+G)"
        />
        <IconButton
          icon={<CameraIcon size={14} />}
          onClick={onToggleCamera}
          active={isCameraOpen}
          title="Camera Vision Stream"
        />
        <IconButton
          icon={<ChatIcon size={14} />}
          onClick={onToggleChat}
          active={isChatOpen}
          title="Open Dialogue Feed"
        />
        <IconButton
          icon={isSkyTheme ? <MoonIcon size={14} /> : <SunIcon size={14} />}
          onClick={onToggleTheme}
          title="Toggle Visual Theme"
        />

        {/* Global Command Launcher Button */}
        <button
          type="button"
          onClick={onOpenCommandBar}
          className="px-3.5 py-1.5 rounded-xl text-xs font-mono bg-gradient-to-r from-white/10 to-white/5 hover:from-white/15 hover:to-white/10 border border-white/10 hover:border-cyan-500/40 text-zinc-200 hover:text-cyan-300 transition-all flex items-center gap-2 shadow-lg group"
        >
          <span className="text-cyan-400 font-bold">⌘K</span>
          <span className="text-[11px] text-zinc-400 group-hover:text-zinc-200">Launcher</span>
        </button>
      </div>
    </header>
  );
};

function IconButton({
  icon,
  onClick,
  active = false,
  title,
}: {
  icon: React.ReactNode;
  onClick: () => void;
  active?: boolean;
  title: string;
}) {
  return (
    <motion.button
      type="button"
      whileHover={{ scale: 1.08 }}
      whileTap={{ scale: 0.92 }}
      onClick={onClick}
      className={`p-2 rounded-xl text-xs flex items-center justify-center transition-all duration-200 ${
        active
          ? 'bg-cyan-500/25 text-cyan-300 border border-cyan-400/50 shadow-[0_0_12px_rgba(6,182,212,0.35)]'
          : 'text-zinc-400 hover:text-white bg-zinc-950/60 hover:bg-zinc-900 border border-white/5 hover:border-white/15'
      }`}
      title={title}
      aria-label={title}
    >
      {icon}
    </motion.button>
  );
}
