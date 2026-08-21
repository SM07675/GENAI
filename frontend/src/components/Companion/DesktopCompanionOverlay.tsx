import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import { useCompanionStore } from '../../store/companionStore';
import { GenieCoreOrb } from '../GenieCoreOrb';
import { SendIcon, CameraIcon } from '../UI/Icons';

type CompanionBridge = {
  isElectron?: boolean;
  sendCompanionAction?: (action: Record<string, unknown>) => void;
  exitCompanion?: () => Promise<unknown>;
  focusMain?: () => void;
  setExpanded?: (expanded: boolean) => void;
  setAlwaysOnTop?: (enabled: boolean) => void;
  companionReady?: () => void;
  onCompanionState?: (callback: (state: any) => void) => (() => void) | undefined;
};

function getBridge(): CompanionBridge {
  return ((window as any).genie || {}) as CompanionBridge;
}

const STATE_LABELS: Record<string, { label: string; color: string }> = {
  offline: { label: 'Offline', color: 'text-zinc-500' },
  idle: { label: 'Ready', color: 'text-cyan-300' },
  sleeping: { label: 'Standby ("Hey Genie")', color: 'text-zinc-400' },
  listening: { label: 'Listening Mode', color: 'text-cyan-300 font-bold' },
  follow_up_listening: { label: 'Listening Mode', color: 'text-cyan-300 font-bold' },
  waking: { label: 'Waking up…', color: 'text-purple-300 font-bold' },
  transcribing: { label: 'Processing Voice…', color: 'text-amber-300 font-bold' },
  thinking: { label: 'Thinking Mode', color: 'text-purple-300 font-bold' },
  searching: { label: 'Search Mode', color: 'text-sky-300 font-bold' },
  planning: { label: 'Planning Mode', color: 'text-indigo-300 font-bold' },
  executing: { label: 'Execution Mode', color: 'text-emerald-300 font-bold' },
  speaking: { label: 'Speaking Mode', color: 'text-cyan-300 font-bold' },
  error: { label: 'Attention Needed', color: 'text-rose-300 font-bold' },
};

export default function DesktopCompanionOverlay() {
  const messages = useAppStore((state) => state.messages);
  const genieState = useAppStore((state) => state.genieState);
  const liveTranscript = useAppStore((state) => state.liveTranscript);
  const wsStatus = useAppStore((state) => state.wsStatus);
  const amplitude = useAppStore((state) => state.amplitude);
  const visionSupported = useAppStore((state) => state.visionSupported);

  const [expanded, setExpanded] = useState(false);
  const [alwaysOnTop, setAlwaysOnTop] = useState(true);
  const [text, setText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const connected = wsStatus === 'authed' || wsStatus === 'connected';
  const isListening = ['listening', 'waking', 'follow_up_listening'].includes(genieState);
  const isBusy = ['thinking', 'executing', 'transcribing', 'speaking'].includes(genieState);
  const statusInfo = !connected ? { label: 'Connecting…', color: 'text-amber-400' } : (STATE_LABELS[genieState] || STATE_LABELS.idle);

  useEffect(() => {
    document.body.classList.add('companion-overlay-mode');
    const bridge = getBridge();
    const unsubscribe = bridge.onCompanionState?.((snapshot) => {
      if (snapshot?.app) useAppStore.setState(snapshot.app);
      if (snapshot?.companion) useCompanionStore.setState(snapshot.companion);
    });
    bridge.companionReady?.();
    return () => {
      unsubscribe?.();
      document.body.classList.remove('companion-overlay-mode');
    };
  }, []);

  useEffect(() => {
    getBridge().setExpanded?.(expanded);
    if (expanded) {
      setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    }
  }, [expanded, messages]);

  const send = useCallback(() => {
    const prompt = text.trim();
    if (!prompt) return;
    const bridge = getBridge();
    bridge.sendCompanionAction?.({ type: 'text', text: prompt });
    setText('');
  }, [text]);

  const toggleVoice = useCallback(() => {
    getBridge().sendCompanionAction?.({ type: isBusy || isListening ? 'cancel' : 'manual_wake' });
  }, [isBusy, isListening]);

  const openMain = useCallback(() => getBridge().focusMain?.(), []);
  const closeCompanion = useCallback(() => { void getBridge().exitCompanion?.(); }, []);

  const recentMessages = useMemo(() => messages.slice(-10), [messages]);

  return (
    <main className="w-full h-full p-2 select-none flex flex-col justify-start">
      {/* ── Movable Floating Glass Container ── */}
      <section
        className={`w-full rounded-3xl border border-white/15 bg-zinc-950/90 backdrop-blur-3xl shadow-[0_25px_60px_rgba(0,0,0,0.8),0_0_35px_rgba(6,182,212,0.15)] overflow-hidden transition-all duration-300 flex flex-col ${
          expanded ? 'h-[500px]' : 'h-auto'
        }`}
      >
        {/* ── 1. Movable Window Titlebar (Drag Region) ── */}
        <header
          className="px-4 py-3 border-b border-white/10 bg-white/[0.03] flex items-center justify-between cursor-move"
          style={{ WebkitAppRegion: 'drag' } as any}
        >
          <div className="flex items-center gap-2.5">
            <span
              className={`w-2 h-2 rounded-full ${
                connected ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-amber-400 animate-pulse'
              }`}
            />
            <span className="font-mono text-xs font-bold uppercase tracking-wider text-zinc-200">
              Genie Overlay
            </span>
            <span className="text-zinc-600 text-xs">•</span>
            <span className={`text-[11px] font-mono ${statusInfo.color}`}>{statusInfo.label}</span>
          </div>

          {/* Action Window Controls (No-Drag) */}
          <div className="flex items-center gap-1.5" style={{ WebkitAppRegion: 'no-drag' } as any}>
            <button
              type="button"
              onClick={() => {
                const next = !alwaysOnTop;
                setAlwaysOnTop(next);
                getBridge().setAlwaysOnTop?.(next);
              }}
              className={`p-1.5 rounded-lg text-xs transition-all ${
                alwaysOnTop ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'text-zinc-500 hover:text-zinc-300'
              }`}
              title="Toggle Always on Top"
            >
              📌
            </button>
            <button
              type="button"
              onClick={openMain}
              className="p-1.5 rounded-lg text-xs text-zinc-400 hover:text-white hover:bg-white/10 transition-all"
              title="Open Full Genie App"
            >
              ↗
            </button>
            <button
              type="button"
              onClick={closeCompanion}
              className="p-1.5 rounded-lg text-xs text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
              title="Close Companion"
            >
              ✕
            </button>
          </div>
        </header>

        {/* ── 2. Hero Interactive Presence (Movable Body) ── */}
        <div className="p-4 flex items-center gap-4 bg-gradient-to-b from-white/[0.02] to-transparent">
          {/* Mini Glowing Genie Core Orb */}
          <div
            onClick={() => setExpanded(!expanded)}
            className="cursor-pointer hover:scale-105 transition-transform shrink-0"
            title="Click to expand conversation"
          >
            <GenieCoreOrb state={genieState} size={76} />
          </div>

          {/* Dynamic Status / Speech Transcript */}
          <div className="flex-1 min-w-0 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-200">Personal Assistant</span>
              <button
                type="button"
                onClick={() => setExpanded(!expanded)}
                className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 transition"
              >
                {expanded ? '▲ Collapse' : '▼ Chat'}
              </button>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed truncate">
              {liveTranscript ? `"${liveTranscript}"` : 'Ask naturally by voice or type...'}
            </p>
          </div>
        </div>

        {/* ── 3. Quick Action Button Bar ── */}
        <div className="px-4 pb-3 flex items-center justify-between gap-2 border-b border-white/5">
          {/* Voice Talk Button */}
          <button
            type="button"
            onClick={toggleVoice}
            disabled={!connected}
            className={`flex-1 py-2 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition-all shadow-md ${
              isListening
                ? 'bg-gradient-to-r from-cyan-400 to-blue-500 text-white shadow-[0_0_20px_rgba(34,211,238,0.5)] animate-pulse'
                : isBusy
                ? 'bg-gradient-to-r from-rose-500 to-red-600 text-white'
                : 'bg-gradient-to-r from-indigo-500 via-purple-500 to-cyan-500 text-white hover:opacity-95'
            }`}
          >
            <span>{isListening ? '🎙 Listening…' : isBusy ? '⏹ Stop' : '🎙 Tap to Talk'}</span>
          </button>

          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="p-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-xs font-mono transition-all"
            title="Toggle Message Feed"
          >
            💬
          </button>
        </div>

        {/* ── 4. Expandable Dialogue & Composer Drawer ── */}
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="flex-1 flex flex-col min-h-0 bg-black/40 overflow-hidden"
            >
              {/* Message Feed */}
              <div className="flex-1 overflow-y-auto p-4 space-y-2.5 custom-scrollbar text-xs">
                {recentMessages.length === 0 ? (
                  <p className="text-center py-6 text-zinc-500 text-xs">
                    No recent dialogue turns.
                  </p>
                ) : (
                  recentMessages.map((m: any, i: number) => (
                    <div
                      key={m.id || i}
                      className={`p-2.5 rounded-xl leading-relaxed border ${
                        m.role === 'user'
                          ? 'bg-indigo-950/40 border-indigo-500/20 text-indigo-100 ml-4'
                          : 'bg-zinc-900/70 border-white/10 text-zinc-200 mr-4'
                      }`}
                    >
                      <div className="text-[10px] font-mono text-zinc-400 font-semibold mb-0.5">
                        {m.role === 'user' ? 'You' : 'Genie'}
                      </div>
                      <p className="whitespace-pre-wrap break-words">{m.text}</p>
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Text Composer */}
              <div className="p-3 border-t border-white/10 bg-zinc-950/80 flex items-center gap-2">
                <input
                  type="text"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                  placeholder="Type a message or command…"
                  className="flex-1 bg-transparent text-xs text-white placeholder-zinc-500 outline-none px-2 font-medium"
                />
                <button
                  type="button"
                  onClick={send}
                  disabled={!text.trim()}
                  className="p-2 rounded-xl bg-cyan-500 text-black font-semibold hover:bg-cyan-400 disabled:opacity-30 transition-all"
                >
                  <SendIcon size={12} />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </section>
    </main>
  );
}
