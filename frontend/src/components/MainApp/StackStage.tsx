/**
 * StackStage.tsx — macOS / iOS Dynamic Stacked Stage Manager.
 *
 * Implements a luxurious 3D-stacked card deck interface allowing users to
 * smoothly flip, expand, and interact with multiple live assistant streams:
 * 1. Active Missions (Autonomous Step DAG + Agent Logs)
 * 2. Dialogue & Conversation Stream
 * 3. Desktop & Vision Perception (System Gauges, Screen Awareness)
 * 4. Neural Memory Vault
 */
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import { useCompanionStore } from '../../store/companionStore';
import { useTaskStore, TaskState } from '../../store/taskStore';
import { AgentBadge } from '../AgentActivity/AgentBadge';
import { TaskProgressBar } from '../TaskWorkspace/TaskProgressBar';
import { StepStatusIndicator } from '../AgentActivity/StepStatusIndicator';
import {
  ChatIcon,
  SparklesIcon,
  BrainIcon,
  ProjectsIcon,
  EyeIcon,
  CameraIcon,
  TrashIcon,
} from '../UI/Icons';

export interface StackStageProps {
  onOpenWorkspace: (taskId?: string) => void;
  onOpenChat: () => void;
  onNavigate: (page: string) => void;
  onTriggerQuickLook: () => void;
}

type StackTab = 'mission' | 'dialogue' | 'perception' | 'memory';

export const StackStage: React.FC<StackStageProps> = ({
  onOpenWorkspace,
  onOpenChat,
  onNavigate,
  onTriggerQuickLook,
}) => {
  const [activeTab, setActiveTab] = useState<StackTab>('mission');
  const activeTask = useTaskStore((s) => s.activeTask);
  const tasks = useTaskStore((s) => s.tasks);
  const messages = useAppStore((s) => s.messages);
  const wsStatus = useAppStore((s) => s.wsStatus);
  const visionSupported = useAppStore((s) => s.visionSupported);
  const visionReason = useAppStore((s) => s.visionReason);
  const companion = useCompanionStore();

  const isConnected = wsStatus === 'authed' || wsStatus === 'connected';
  const recentMessages = messages.slice(-5).reverse();

  const tabs: { id: StackTab; label: string; icon: string; badge?: string | number }[] = [
    {
      id: 'mission',
      label: 'Autonomous Mission',
      icon: '⚡',
      badge: activeTask ? activeTask.status.toUpperCase() : tasks.length > 0 ? tasks.length : undefined,
    },
    {
      id: 'dialogue',
      label: 'Dialogue Stream',
      icon: '💬',
      badge: messages.length > 0 ? messages.length : undefined,
    },
    {
      id: 'perception',
      label: 'Desktop Intelligence',
      icon: '👁',
      badge: companion.mode === 'active' ? 'LIVE' : undefined,
    },
    {
      id: 'memory',
      label: 'Neural Memory',
      icon: '🧠',
    },
  ];

  return (
    <div className="w-full max-w-4xl mx-auto space-y-4">
      {/* ── Stack Segmented Pill Controller (macOS / iOS Style) ── */}
      <div className="flex items-center justify-center">
        <div className="flex items-center gap-1.5 p-1.5 rounded-2xl bg-zinc-950/70 border border-white/10 backdrop-blur-2xl shadow-xl">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`relative px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all duration-300 ${
                  isActive
                    ? 'text-white'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/5'
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="active-stack-pill"
                    className="absolute inset-0 rounded-xl bg-gradient-to-r from-cyan-500/25 via-indigo-500/25 to-purple-500/25 border border-cyan-400/40 shadow-[0_0_20px_rgba(6,182,212,0.25)]"
                    transition={{ type: 'spring', stiffness: 450, damping: 32 }}
                  />
                )}
                <span className="relative z-10 text-sm">{tab.icon}</span>
                <span className="relative z-10 font-medium">{tab.label}</span>
                {tab.badge && (
                  <span
                    className={`relative z-10 px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold ${
                      isActive ? 'bg-cyan-400 text-black' : 'bg-white/10 text-zinc-400'
                    }`}
                  >
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── 3D Dynamic Floating Glass Card Deck ── */}
      <div className="relative min-h-[260px]">
        <AnimatePresence mode="wait">
          {/* 1. MISSION STACK CARD */}
          {activeTab === 'mission' && (
            <motion.div
              key="mission-card"
              initial={{ opacity: 0, y: 15, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -15, scale: 0.98 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              className="w-full p-5 rounded-3xl border border-white/15 bg-gradient-to-br from-zinc-950/85 via-zinc-900/60 to-black/90 backdrop-blur-3xl shadow-[0_20px_60px_rgba(0,0,0,0.6),0_0_40px_rgba(6,182,212,0.12)] space-y-4"
            >
              {activeTask ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
                      <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-300">
                        {activeTask.status} • {activeTask.task_id}
                      </span>
                      {activeTask.active_agent && (
                        <AgentBadge agent={activeTask.active_agent} isActive size="sm" />
                      )}
                    </div>
                    <button
                      onClick={() => onOpenWorkspace(activeTask.task_id)}
                      className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30 transition-all flex items-center gap-1.5 shadow-sm"
                    >
                      <span>Full Workspace</span>
                      <span>→</span>
                    </button>
                  </div>

                  <h3 className="text-base font-semibold text-white tracking-tight leading-snug">
                    {activeTask.goal.objective}
                  </h3>

                  <TaskProgressBar
                    progress={activeTask.progress}
                    status={activeTask.status}
                    totalSteps={activeTask.plan?.steps?.length}
                    completedSteps={activeTask.plan?.steps?.filter((s) => s.status === 'completed').length}
                  />

                  {/* Live Step Previews */}
                  {activeTask.plan?.steps && activeTask.plan.steps.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 pt-1">
                      {activeTask.plan.steps.slice(0, 3).map((step, idx) => (
                        <div
                          key={step.step_id || idx}
                          className="p-2.5 rounded-xl bg-black/40 border border-white/5 flex items-center gap-2 text-xs"
                        >
                          <StepStatusIndicator status={step.status} size={18} />
                          <span className="text-zinc-300 truncate font-medium">{step.title}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : tasks.length > 0 ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono uppercase tracking-wider text-zinc-400 font-semibold">
                      Recent Mission History
                    </span>
                    <button
                      onClick={() => onNavigate('tasks')}
                      className="text-xs font-mono text-cyan-400 hover:text-cyan-300 font-semibold"
                    >
                      View All Missions →
                    </button>
                  </div>

                  <div className="space-y-2">
                    {tasks.slice(0, 2).map((t) => (
                      <div
                        key={t.task_id}
                        onClick={() => onOpenWorkspace(t.task_id)}
                        className="p-3 rounded-xl bg-black/40 border border-white/5 hover:border-cyan-500/30 transition-all cursor-pointer flex items-center justify-between gap-3 text-xs"
                      >
                        <div className="flex items-center gap-2 flex-1 truncate">
                          <span className="text-cyan-400 font-bold">⚡</span>
                          <span className="text-zinc-200 font-medium truncate">{t.goal.objective}</span>
                        </div>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-white/5 border border-white/10 text-zinc-400">
                          {t.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 space-y-2">
                  <div className="text-2xl">⚡</div>
                  <h4 className="text-sm font-semibold text-zinc-200">No Active Mission</h4>
                  <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                    Type a goal below or press <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono text-[10px]">⌘K</kbd> to launch autonomous multi-step execution.
                  </p>
                </div>
              )}
            </motion.div>
          )}

          {/* 2. DIALOGUE STREAM CARD */}
          {activeTab === 'dialogue' && (
            <motion.div
              key="dialogue-card"
              initial={{ opacity: 0, y: 15, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -15, scale: 0.98 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              className="w-full p-5 rounded-3xl border border-white/15 bg-gradient-to-br from-zinc-950/85 via-zinc-900/60 to-black/90 backdrop-blur-3xl shadow-[0_20px_60px_rgba(0,0,0,0.6)] space-y-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ChatIcon size={16} className="text-cyan-400" />
                  <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider font-mono">
                    Live Dialogue Feed
                  </h3>
                </div>
                <button
                  onClick={onOpenChat}
                  className="text-xs font-mono text-cyan-400 hover:text-cyan-300 font-semibold"
                >
                  Open Full Chat →
                </button>
              </div>

              {recentMessages.length === 0 ? (
                <div className="text-center py-8 text-zinc-500 text-xs">
                  No conversation history yet. Start by typing below or saying "Hey Genie".
                </div>
              ) : (
                <div className="space-y-2.5 max-h-[220px] overflow-y-auto custom-scrollbar pr-1">
                  {recentMessages.map((m, i) => (
                    <div
                      key={m.id || i}
                      className={`p-3 rounded-2xl text-xs leading-relaxed border ${
                        m.role === 'user'
                          ? 'bg-indigo-950/30 border-indigo-500/20 text-indigo-100 ml-6'
                          : 'bg-zinc-900/60 border-white/10 text-zinc-200 mr-6'
                      }`}
                    >
                      <div className="flex items-center justify-between font-mono text-[10px] text-zinc-400 mb-1">
                        <span className="font-semibold">{m.role === 'user' ? 'You' : 'Genie'}</span>
                        <span>{new Date(m.timestamp || Date.now()).toLocaleTimeString()}</span>
                      </div>
                      <p className="whitespace-pre-wrap break-words">{m.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {/* 3. DESKTOP & PERCEPTION INTELLIGENCE CARD */}
          {activeTab === 'perception' && (
            <motion.div
              key="perception-card"
              initial={{ opacity: 0, y: 15, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -15, scale: 0.98 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              className="w-full p-5 rounded-3xl border border-white/15 bg-gradient-to-br from-zinc-950/85 via-zinc-900/60 to-black/90 backdrop-blur-3xl shadow-[0_20px_60px_rgba(0,0,0,0.6)] space-y-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <EyeIcon size={16} className="text-cyan-400" />
                  <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider font-mono">
                    Real-time Perception & OS Telemetry
                  </h3>
                </div>
                <button
                  onClick={onTriggerQuickLook}
                  className="px-3 py-1 rounded-xl text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 hover:bg-indigo-500/30 transition-all flex items-center gap-1.5"
                >
                  <span>Quick Look</span>
                  <span className="text-[10px] font-mono text-zinc-400">Ctrl+Shift+G</span>
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                <div className="p-3 rounded-2xl bg-black/40 border border-white/5 space-y-1.5">
                  <div className="text-[10px] font-mono uppercase text-zinc-400">Agent Core</div>
                  <div className="flex items-center gap-2 font-semibold text-zinc-200">
                    <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`} />
                    <span>{isConnected ? 'Autonomous Ready' : 'Connecting…'}</span>
                  </div>
                </div>

                <div className="p-3 rounded-2xl bg-black/40 border border-white/5 space-y-1.5">
                  <div className="text-[10px] font-mono uppercase text-zinc-400">Vision Stream</div>
                  <div className="flex items-center gap-2 font-semibold text-zinc-200">
                    <span className={`w-2 h-2 rounded-full ${visionSupported ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
                    <span>{visionSupported ? 'Active' : (visionReason || 'Offline')}</span>
                  </div>
                </div>

                <div className="p-3 rounded-2xl bg-black/40 border border-white/5 space-y-1.5">
                  <div className="text-[10px] font-mono uppercase text-zinc-400">Continuous Companion</div>
                  <div className="flex items-center gap-2 font-semibold text-zinc-200">
                    <span className={`w-2 h-2 rounded-full ${companion.mode === 'active' ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
                    <span>{companion.mode === 'active' ? `Active (${companion.subMode})` : 'Standby'}</span>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* 4. NEURAL MEMORY CARD */}
          {activeTab === 'memory' && (
            <motion.div
              key="memory-card"
              initial={{ opacity: 0, y: 15, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -15, scale: 0.98 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              className="w-full p-5 rounded-3xl border border-white/15 bg-gradient-to-br from-zinc-950/85 via-zinc-900/60 to-black/90 backdrop-blur-3xl shadow-[0_20px_60px_rgba(0,0,0,0.6)] space-y-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BrainIcon size={16} className="text-cyan-400" />
                  <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider font-mono">
                    Cognitive Memory Vault
                  </h3>
                </div>
                <button
                  onClick={() => onNavigate('memory')}
                  className="text-xs font-mono text-cyan-400 hover:text-cyan-300 font-semibold"
                >
                  Manage Memory →
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-2xl bg-black/40 border border-white/5 space-y-1">
                  <span className="text-[10px] font-mono text-indigo-400 font-semibold uppercase">Learned Preferences</span>
                  <p className="text-zinc-300 text-[11px] leading-relaxed">
                    User prefers Cyber Luxe dark glass aesthetic, structured plans, and direct concise reports.
                  </p>
                </div>
                <div className="p-3 rounded-2xl bg-black/40 border border-white/5 space-y-1">
                  <span className="text-[10px] font-mono text-cyan-400 font-semibold uppercase">Project Context</span>
                  <p className="text-zinc-300 text-[11px] leading-relaxed">
                    Project Genie AI Rebuild — Multi-agent runtime with DAG task execution and persistent memory.
                  </p>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
