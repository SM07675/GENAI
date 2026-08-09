/**
 * RightContextPanel.jsx — Genie OS Right Panel (~27% width)
 * Memory context, live tool execution console, system notifications, active tasks.
 */

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../../store/appStore';

export default function RightContextPanel() {
  const genieState = useAppStore((s) => s.genieState);
  const activeToolEvents = useAppStore((s) => s.activeToolEvents);
  const systemNote = useAppStore((s) => s.systemNote);
  const messages = useAppStore((s) => s.messages);

  // Collect all tool events from recent messages
  const recentToolEvents = messages
    .flatMap((m) => m.toolEvents || [])
    .slice(-6);

  return (
    <aside
      className="flex flex-col h-full overflow-hidden select-none border-l"
      style={{
        width: '27%',
        minWidth: '280px',
        maxWidth: '420px',
        background: 'rgba(7, 11, 20, 0.75)',
        backdropFilter: 'blur(20px)',
        borderColor: 'rgba(255, 255, 255, 0.06)',
      }}
    >
      {/* ── PANEL HEADER ─────────────────────────────────────────────── */}
      <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: 'rgba(255, 255, 255, 0.06)' }}>
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <span>⚡</span> Context & Execution
          </h2>
          <p className="text-[11px] text-slate-400">Live Agent Operations</p>
        </div>

        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
          Active Sync
        </span>
      </div>

      {/* ── SYSTEM NOTIFICATIONS & NOTES ────────────────────────────────── */}
      <AnimatePresence>
        {systemNote && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="p-3 border-b bg-amber-500/10 border-amber-500/20 text-amber-300 text-xs flex items-start gap-2.5"
          >
            <span className="text-amber-400 text-sm">⚡</span>
            <div className="flex-1">
              <p className="font-semibold text-[11px]">System Notice</p>
              <p className="text-[11px] leading-tight text-amber-200/90">{systemNote}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── SCROLLABLE CONTEXT BODY ────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-4 custom-scrollbar">
        {/* 1. Tool Execution Console */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <span>🛠️</span> Tool Execution ({activeToolEvents.length} running)
            </span>
            {activeToolEvents.length > 0 && (
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            )}
          </div>

          {activeToolEvents.length === 0 && recentToolEvents.length === 0 ? (
            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] text-center text-xs text-slate-400">
              No tools active
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {/* Currently active tools */}
              {activeToolEvents.map((evt, idx) => (
                <motion.div
                  key={`active-${idx}`}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/25 text-xs text-amber-200"
                >
                  <div className="flex items-center justify-between font-mono font-semibold mb-1 text-[11px]">
                    <span className="flex items-center gap-1.5 text-amber-300">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                      {evt.name || 'Executing Tool'}
                    </span>
                    <span className="text-[10px] text-amber-400">RUNNING</span>
                  </div>
                  {evt.args && (
                    <pre className="text-[10px] font-mono bg-black/40 p-1.5 rounded text-slate-300 overflow-x-auto">
                      {JSON.stringify(evt.args, null, 2)}
                    </pre>
                  )}
                </motion.div>
              ))}

              {/* Recent finished tool events */}
              {recentToolEvents.map((evt, idx) => (
                <div
                  key={`recent-${idx}`}
                  className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04] text-xs text-slate-300"
                >
                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 mb-0.5">
                    <span>{evt.name || 'Tool Event'}</span>
                    <span className="text-[10px] text-emerald-400">DONE</span>
                  </div>
                  {evt.result && (
                    <p className="text-[10px] text-slate-400 truncate">
                      {typeof evt.result === 'string' ? evt.result : JSON.stringify(evt.result)}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 2. Persona & Memory Vault Summary */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <span>🧠</span> Memory & State
            </span>
          </div>

          <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Genie Mode</span>
              <span className="font-semibold text-cyan-400 capitalize">{genieState}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Voice Synthesis</span>
              <span className="font-semibold text-emerald-400">Edge TTS + Cue</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Memory Graph</span>
              <span className="font-mono text-[11px] text-slate-300">12 Active Nodes</span>
            </div>
          </div>
        </div>

        {/* 3. System Metrics Card */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <span>📊</span> Active Workspace
            </span>
          </div>

          <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] flex flex-col gap-2 text-xs">
            <div className="flex justify-between text-slate-400 text-[11px]">
              <span>Context Length</span>
              <span className="text-slate-200 font-mono">4,096 tokens</span>
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div className="bg-gradient-to-r from-cyan-500 to-indigo-500 h-full w-[35%]" />
            </div>

            <div className="flex justify-between text-slate-400 text-[11px] mt-1">
              <span>Latency</span>
              <span className="text-emerald-400 font-mono">14ms</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
