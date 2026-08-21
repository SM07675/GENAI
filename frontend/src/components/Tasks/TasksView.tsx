import React from 'react';
import { motion } from 'framer-motion';
import { useTaskStore, TaskState } from '../../store/taskStore';
import { TaskProgressBar } from '../TaskWorkspace/TaskProgressBar';
import { AgentBadge } from '../AgentActivity/AgentBadge';

export interface TasksViewProps {
  onOpenWorkspace: (taskId?: string) => void;
  onSendGoal: (text: string) => void;
}

export const TasksView: React.FC<TasksViewProps> = ({ onOpenWorkspace, onSendGoal }) => {
  const tasks = useTaskStore((s) => s.tasks);
  const activeTask = useTaskStore((s) => s.activeTask);

  const handleQuickGoal = (goalText: string) => {
    onSendGoal(goalText);
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar p-6 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <span className="text-cyan-400">⚡</span> Missions & Autonomous Tasks
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Track, inspect, and supervise multi-step agent workflows across your system.
          </p>
        </div>

        {activeTask && (
          <button
            onClick={() => onOpenWorkspace(activeTask.task_id)}
            className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30 transition-all flex items-center gap-1.5"
          >
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            Open Active Workspace
          </button>
        )}
      </div>

      {/* Quick Launch Pre-configured Agent Missions */}
      <div className="space-y-2">
        <span className="text-xs font-mono uppercase tracking-wider text-zinc-500 font-semibold">
          Quick Start Missions
        </span>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div
            onClick={() => handleQuickGoal('Search top tech headlines and compile a briefing')}
            className="p-3.5 rounded-xl border border-white/5 bg-zinc-950/40 hover:border-cyan-500/30 hover:bg-zinc-900/40 transition-all cursor-pointer space-y-1.5 group"
          >
            <div className="flex items-center gap-2">
              <span className="text-base">📰</span>
              <span className="text-xs font-semibold text-zinc-200 group-hover:text-cyan-300 transition">
                News Briefing
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Research Agent will aggregate and summarize today's headlines.
            </p>
          </div>

          <div
            onClick={() => handleQuickGoal('Inspect workspace files, check for errors, and report project status')}
            className="p-3.5 rounded-xl border border-white/5 bg-zinc-950/40 hover:border-emerald-500/30 hover:bg-zinc-900/40 transition-all cursor-pointer space-y-1.5 group"
          >
            <div className="flex items-center gap-2">
              <span className="text-base">💻</span>
              <span className="text-xs font-semibold text-zinc-200 group-hover:text-emerald-300 transition">
                Code & Project Audit
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Coding & File Agents inspect codebase structure and tests.
            </p>
          </div>

          <div
            onClick={() => handleQuickGoal('Capture screen, analyze active context, and provide suggestions')}
            className="p-3.5 rounded-xl border border-white/5 bg-zinc-950/40 hover:border-purple-500/30 hover:bg-zinc-900/40 transition-all cursor-pointer space-y-1.5 group"
          >
            <div className="flex items-center gap-2">
              <span className="text-base">👁</span>
              <span className="text-xs font-semibold text-zinc-200 group-hover:text-purple-300 transition">
                Situational Awareness
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              System Agent analyzes your current screen and active apps.
            </p>
          </div>
        </div>
      </div>

      {/* Task List */}
      <div className="space-y-3">
        <span className="text-xs font-mono uppercase tracking-wider text-zinc-500 font-semibold">
          All Tasks ({tasks.length})
        </span>

        {tasks.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-zinc-800 p-12 text-center space-y-3">
            <div className="text-3xl">✦</div>
            <p className="text-sm font-medium text-zinc-400">No autonomous tasks run yet.</p>
            <p className="text-xs text-zinc-500 max-w-sm mx-auto">
              Start by typing a goal in the command bar or click a quick-start mission above.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((task: TaskState) => {
              const isRunning = task.status === 'running' || task.status === 'planning' || task.status === 'replanning';
              const isComplete = task.status === 'completed';
              const isFailed = task.status === 'failed';

              const statusColor = isComplete
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                : isFailed
                ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                : isRunning
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30 animate-pulse'
                : 'bg-zinc-800 text-zinc-400 border-zinc-700';

              return (
                <motion.div
                  key={task.task_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  onClick={() => onOpenWorkspace(task.task_id)}
                  className="p-4 rounded-xl border border-white/10 bg-zinc-950/60 hover:border-cyan-500/40 hover:bg-zinc-900/60 backdrop-blur-md transition-all cursor-pointer space-y-3 shadow-lg group"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase border ${statusColor}`}>
                          {task.status}
                        </span>
                        {task.active_agent && (
                          <AgentBadge agent={task.active_agent} isActive={isRunning} size="sm" />
                        )}
                        <span className="text-[11px] font-mono text-zinc-500">
                          {new Date(task.started_at).toLocaleTimeString()}
                        </span>
                      </div>
                      <h3 className="text-sm font-semibold text-white group-hover:text-cyan-300 transition line-clamp-1">
                        {task.goal.objective}
                      </h3>
                    </div>

                    <span className="text-xs font-mono text-cyan-400 opacity-0 group-hover:opacity-100 transition">
                      View Workspace →
                    </span>
                  </div>

                  <TaskProgressBar
                    progress={task.progress}
                    status={task.status}
                    totalSteps={task.plan?.steps?.length}
                    completedSteps={task.plan?.steps?.filter((s) => s.status === 'completed').length}
                  />
                </motion.div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
