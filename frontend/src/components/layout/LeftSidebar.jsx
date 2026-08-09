/**
 * LeftSidebar.jsx — Genie OS Left Panel (~18% width)
 * Navigation, conversation history, quick presets, system status.
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../../store/appStore';

const QUICK_PRESETS = [
  { icon: '✨', label: 'Summarize recent context', prompt: 'Summarize our recent conversation and active context.' },
  { icon: '💻', label: 'Check active tasks', prompt: 'What tools and tasks are currently running?' },
  { icon: '🧠', label: 'Recall stored memories', prompt: 'List key stored facts in your memory vault.' },
  { icon: '⚡', label: 'System diagnostic', prompt: 'Run a quick diagnostic check on system services.' },
];

export default function LeftSidebar({ activeTab, setActiveTab }) {
  const wsStatus = useAppStore((s) => s.wsStatus);
  const messages = useAppStore((s) => s.messages);
  const pushUserMessage = useAppStore((s) => s.pushUserMessage);
  const toggleListening = useAppStore((s) => s.toggleListening);

  const [searchQuery, setSearchQuery] = useState('');

  // Group user messages for conversation history preview
  const userMessages = messages.filter((m) => m.role === 'user');
  const filteredHistory = userMessages.filter((m) =>
    m.text.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handlePresetClick = (promptText) => {
    pushUserMessage(promptText);
    // If ws is available, send message through voice or chat pipeline
    const ws = useAppStore.getState().ws;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'user_text_input', text: promptText }));
    }
  };

  return (
    <aside
      className="flex flex-col h-full overflow-hidden select-none border-r"
      style={{
        width: '18%',
        minWidth: '220px',
        maxWidth: '300px',
        background: 'rgba(7, 11, 20, 0.75)',
        backdropFilter: 'blur(20px)',
        borderColor: 'rgba(255, 255, 255, 0.06)',
      }}
    >
      {/* ── BRAND / LOGO HEADER ───────────────────────────────────────── */}
      <div className="p-4 flex items-center justify-between border-b" style={{ borderColor: 'rgba(255, 255, 255, 0.06)' }}>
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center font-bold text-white shadow-lg"
            style={{
              background: 'linear-gradient(135deg, #22d3ee, #6366f1, #a855f7)',
              boxShadow: '0 0 16px rgba(34, 211, 238, 0.3)',
            }}
          >
            G
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-wide text-white flex items-center gap-1.5">
              GENIE OS
              <span className="text-[10px] px-1.5 py-0.5 rounded-full font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                v2.5
              </span>
            </h1>
            <p className="text-[11px] text-slate-400">3D AI Desktop Assistant</p>
          </div>
        </div>

        {/* Live WS Status Indicator */}
        <div
          className="w-2.5 h-2.5 rounded-full"
          title={`WebSocket: ${wsStatus}`}
          style={{
            background: wsStatus === 'authed' ? '#34d399' : wsStatus === 'connecting' ? '#fbbf24' : '#f87171',
            boxShadow: wsStatus === 'authed' ? '0 0 8px #34d399' : 'none',
          }}
        />
      </div>

      {/* ── NAVIGATION TABS ────────────────────────────────────────────── */}
      <div className="p-3 flex flex-col gap-1 border-b" style={{ borderColor: 'rgba(255, 255, 255, 0.05)' }}>
        {[
          { id: 'assistant', label: 'Assistant Stage', icon: '🤖' },
          { id: 'history', label: 'Conversations', icon: '💬' },
          { id: 'memory', label: 'Memory Vault', icon: '🧠' },
          { id: 'tasks', label: 'Task Runner', icon: '⚡' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'
            }`}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* ── QUICK PROMPT PRESETS ────────────────────────────────────────── */}
      <div className="px-3 pt-3 pb-2">
        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2 px-1">
          Quick Actions
        </p>
        <div className="flex flex-col gap-1.5">
          {QUICK_PRESETS.map((preset, idx) => (
            <button
              key={idx}
              onClick={() => handlePresetClick(preset.prompt)}
              className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs text-slate-300 hover:text-white bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.04] transition-all flex items-center gap-2 group"
            >
              <span className="text-sm group-hover:scale-110 transition-transform">{preset.icon}</span>
              <span className="truncate">{preset.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── CONVERSATION HISTORY LIST ───────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-h-0 px-3 pt-2 pb-3">
        <div className="flex items-center justify-between mb-2 px-1">
          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            History ({filteredHistory.length})
          </p>
        </div>

        {/* History Search input */}
        <input
          type="text"
          placeholder="Filter history..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-2.5 py-1.5 mb-2 rounded-lg text-xs bg-black/30 border border-white/10 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
        />

        <div className="flex-1 overflow-y-auto flex flex-col gap-1.5 pr-1 custom-scrollbar">
          {filteredHistory.length === 0 ? (
            <div className="py-6 text-center text-xs text-slate-400">
              No recent prompts
            </div>
          ) : (
            filteredHistory.slice().reverse().map((msg) => (
              <div
                key={msg.id}
                className="p-2 rounded-lg text-xs bg-white/[0.02] hover:bg-white/[0.05] border border-white/[0.04] text-slate-300 transition-all cursor-pointer truncate"
                title={msg.text}
              >
                <div className="flex items-center justify-between text-[10px] text-slate-400 mb-0.5">
                  <span>You</span>
                  <span>{new Date(msg.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
                <p className="truncate text-slate-200">{msg.text}</p>
              </div>
            ))
          )}
        </div>
      </div>

      {/* ── FOOTER STATS ──────────────────────────────────────────────── */}
      <div className="p-3 border-t text-[11px] text-slate-400 flex items-center justify-between bg-black/20" style={{ borderColor: 'rgba(255, 255, 255, 0.05)' }}>
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Engine Online
        </span>
        <span className="font-mono text-[10px] text-slate-500">60 FPS</span>
      </div>
    </aside>
  );
}
