/**
 * ProjectsView.tsx — Projects & Task Management inside Main App.
 */
import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  ProjectsIcon,
  CheckIcon,
  BrainIcon,
  PlusIcon,
  ZapIcon,
} from '../UI/Icons';

export default function ProjectsView() {
  const [tasks, setTasks] = useState([
    { id: '1', title: 'Floating Screen Companion Mode Overlay', done: true },
    { id: '2', title: 'Cyber Luxe Dark & Sky Glass Theme Engine', done: true },
    { id: '3', title: '2D Animated Robot Avatar with Audio Lip-Sync', done: true },
    { id: '4', title: 'Sentence-Transformers Semantic Memory Vector Store', done: true },
    { id: '5', title: 'Focus-Free Dragging Physics & Corner Snapping', done: true },
  ]);

  const toggleTask = (id: string) => {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t)));
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Active Projects & Task Tracking
        </h1>
        <p className="text-xs md:text-sm font-medium text-slate-400 mt-1">
          Genie tracks active development context, project tasks, and architecture notes.
        </p>
      </div>

      {/* Project Banner Card */}
      <div className="cyber-glass rounded-3xl p-6 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-white/10 pb-4 gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <ProjectsIcon size={24} />
            </div>
            <div>
              <h2 className="text-lg font-extrabold">Project: Genie AI Companion</h2>
              <p className="text-xs font-semibold text-cyan-400">Status: Complete Premium UI/UX Redesign</p>
            </div>
          </div>
          <span className="px-3.5 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-xs font-bold text-emerald-400 self-start md:self-auto">
            ● Active Workspace
          </span>
        </div>

        <p className="text-xs leading-relaxed text-slate-300">
          Transforming Genie into a living digital companion with cyber-luxe aesthetics, cute 2D robot avatar, real-time voice lip-sync, local sentence-transformers memory, and draggable screen overlay.
        </p>
      </div>

      {/* Task List & Architecture Notes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Task Checklist */}
        <div className="cyber-card rounded-3xl p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <h3 className="text-sm font-bold flex items-center gap-2">
              <CheckIcon size={18} className="text-cyan-400" />
              <span>Task Checklist</span>
            </h3>
            <span className="text-xs text-cyan-400 font-bold">{tasks.filter(t => t.done).length} / {tasks.length} Completed</span>
          </div>

          <div className="space-y-2.5">
            {tasks.map((task) => (
              <div
                key={task.id}
                onClick={() => toggleTask(task.id)}
                className="flex items-center gap-3 p-3 rounded-2xl bg-white/5 border border-white/10 cursor-pointer hover:bg-white/10 transition-all text-xs"
              >
                <div className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${task.done ? 'bg-cyan-500 text-slate-950 font-bold' : 'bg-slate-700 text-slate-400'}`}>
                  <CheckIcon size={12} />
                </div>
                <span className={`font-semibold ${task.done ? 'line-through text-slate-400' : 'text-slate-200'}`}>
                  {task.title}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Architecture Notes */}
        <div className="cyber-card rounded-3xl p-6 space-y-4">
          <h3 className="text-sm font-bold flex items-center gap-2 border-b border-white/10 pb-3">
            <BrainIcon size={18} className="text-purple-400" />
            <span>Architecture Notes</span>
          </h3>

          <div className="space-y-3 text-xs leading-relaxed text-slate-300">
            <div className="p-3 rounded-2xl bg-white/5 border border-white/10">
              <span className="font-bold text-cyan-400">Unified Core:</span> Reuses existing FastAPI LLM router, STT (Whisper), Edge TTS, VAD, and SQLite memory store.
            </div>
            <div className="p-3 rounded-2xl bg-white/5 border border-white/10">
              <span className="font-bold text-purple-400">Screen Overlay:</span> Floating draggable portal widget in Web, always-on-top transparent BrowserWindow in Electron.
            </div>
            <div className="p-3 rounded-2xl bg-white/5 border border-white/10">
              <span className="font-bold text-emerald-400">Design System:</span> Responsive Cyber Luxe Dark + Sky Glass theme system with Framer Motion animations.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
