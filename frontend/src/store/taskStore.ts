import { create } from 'zustand';

export interface PlanStep {
  step_id: string;
  title: string;
  description: string;
  agent: string;
  tool_names: string[];
  depends_on: string[];
  status: 'pending' | 'ready' | 'running' | 'completed' | 'failed' | 'skipped' | 'retrying' | 'cancelled';
  parallel_group?: string | null;
  timeout_seconds?: number;
  retry_count?: number;
  result?: Record<string, any>;
  error?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  observations?: string[];
}

export interface ExecutionPlan {
  plan_id: string;
  objective: string;
  task_type: string;
  steps: PlanStep[];
  expected_failures: string[];
  estimated_seconds?: number | null;
  progress: number;
  version: number;
  created_at: string;
}

export interface TimelineEntry {
  entry_id: string;
  timestamp: string;
  agent: string;
  action: string;
  detail: string;
  status: 'info' | 'success' | 'warning' | 'error';
  step_id?: string | null;
  tool_name?: string | null;
  duration_ms?: number | null;
}

export interface Observation {
  observation_id: string;
  source: string;
  content: string;
  timestamp: string;
  step_id?: string | null;
}

export interface TaskState {
  task_id: string;
  session_id: string;
  goal: {
    goal_id: string;
    objective: string;
    constraints?: string[];
    expected_outcome?: string;
    required_capabilities?: string[];
    raw_input?: string;
    is_simple?: boolean;
  };
  status: 'created' | 'planning' | 'running' | 'paused' | 'replanning' | 'verifying' | 'completed' | 'failed' | 'cancelled';
  plan: ExecutionPlan | null;
  active_agent: string | null;
  active_tool: string | null;
  observations: Observation[];
  timeline: TimelineEntry[];
  progress: number;
  confidence: number;
  autonomy_level: 'manual' | 'assist' | 'balanced' | 'autonomous';
  started_at: string;
  paused_at?: string | null;
  completed_at?: string | null;
  result?: Record<string, any>;
  error?: string | null;
  elapsed_seconds: number;
}

interface TaskStoreState {
  activeTask: TaskState | null;
  tasks: TaskState[];
  isTaskWorkspaceOpen: boolean;
  activeAgentFilter: string | null;

  // Actions
  setActiveTask: (task: TaskState | null) => void;
  updateActiveTask: (updater: (prev: TaskState) => TaskState) => void;
  setTasks: (tasks: TaskState[]) => void;
  openTaskWorkspace: (taskId?: string) => void;
  closeTaskWorkspace: () => void;
  setAgentFilter: (agent: string | null) => void;

  // Event handlers for real-time WebSocket events
  onGoalReceived: (data: { task_id: string; input: string }) => void;
  onPlanCreated: (data: { task_id: string; plan: ExecutionPlan; version?: number }) => void;
  onStepStarted: (data: { task_id: string; step: PlanStep; progress: number }) => void;
  onStepCompleted: (data: { task_id: string; step_id: string; result: any; progress: number }) => void;
  onStepFailed: (data: { task_id: string; step_id: string; error: string; progress: number }) => void;
  onAgentActivated: (data: { task_id: string; agent: string; step_id?: string }) => void;
  onToolCalled: (data: { task_id?: string; tool_name: string; args: any; step_id?: string }) => void;
  onToolCompleted: (data: { task_id?: string; tool_name: string; status: string; elapsed_ms: number }) => void;
  onObservationReceived: (data: { task_id?: string; observation: Observation }) => void;
  onVerificationResult: (data: { task_id?: string; step_id?: string; status: string; message: string }) => void;
  onTaskCompleted: (data: { task_id: string; success: boolean; summary: string; progress: number }) => void;
  onTaskPaused: (data: { task_id: string }) => void;
  onTaskResumed: (data: { task_id: string }) => void;
  onTaskCancelled: (data: { task_id: string }) => void;
  onReplanning: (data: { task_id: string; attempt: number }) => void;
}

export const useTaskStore = create<TaskStoreState>((set, get) => ({
  activeTask: null,
  tasks: [],
  isTaskWorkspaceOpen: false,
  activeAgentFilter: null,

  setActiveTask: (task) => set({ activeTask: task }),
  
  updateActiveTask: (updater) =>
    set((state) => ({
      activeTask: state.activeTask ? updater(state.activeTask) : null,
    })),

  setTasks: (tasks) => set({ tasks }),

  openTaskWorkspace: (taskId) => {
    if (taskId) {
      const task = get().tasks.find((t) => t.task_id === taskId);
      if (task) {
        set({ activeTask: task, isTaskWorkspaceOpen: true });
        return;
      }
    }
    set({ isTaskWorkspaceOpen: true });
  },

  closeTaskWorkspace: () => set({ isTaskWorkspaceOpen: false }),

  setAgentFilter: (agent) => set({ activeAgentFilter: agent }),

  onGoalReceived: (data) => {
    const newTask: TaskState = {
      task_id: data.task_id,
      session_id: 'default',
      goal: {
        goal_id: 'goal_' + Date.now(),
        objective: data.input,
        raw_input: data.input,
      },
      status: 'planning',
      plan: null,
      active_agent: 'planner',
      active_tool: null,
      observations: [],
      timeline: [
        {
          entry_id: 'tl_' + Date.now(),
          timestamp: new Date().toLocaleTimeString(),
          agent: 'Genie OS',
          action: 'Objective Received',
          detail: data.input,
          status: 'info',
        },
      ],
      progress: 0,
      confidence: 1.0,
      autonomy_level: 'balanced',
      started_at: new Date().toISOString(),
      elapsed_seconds: 0,
    };

    set((state) => ({
      activeTask: newTask,
      tasks: [newTask, ...state.tasks.filter((t) => t.task_id !== data.task_id)],
      isTaskWorkspaceOpen: true,
    }));
  },

  onPlanCreated: (data) => {
    set((state) => {
      if (!state.activeTask || state.activeTask.task_id !== data.task_id) return state;
      const updated: TaskState = {
        ...state.activeTask,
        status: 'running',
        plan: data.plan,
        progress: data.plan.progress || 0,
        timeline: [
          ...state.activeTask.timeline,
          {
            entry_id: 'tl_' + Date.now(),
            timestamp: new Date().toLocaleTimeString(),
            agent: 'Planner',
            action: 'Execution Plan Created',
            detail: `${data.plan.steps?.length || 0} steps formulated for autonomous execution.`,
            status: 'success',
          },
        ],
      };
      return {
        activeTask: updated,
        tasks: state.tasks.map((t) => (t.task_id === data.task_id ? updated : t)),
      };
    });
  },

  onStepStarted: (data) => {
    set((state) => {
      if (!state.activeTask || state.activeTask.task_id !== data.task_id) return state;
      const plan = state.activeTask.plan;
      if (!plan) return state;

      const updatedSteps = plan.steps.map((s) =>
        s.step_id === data.step.step_id ? { ...s, status: 'running' as const, started_at: new Date().toISOString() } : s
      );

      const updated: TaskState = {
        ...state.activeTask,
        status: 'running',
        active_agent: data.step.agent,
        plan: { ...plan, steps: updatedSteps },
        progress: data.progress,
        timeline: [
          ...state.activeTask.timeline,
          {
            entry_id: 'tl_' + Date.now(),
            timestamp: new Date().toLocaleTimeString(),
            agent: data.step.agent,
            action: `Executing: ${data.step.title}`,
            detail: data.step.description || '',
            status: 'info',
            step_id: data.step.step_id,
          },
        ],
      };

      return {
        activeTask: updated,
        tasks: state.tasks.map((t) => (t.task_id === data.task_id ? updated : t)),
      };
    });
  },

  onStepCompleted: (data) => {
    set((state) => {
      if (!state.activeTask || state.activeTask.task_id !== data.task_id) return state;
      const plan = state.activeTask.plan;
      if (!plan) return state;

      const updatedSteps = plan.steps.map((s) =>
        s.step_id === data.step_id
          ? { ...s, status: 'completed' as const, completed_at: new Date().toISOString(), result: data.result }
          : s
      );

      const completedStep = plan.steps.find((s) => s.step_id === data.step_id);

      const updated: TaskState = {
        ...state.activeTask,
        plan: { ...plan, steps: updatedSteps },
        progress: data.progress,
        timeline: [
          ...state.activeTask.timeline,
          {
            entry_id: 'tl_' + Date.now(),
            timestamp: new Date().toLocaleTimeString(),
            agent: completedStep?.agent || 'Agent',
            action: `Completed: ${completedStep?.title || data.step_id}`,
            detail: typeof data.result?.message === 'string' ? data.result.message : 'Step finished successfully.',
            status: 'success',
            step_id: data.step_id,
          },
        ],
      };

      return {
        activeTask: updated,
        tasks: state.tasks.map((t) => (t.task_id === data.task_id ? updated : t)),
      };
    });
  },

  onStepFailed: (data) => {
    set((state) => {
      if (!state.activeTask || state.activeTask.task_id !== data.task_id) return state;
      const plan = state.activeTask.plan;
      if (!plan) return state;

      const updatedSteps = plan.steps.map((s) =>
        s.step_id === data.step_id
          ? { ...s, status: 'failed' as const, completed_at: new Date().toISOString(), error: data.error }
          : s
      );

      const failedStep = plan.steps.find((s) => s.step_id === data.step_id);

      const updated: TaskState = {
        ...state.activeTask,
        plan: { ...plan, steps: updatedSteps },
        timeline: [
          ...state.activeTask.timeline,
          {
            entry_id: 'tl_' + Date.now(),
            timestamp: new Date().toLocaleTimeString(),
            agent: failedStep?.agent || 'Agent',
            action: `Failure: ${failedStep?.title || data.step_id}`,
            detail: data.error,
            status: 'error',
            step_id: data.step_id,
          },
        ],
      };

      return {
        activeTask: updated,
        tasks: state.tasks.map((t) => (t.task_id === data.task_id ? updated : t)),
      };
    });
  },

  onAgentActivated: (data) => {
    set((state) => {
      if (!state.activeTask || state.activeTask.task_id !== data.task_id) return state;
      return {
        activeTask: {
          ...state.activeTask,
          active_agent: data.agent,
        },
      };
    });
  },

  onToolCalled: (data) => {
    set((state) => {
      if (!state.activeTask) return state;
      const updated: TaskState = {
        ...state.activeTask,
        active_tool: data.tool_name,
        timeline: [
          ...state.activeTask.timeline,
          {
            entry_id: 'tl_' + Date.now(),
            timestamp: new Date().toLocaleTimeString(),
            agent: state.activeTask.active_agent || 'Tool Engine',
            action: `Invoking Tool: ${data.tool_name}`,
            detail: typeof data.args === 'object' ? JSON.stringify(data.args) : '',
            status: 'info',
            tool_name: data.tool_name,
            step_id: data.step_id,
          },
        ],
      };
      return { activeTask: updated };
    });
  },

  onToolCompleted: (data) => {
    set((state) => {
      if (!state.activeTask) return state;
      return {
        activeTask: {
          ...state.activeTask,
          active_tool: null,
        },
      };
    });
  },

  onObservationReceived: (data) => {
    set((state) => {
      if (!state.activeTask) return state;
      return {
        activeTask: {
          ...state.activeTask,
          observations: [data.observation, ...state.activeTask.observations],
        },
      };
    });
  },

  onVerificationResult: (data) => {
    set((state) => {
      if (!state.activeTask) return state;
      const isPass = data.status === 'passed';
      return {
        activeTask: {
          ...state.activeTask,
          timeline: [
            ...state.activeTask.timeline,
            {
              entry_id: 'tl_' + Date.now(),
              timestamp: new Date().toLocaleTimeString(),
              agent: 'Verifier',
              action: `Verification: ${data.status.toUpperCase()}`,
              detail: data.message,
              status: isPass ? 'success' : 'warning',
              step_id: data.step_id,
            },
          ],
        },
      };
    });
  },

  onTaskCompleted: (data) => {
    set((state) => {
      if (!state.activeTask || state.activeTask.task_id !== data.task_id) return state;
      const updated: TaskState = {
        ...state.activeTask,
        status: data.success ? 'completed' : 'failed',
        progress: 1.0,
        completed_at: new Date().toISOString(),
        timeline: [
          ...state.activeTask.timeline,
          {
            entry_id: 'tl_' + Date.now(),
            timestamp: new Date().toLocaleTimeString(),
            agent: 'Genie OS',
            action: data.success ? 'Mission Accomplished' : 'Mission Concluded with Issues',
            detail: data.summary,
            status: data.success ? 'success' : 'error',
          },
        ],
      };
      return {
        activeTask: updated,
        tasks: state.tasks.map((t) => (t.task_id === data.task_id ? updated : t)),
      };
    });
  },

  onTaskPaused: (data) => {
    set((state) => {
      if (!state.activeTask || state.activeTask.task_id !== data.task_id) return state;
      const updated: TaskState = {
        ...state.activeTask,
        status: 'paused',
        paused_at: new Date().toISOString(),
        timeline: [
          ...state.activeTask.timeline,
          {
            entry_id: 'tl_' + Date.now(),
            timestamp: new Date().toLocaleTimeString(),
            agent: 'Genie OS',
            action: 'Task Paused by User',
            detail: 'Execution halted. Awaiting resume instruction.',
            status: 'warning',
          },
        ],
      };
      return {
        activeTask: updated,
        tasks: state.tasks.map((t) => (t.task_id === data.task_id ? updated : t)),
      };
    });
  },

  onTaskResumed: (data) => {
    set((state) => {
      if (!state.activeTask || state.activeTask.task_id !== data.task_id) return state;
      const updated: TaskState = {
        ...state.activeTask,
        status: 'running',
        paused_at: null,
        timeline: [
          ...state.activeTask.timeline,
          {
            entry_id: 'tl_' + Date.now(),
            timestamp: new Date().toLocaleTimeString(),
            agent: 'Genie OS',
            action: 'Task Resumed',
            detail: 'Execution graph continuing.',
            status: 'info',
          },
        ],
      };
      return {
        activeTask: updated,
        tasks: state.tasks.map((t) => (t.task_id === data.task_id ? updated : t)),
      };
    });
  },

  onTaskCancelled: (data) => {
    set((state) => {
      if (!state.activeTask || state.activeTask.task_id !== data.task_id) return state;
      const updated: TaskState = {
        ...state.activeTask,
        status: 'cancelled',
        completed_at: new Date().toISOString(),
        timeline: [
          ...state.activeTask.timeline,
          {
            entry_id: 'tl_' + Date.now(),
            timestamp: new Date().toLocaleTimeString(),
            agent: 'Genie OS',
            action: 'Task Terminated',
            detail: 'Cancelled by user command.',
            status: 'warning',
          },
        ],
      };
      return {
        activeTask: updated,
        tasks: state.tasks.map((t) => (t.task_id === data.task_id ? updated : t)),
      };
    });
  },

  onReplanning: (data) => {
    set((state) => {
      if (!state.activeTask || state.activeTask.task_id !== data.task_id) return state;
      const updated: TaskState = {
        ...state.activeTask,
        status: 'replanning',
        timeline: [
          ...state.activeTask.timeline,
          {
            entry_id: 'tl_' + Date.now(),
            timestamp: new Date().toLocaleTimeString(),
            agent: 'Planner',
            action: `Autonomous Replanning (Attempt ${data.attempt})`,
            detail: 'Recovering from obstacle by generating an alternative execution route.',
            status: 'warning',
          },
        ],
      };
      return {
        activeTask: updated,
        tasks: state.tasks.map((t) => (t.task_id === data.task_id ? updated : t)),
      };
    });
  },
}));
