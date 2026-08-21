import React from 'react';
import { motion } from 'framer-motion';
import { ExecutionPlan, PlanStep } from '../../store/taskStore';
import { StepStatusIndicator } from '../AgentActivity/StepStatusIndicator';
import { AgentBadge } from '../AgentActivity/AgentBadge';

export interface PlanViewProps {
  plan: ExecutionPlan | null;
  activeStepId?: string | null;
}

export const PlanView: React.FC<PlanViewProps> = ({ plan, activeStepId }) => {
  if (!plan || !plan.steps || plan.steps.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center text-zinc-500 space-y-2">
        <div className="w-8 h-8 rounded-full border border-dashed border-zinc-700 animate-spin flex items-center justify-center text-xs">
          ✦
        </div>
        <p className="text-sm font-medium">Formulating execution graph...</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono uppercase tracking-wider text-zinc-400 font-semibold">
            Execution Plan
          </span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-white/5 border border-white/10 text-zinc-400">
            v{plan.version} • {plan.task_type}
          </span>
        </div>
        {plan.estimated_seconds && (
          <span className="text-[11px] font-mono text-zinc-400">
            ~{plan.estimated_seconds}s estimated
          </span>
        )}
      </div>

      <div className="relative pl-6 space-y-3 before:absolute before:left-3 before:top-3 before:bottom-3 before:w-[2px] before:bg-white/10">
        {plan.steps.map((step: PlanStep, idx: number) => {
          const isRunning = step.status === 'running';
          const isCompleted = step.status === 'completed';
          const isFailed = step.status === 'failed';

          return (
            <motion.div
              key={step.step_id || idx}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.05 }}
              className={`relative rounded-xl border p-3.5 transition-all duration-200 backdrop-blur-md ${
                isRunning
                  ? 'border-cyan-500/50 bg-cyan-950/20 shadow-[0_0_20px_rgba(6,182,212,0.15)] ring-1 ring-cyan-500/30'
                  : isCompleted
                  ? 'border-emerald-500/30 bg-emerald-950/10'
                  : isFailed
                  ? 'border-rose-500/40 bg-rose-950/20'
                  : 'border-white/5 bg-zinc-950/40 opacity-70 hover:opacity-100 hover:border-white/15'
              }`}
            >
              {/* Step Status Pin on timeline */}
              <div className="absolute -left-[30px] top-3.5 z-10">
                <StepStatusIndicator status={step.status} size={22} />
              </div>

              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-mono text-zinc-500">#{idx + 1}</span>
                    <h4
                      className={`text-sm font-medium tracking-tight ${
                        isRunning ? 'text-cyan-300 font-semibold' : isCompleted ? 'text-zinc-200' : 'text-zinc-400'
                      }`}
                    >
                      {step.title}
                    </h4>
                  </div>
                  {step.description && (
                    <p className="text-xs text-zinc-400 leading-relaxed pl-5">
                      {step.description}
                    </p>
                  )}
                </div>

                <AgentBadge agent={step.agent} isActive={isRunning} size="sm" />
              </div>

              {step.tool_names && step.tool_names.length > 0 && (
                <div className="mt-2.5 pt-2 border-t border-white/5 flex items-center gap-1.5 flex-wrap pl-5">
                  <span className="text-[10px] text-zinc-500 font-mono">Tools:</span>
                  {step.tool_names.map((t) => (
                    <span
                      key={t}
                      className="px-2 py-0.5 rounded text-[10px] font-mono bg-white/5 border border-white/10 text-cyan-300/90"
                    >
                      ⚙ {t}
                    </span>
                  ))}
                </div>
              )}

              {step.error && (
                <div className="mt-2 p-2 rounded bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs font-mono">
                  {step.error}
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
