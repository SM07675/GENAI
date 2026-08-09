/**
 * ProjectsView.tsx — Projects & Task Management inside Main App.
 *
 * Per spec §38:
 * Project-aware UI showing:
 * - Current Active Project
 * - Status & Architecture Notes
 * - Next Tasks
 * - Known Bugs & Fixes
 */
import React, { useState } from 'react';

export default function ProjectsView() {
  const [tasks, setTasks] = useState([
    { id: '1', title: 'Separate Desktop Floating Companion Window', done: true },
    { id: '2', title: 'Sky Blue Light Glass Design System & Theme', done: true },
    { id: '3', title: '2D Animated Robot Avatar with Audio Lip-Sync', done: true },
    { id: '4', title: 'Sentence-Transformers Semantic Memory Store', done: true },
    { id: '5', title: 'Multi-Monitor Display Safety & Focus-Free Dragging', done: true },
  ]);

  const toggleTask = (id: string) => {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t)));
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Active Projects & Task Tracking
        </h1>
        <p className="text-sm font-medium text-slate-500 mt-1">
          Genie tracks active development context, tasks, and architecture notes.
        </p>
      </div>

      {/* Project Banner Card */}
      <div className="sky-glass rounded-3xl p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-sky-200/60 pb-3">
          <div className="flex items-center gap-3">
            <span className="text-2xl">▣</span>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Project: Genie AI Companion</h2>
              <p className="text-xs font-semibold text-sky-700">Status: Complete Premium UI/UX Redesign</p>
            </div>
          </div>
          <span className="px-3 py-1 rounded-full bg-emerald-100 border border-emerald-300 text-xs font-bold text-emerald-800">
            Active Phase
          </span>
        </div>

        <p className="text-xs leading-relaxed text-slate-600">
          Transforming Genie into a living digital companion with sky-blue light glass aesthetics, cute 2D robot avatar, real-time voice lip-sync, local sentence-transformers memory, and transparent desktop overlay window.
        </p>
      </div>

      {/* Task List & Architecture Notes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Next Tasks */}
        <div className="sky-glass-card rounded-2xl p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2 border-b border-sky-200/60 pb-3">
            <span>✓</span> Task Checklist
          </h3>

          <div className="space-y-2">
            {tasks.map((task) => (
              <div
                key={task.id}
                onClick={() => toggleTask(task.id)}
                className="flex items-center gap-3 p-3 rounded-xl bg-white/70 border border-sky-100 cursor-pointer hover:bg-white transition-all text-xs"
              >
                <div className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${task.done ? 'bg-sky-500 text-white' : 'bg-slate-200 text-slate-400'}`}>
                  ✓
                </div>
                <span className={`font-semibold ${task.done ? 'line-through text-slate-400' : 'text-slate-800'}`}>
                  {task.title}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Architecture Notes */}
        <div className="sky-glass-card rounded-2xl p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2 border-b border-sky-200/60 pb-3">
            <span>🧠</span> Architecture Notes
          </h3>

          <div className="space-y-3 text-xs leading-relaxed text-slate-600">
            <div className="p-3 rounded-xl bg-white/60 border border-sky-100">
              <span className="font-bold text-slate-800">Unified Core:</span> Reuses existing FastAPI LLM router, STT (Whisper), Edge TTS, VAD, and SQLite memory store.
            </div>
            <div className="p-3 rounded-xl bg-white/60 border border-sky-100">
              <span className="font-bold text-slate-800">Electron Overlay:</span> BrowserWindow configured with <code className="text-sky-700">transparent: true</code>, <code className="text-sky-700">frame: false</code>, <code className="text-sky-700">alwaysOnTop: true</code>, and <code className="text-sky-700">showInactive()</code>.
            </div>
            <div className="p-3 rounded-xl bg-white/60 border border-sky-100">
              <span className="font-bold text-slate-800">Design Tokens:</span> Centralized theme tokens (<code className="text-sky-700">theme.ts</code>) using Sky Blue light glass design identity.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
