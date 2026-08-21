/**
 * HomeView.tsx — Central Spatial Stage for Genie AI OS.
 *
 * Implements a world-class assistant stage with:
 * 1. Living Holographic AI Core Orb & Dynamic Aura
 * 2. Holographic Quick Action Pills
 * 3. macOS / iOS Dynamic Stacked Stage Deck (Missions, Dialogue, Perception, Memory)
 */
import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GenieCoreOrb } from '../GenieCoreOrb';
import { useAppStore } from '../../store/appStore';
import { useCompanionStore } from '../../store/companionStore';
import { StackStage } from './StackStage';
import {
  SparklesIcon,
  BrainIcon,
  ChatIcon,
  EyeIcon,
  CameraIcon,
  ProjectsIcon,
} from '../UI/Icons';

interface HomeViewProps {
  onNavigate: (page: string) => void;
  genieState: string;
  onToggleCompanion: () => void;
  onQuickLook: () => void;
  onOpenCamera: () => void;
  onOpenChat: () => void;
  onOpenWorkspace: (taskId?: string) => void;
}

export default function HomeView({
  onNavigate,
  genieState,
  onToggleCompanion,
  onQuickLook,
  onOpenCamera,
  onOpenChat,
  onOpenWorkspace,
}: HomeViewProps) {
  const companion = useCompanionStore();
  const liveTranscript = useAppStore((s) => s.liveTranscript);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  return (
    <div className="h-full overflow-y-auto custom-scrollbar px-6 py-2 space-y-5 max-w-5xl mx-auto flex flex-col items-center select-none">
      {/* ── 1. Hero AI Core & Dynamic Aura ── */}
      <motion.div
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.45, ease: 'easeOut' }}
        className="flex flex-col items-center text-center space-y-2 pt-1 relative"
      >
        <div className="relative group cursor-pointer">
          <GenieCoreOrb state={genieState} size={170} />
          {/* Subtle Pedestal Reflection Glow */}
          <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 w-32 h-6 bg-gradient-to-r from-cyan-500/20 via-purple-500/20 to-indigo-500/20 blur-xl rounded-full pointer-events-none" />
        </div>

        {/* Dynamic Mode Badge */}
        <div className="flex items-center justify-center pt-1">
          <motion.div
            key={genieState}
            initial={{ opacity: 0, scale: 0.9, y: 3 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className={`px-3.5 py-1 rounded-full text-xs font-mono font-semibold flex items-center gap-2 border backdrop-blur-xl shadow-lg transition-all ${
              genieState === 'listening' || genieState === 'follow_up_listening'
                ? 'bg-cyan-950/80 border-cyan-400/60 text-cyan-300 shadow-[0_0_20px_rgba(6,182,212,0.4)]'
                : genieState === 'thinking'
                ? 'bg-purple-950/80 border-purple-400/60 text-purple-300 shadow-[0_0_20px_rgba(168,85,247,0.4)]'
                : genieState === 'searching'
                ? 'bg-sky-950/80 border-sky-400/60 text-sky-300 shadow-[0_0_20px_rgba(14,165,233,0.4)]'
                : genieState === 'executing'
                ? 'bg-emerald-950/80 border-emerald-400/60 text-emerald-300 shadow-[0_0_20px_rgba(16,185,129,0.4)]'
                : genieState === 'speaking'
                ? 'bg-blue-950/80 border-blue-400/60 text-blue-300 shadow-[0_0_20px_rgba(59,130,246,0.4)]'
                : genieState === 'transcribing'
                ? 'bg-amber-950/80 border-amber-400/60 text-amber-300 shadow-[0_0_20px_rgba(245,158,11,0.4)]'
                : 'bg-zinc-950/60 border-white/10 text-zinc-400'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${
              ['listening', 'follow_up_listening', 'thinking', 'searching', 'executing', 'speaking', 'transcribing'].includes(genieState)
                ? 'animate-ping bg-current'
                : 'bg-emerald-400'
            }`} />
            <span className="uppercase tracking-wider text-[10px] font-bold">
              {genieState === 'listening' || genieState === 'follow_up_listening'
                ? '🎙️ Listening Mode'
                : genieState === 'thinking'
                ? '🧠 Thinking Mode'
                : genieState === 'searching'
                ? '🔍 Search Mode'
                : genieState === 'executing'
                ? '⚙️ Execution Mode'
                : genieState === 'speaking'
                ? '🔊 Speaking Mode'
                : genieState === 'transcribing'
                ? '📝 Transcribing Voice'
                : '✨ Standby • Ready'}
            </span>
          </motion.div>
        </div>

        {/* Dynamic Title / Live Subtitle */}
        <div className="space-y-1 max-w-lg mx-auto">
          <AnimatePresence mode="wait">
            {liveTranscript ? (
              <motion.div
                key="transcript"
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                className="px-4 py-1.5 rounded-full bg-zinc-950/80 border border-cyan-500/30 text-cyan-300 font-mono text-xs shadow-lg inline-block"
              >
                "{liveTranscript}"
              </motion.div>
            ) : (
              <motion.div
                key="greeting"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <h1 className="text-xl md:text-2xl font-bold tracking-tight bg-gradient-to-r from-white via-zinc-200 to-zinc-400 bg-clip-text text-transparent">
                  {greeting}, ready for your next mission.
                </h1>
                <p className="text-[11px] text-zinc-400 leading-relaxed font-medium">
                  Autonomous Operating System • Multimodal Intelligence • Persistent Memory
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>

      {/* ── 2. Holographic Quick Action Pills ── */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.3 }}
        className="flex items-center justify-center gap-2 flex-wrap w-full"
      >
        <ActionButton
          icon={<span className="text-cyan-400 font-bold">⚡</span>}
          label="Missions & Tasks"
          onClick={() => onNavigate('tasks')}
          highlight
        />
        <ActionButton
          icon={<SparklesIcon size={13} />}
          label={`Companion: ${companion.mode}`}
          active={companion.mode === 'active'}
          onClick={onToggleCompanion}
        />
        <ActionButton icon={<EyeIcon size={13} />} label="Quick Look" onClick={onQuickLook} />
        <ActionButton icon={<CameraIcon size={13} />} label="Vision Cam" onClick={onOpenCamera} />
        <ActionButton icon={<ChatIcon size={13} />} label="Dialogue" onClick={onOpenChat} />
        <ActionButton icon={<BrainIcon size={13} />} label="Memory" onClick={() => onNavigate('memory')} />
        <ActionButton icon={<ProjectsIcon size={13} />} label="Projects" onClick={() => onNavigate('projects')} />
      </motion.div>

      {/* ── 3. macOS / iOS Dynamic Stack Stage Deck ── */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15, duration: 0.4 }}
        className="w-full"
      >
        <StackStage
          onOpenWorkspace={onOpenWorkspace}
          onOpenChat={onOpenChat}
          onNavigate={onNavigate}
          onTriggerQuickLook={onQuickLook}
        />
      </motion.div>
    </div>
  );
}

function ActionButton({
  icon,
  label,
  onClick,
  active = false,
  highlight = false,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  active?: boolean;
  highlight?: boolean;
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileHover={{ scale: 1.06 }}
      whileTap={{ scale: 0.94 }}
      className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all duration-200 border shadow-sm ${
        active
          ? 'bg-gradient-to-r from-cyan-500/25 to-indigo-500/25 text-cyan-300 border-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.3)]'
          : highlight
          ? 'bg-gradient-to-r from-cyan-950/60 to-indigo-950/60 text-cyan-200 border-cyan-500/40 hover:border-cyan-400'
          : 'bg-zinc-900/60 text-zinc-300 border-white/10 hover:bg-zinc-800/80 hover:border-white/20 hover:text-white'
      }`}
    >
      {icon}
      <span>{label}</span>
    </motion.button>
  );
}
