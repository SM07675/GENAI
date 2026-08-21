import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useTaskStore } from '../../store/taskStore';
import { PlanView } from './PlanView';
import { ActivityTimeline } from './ActivityTimeline';
import { TaskProgressBar } from './TaskProgressBar';
import { AgentBadge } from '../AgentActivity/AgentBadge';
import { ObservationCard } from '../AgentActivity/ObservationCard';

export interface TaskWorkspaceProps {
  onSendTaskAction: (action: 'pause' | 'resume' | 'cancel', taskId: string) => void;
}

export const TaskWorkspace: React.FC<TaskWorkspaceProps> = ({ onSendTaskAction }) => {
  const activeTask = useTaskStore((s) => s.activeTask);
  const closeTaskWorkspace = useTaskStore((s) => s.closeTaskWorkspace);
  const [activeTab, setActiveTab] = useState<'plan' | 'timeline' | 'observations'>('plan');

  if (!activeTask) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center text-zinc-500">
        <p>No active mission selected.</p>
      </div>
    );
  }

  const isRunning = activeTask.status === 'running' || activeTask.status === 'planning' || activeTask.status === 'replanning';
  const isPaused = activeTask.status === 'paused';
  const isComplete = activeTask.status === 'completed';
  const isFailed = activeTask.status === 'failed';

  const statusBadgeColor = isComplete
    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
    : isFailed
    ? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
    : isPaused
    ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
    : 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40 animate-pulse';

  return (
    <div className="h-full flex flex-col bg-zinc-950/80 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
      {/* Top Header */}
      <div className="p-5 border-b border-white/10 bg-gradient-to-r from-white/[0.03] to-transparent space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1.5 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-medium border uppercase tracking-wider ${statusBadgeColor}`}>
                {activeTask.status}
              </span>
              {activeTask.active_agent && (
                <AgentBadge agent={activeTask.active_agent} isActive={isRunning} size="sm" />
              )}
              {activeTask.active_tool && (
                <span className="px-2 py-0.5 rounded text-xs font-mono bg-cyan-950/60 border border-cyan-500/30 text-cyan-300">
                  ⚙ {activeTask.active_tool}
                </span>
              )}
            </div>
            <h2 className="text-lg font-semibold tracking-tight text-white line-clamp-2">
              {activeTask.goal.objective}
            </h2>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            {isRunning && (
              <button
                onClick={() => onSendTaskAction('pause', activeTask.task_id)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:bg-amber-500/30 transition-all"
              >
                ⏸ Pause
              </button>
            )}
            {isPaused && (
              <button
                onClick={() => onSendTaskAction('resume', activeTask.task_id)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30 transition-all"
              >
                ▶ Resume
              </button>
            )}
            {(isRunning || isPaused) && (
              <button
                onClick={() => onSendTaskAction('cancel', activeTask.task_id)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-500/20 text-rose-300 border border-rose-500/30 hover:bg-rose-500/30 transition-all"
              >
                ✕ Cancel
              </button>
            )}
            <button
              onClick={closeTaskWorkspace}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-all"
              title="Close Workspace"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        <TaskProgressBar
          progress={activeTask.progress}
          status={activeTask.status}
          totalSteps={activeTask.plan?.steps?.length}
          completedSteps={activeTask.plan?.steps?.filter((s) => s.status === 'completed').length}
        />

        {/* Tabs */}
        <div className="flex items-center gap-2 border-b border-white/5 pt-1">
          <button
            onClick={() => setActiveTab('plan')}
            className={`pb-2 px-3 text-xs font-medium border-b-2 transition-all ${
              activeTab === 'plan'
                ? 'border-cyan-400 text-cyan-300'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Plan Graph ({activeTask.plan?.steps?.length || 0})
          </button>
          <button
            onClick={() => setActiveTab('timeline')}
            className={`pb-2 px-3 text-xs font-medium border-b-2 transition-all ${
              activeTab === 'timeline'
                ? 'border-cyan-400 text-cyan-300'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Activity Timeline ({activeTask.timeline?.length || 0})
          </button>
          <button
            onClick={() => setActiveTab('observations')}
            className={`pb-2 px-3 text-xs font-medium border-b-2 transition-all ${
              activeTab === 'observations'
                ? 'border-cyan-400 text-cyan-300'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Observations ({activeTask.observations?.length || 0})
          </button>
        </div>
      </div>

      {/* Main Workspace Body */}
      <div className="flex-1 overflow-y-auto p-5 custom-scrollbar">
        <AnimatePresence mode="wait">
          {activeTab === 'plan' && (
            <motion.div
              key="plan"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              <PlanView plan={activeTask.plan} />
            </motion.div>
          )}

          {activeTab === 'timeline' && (
            <motion.div
              key="timeline"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              <ActivityTimeline timeline={activeTask.timeline} />
            </motion.div>
          )}

          {activeTab === 'observations' && (
            <motion.div
              key="observations"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-3"
            >
              {activeTask.observations && activeTask.observations.length > 0 ? (
                activeTask.observations.map((obs) => (
                  <ObservationCard key={obs.observation_id} observation={obs} />
                ))
              ) : (
                <div className="text-center py-12 text-zinc-500 text-xs">
                  No post-action observations collected yet.
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
