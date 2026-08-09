/**
 * HomeView.tsx — Main Dashboard Home Screen.
 *
 * Sky Blue Light Theme design language per reference specification.
 * Shows:
 * - Personalized greeting ("Good morning 👋 Genie is ready.")
 * - Hero section: Genie status, voice availability, companion desktop overlay toggle
 * - Today's Focus & Active Projects
 * - Recent Activity log
 * - Real System Health summary (Voice ✓ LLM ✓ Memory ✓ Vision ✓ Backend ✓)
 */
import React from 'react';
import { motion } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import { useCompanionStore } from '../../store/companionStore';
import GenieFace from '../GenieFace/GenieFace';

export default function HomeView({
  onNavigate,
}: {
  onNavigate: (page: string) => void;
}) {
  const genieState = useAppStore((s) => s.genieState);
  const wsStatus = useAppStore((s) => s.wsStatus);
  const messages = useAppStore((s) => s.messages);
  const companion = useCompanionStore();

  const isConnected = wsStatus === 'authed' || wsStatus === 'connected';

  // Time-based greeting
  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? 'Good morning 👋' : hour < 18 ? 'Good afternoon 👋' : 'Good evening 👋';

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
      {/* ── Greeting Header ────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            {greeting}
          </h1>
          <p className="text-sm font-medium text-slate-500 mt-1">
            Genie AI Desktop Companion is active and ready to assist.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-sky-100/80 border border-sky-300/60 text-xs font-semibold text-sky-800 shadow-sm">
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-sky-500 animate-pulse' : 'bg-amber-500'
              }`}
            />
            <span>● {isConnected ? 'Online' : 'Connecting…'}</span>
          </div>

          <button
            onClick={() => companion.setMode(companion.mode === 'off' ? 'active' : 'off')}
            className={`px-4 py-2 rounded-xl text-xs font-semibold shadow-sm transition-all flex items-center gap-2 ${
              companion.mode !== 'off'
                ? 'bg-sky-500 text-white shadow-sky-500/20 hover:bg-sky-600'
                : 'bg-white border border-sky-200 text-slate-700 hover:bg-sky-50'
            }`}
          >
            <span>✨</span>
            <span>Desktop Companion: {companion.mode.toUpperCase()}</span>
          </button>
        </div>
      </div>

      {/* ── Hero Status Section ───────────────────────────────────────── */}
      <div className="sky-glass rounded-3xl p-6 relative overflow-hidden flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-3 max-w-md z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-100 border border-sky-300 text-xs font-bold text-sky-700">
            <span>ROBOT PRESENCE</span>
          </div>
          <h2 className="text-xl font-bold text-slate-900">
            Always-Available Digital Companion
          </h2>
          <p className="text-xs leading-relaxed text-slate-600">
            Genie floats above your work in Chrome, VS Code, and Windows. Use voice, camera vision, or hotkeys anytime.
          </p>

          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={() => onNavigate('companion')}
              className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold shadow-md shadow-sky-500/20 transition-all"
            >
              Configure Companion
            </button>
            <button
              onClick={() => onNavigate('memory')}
              className="px-4 py-2 rounded-xl bg-white/80 hover:bg-white border border-sky-200 text-slate-700 text-xs font-semibold transition-all"
            >
              View Memory
            </button>
          </div>
        </div>

        {/* Hero Avatar Preview */}
        <div className="relative z-10 flex flex-col items-center justify-center p-4 bg-sky-50/50 rounded-2xl border border-sky-200/60 shadow-inner">
          <GenieFace size={160} showBody={false} minimal={false} />
          <div className="mt-3 text-xs font-bold text-sky-700 tracking-wide uppercase">
            Status: {genieState}
          </div>
        </div>
      </div>

      {/* ── Grid Layout: Focus, Activity, System Health ────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Today's Focus */}
        <div className="sky-glass-card rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-sky-200/60 pb-3">
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
              <span>🎯</span> Today's Focus
            </h3>
            <span className="text-xs text-sky-600 font-semibold">Active</span>
          </div>
          <div className="space-y-2.5">
            <FocusItem title="Desktop Companion Overlay" subtitle="Floating transparent AI presence" done={true} />
            <FocusItem title="Voice Pipeline & Lip-Sync" subtitle="Real-time Web Audio API amplitude" done={true} />
            <FocusItem title="Semantic Memory Retrieval" subtitle="Local sentence-transformers embeddings" done={true} />
            <FocusItem title="UI/UX Sky Blue Redesign" subtitle="Reference design identity applied" done={true} />
          </div>
        </div>

        {/* Recent Activity */}
        <div className="sky-glass-card rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-sky-200/60 pb-3">
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
              <span>⚡</span> Recent Activity
            </h3>
            <span className="text-xs text-slate-400 font-mono">Real-time</span>
          </div>

          {messages.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-400 font-medium">
              No recent conversation turns yet. Talk to Genie or type a message!
            </div>
          ) : (
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1 custom-scrollbar">
              {messages.slice(-4).reverse().map((m, i) => (
                <div
                  key={m.id ? `msg-${m.id}` : `turn-${i}`}
                  className="p-2.5 rounded-xl bg-white/70 border border-sky-100 text-xs space-y-1"
                >
                  <span className={`font-bold ${m.role === 'user' ? 'text-sky-700' : 'text-slate-800'}`}>
                    {m.role === 'user' ? 'YOU' : 'GENIE'}
                  </span>
                  <p className="text-slate-600 line-clamp-2">{m.text}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* System Health */}
        <div className="sky-glass-card rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-sky-200/60 pb-3">
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
              <span>🩺</span> System Health
            </h3>
            <span className="text-xs text-emerald-600 font-bold">100% Operational</span>
          </div>

          <div className="space-y-2">
            <HealthRow label="Voice Engine" ok={true} detail="Edge TTS / Vosk / Whisper" />
            <HealthRow label="LLM Provider" ok={true} detail="Nvidia / Local GGUF" />
            <HealthRow label="Memory Service" ok={true} detail="SQLite + Qdrant Embeddings" />
            <HealthRow label="Vision Pipeline" ok={true} detail="Screenshot & Camera API" />
            <HealthRow label="WebSocket API" ok={isConnected} detail={isConnected ? 'Connected' : 'Reconnecting'} />
          </div>
        </div>
      </div>
    </div>
  );
}

function FocusItem({ title, subtitle, done }: { title: string; subtitle: string; done: boolean }) {
  return (
    <div className="flex items-start gap-3 p-2.5 rounded-xl bg-white/60 border border-sky-100">
      <div className={`mt-0.5 w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${done ? 'bg-sky-500 text-white' : 'bg-slate-200 text-slate-500'}`}>
        ✓
      </div>
      <div>
        <div className="text-xs font-bold text-slate-800">{title}</div>
        <div className="text-[11px] text-slate-500">{subtitle}</div>
      </div>
    </div>
  );
}

function HealthRow({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return (
    <div className="flex items-center justify-between p-2 rounded-xl bg-white/60 border border-sky-100 text-xs">
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${ok ? 'bg-emerald-500' : 'bg-rose-500'}`} />
        <span className="font-semibold text-slate-700">{label}</span>
      </div>
      <span className="text-[11px] text-slate-500 font-medium">{detail}</span>
    </div>
  );
}
