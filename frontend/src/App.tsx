/**
 * App.tsx — Genie AI Desktop Assistant Main Application.
 *
 * Architecture:
 * - Sky Blue Light Glassmorphism UI (Main Application Window)
 * - Standalone Transparent Desktop Overlay Window (DesktopCompanionOverlay)
 * - Shared Genie Core (WebSocket, LLM, STT, Edge TTS, Memory, Vision)
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { useAppStore } from './store/appStore';
import { useCompanionStore } from './store/companionStore';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioPlayer } from './hooks/useAudioPlayer';
import { useVoicePipeline } from './hooks/useVoicePipeline';
import { ChatPanel } from './components/ChatPanel';
import MicrophoneButton from './components/MicrophoneButton';
import MinimalControls from './components/MinimalControls';
import BackgroundPlayer from './components/BackgroundPlayer';
import CompanionWindow from './components/Companion/CompanionWindow';
import CompanionDashboard from './components/Companion/CompanionDashboard';
import CameraCompanion from './components/Companion/CameraCompanion';
import DesktopCompanionOverlay from './components/Companion/DesktopCompanionOverlay';
import ToolFeedback from './components/Companion/ToolFeedback';
import HomeView from './components/MainApp/HomeView';
import CompanionConfigView from './components/MainApp/CompanionConfigView';
import MemoryView from './components/MainApp/MemoryView';
import ProjectsView from './components/MainApp/ProjectsView';
import SettingsView from './components/MainApp/SettingsView';
import { FirstRunWalkthrough } from './components/FirstRun/FirstRunWalkthrough';
import { motion, AnimatePresence } from 'framer-motion';

// ── Sub-app: authenticated, backend wired ─────────────────────────────────────
function GenieApp({ pin }: { pin: string }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [activeNav, setActiveNav] = useState<string>('home');
  const [showChatPanel, setShowChatPanel] = useState(false);
  const [showTextInput, setShowTextInput] = useState(false);
  const [showDashboard, setShowDashboard] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const [textInput, setTextInput] = useState('');

  // ── Detect dedicated Electron overlay window ──────────────────────────────
  const genie = (typeof window !== 'undefined' && (window as any).genie) || {};
  const isDedicatedElectronOverlay =
    genie.isCompanionOverlay ||
    (typeof window !== 'undefined' && window.location.search.includes('companion=1'));

  if (isDedicatedElectronOverlay) {
    return <DesktopCompanionOverlay />;
  }

  // ── Audio player: receives TTS chunks from useWebSocket ──────────────────
  const { queueAudioChunk, stopAudio, notifyTtsDone } = useAudioPlayer(audioRef);

  // ── WebSocket: connects to backend, routes all messages ──────────────────
  const { sendText } = useWebSocket(pin, queueAudioChunk, stopAudio, notifyTtsDone);

  // ── Voice pipeline ────────────────────────────────────────────────────────
  const { toggleListening } = useVoicePipeline();

  // ── Store hooks ───────────────────────────────────────────────────────────
  const genieState = useAppStore((s) => s.genieState);
  const liveTranscript = useAppStore((s) => s.liveTranscript);
  const wsStatus = useAppStore((s) => s.wsStatus);
  const companion = useCompanionStore();

  const isBackendConnected = wsStatus === 'authed' || wsStatus === 'connected';

  const handleSendText = useCallback(
    (textToSend?: string) => {
      const text = (textToSend || textInput).trim();
      if (!text) return;
      sendText(text);
      setTextInput('');
      setShowTextInput(false);
    },
    [textInput, sendText]
  );

  const handleTriggerQuickLook = () => {
    sendText("what's wrong on my screen");
  };

  const handleToggleCompanion = () => {
    companion.setMode(companion.mode === 'off' ? 'active' : 'off');
  };

  return (
    <main className="relative w-screen h-screen overflow-hidden bg-sky-50 text-slate-900 select-none flex">
      {/* Hidden audio element for TTS playback */}
      <audio ref={audioRef} style={{ display: 'none' }} />

      {/* Hidden background audio player */}
      <BackgroundPlayer />

      {/* Animated Sky Blue Backdrop */}
      <div className="genie-bg-sky pointer-events-none" />

      {/* ── Left Sidebar Navigation (§44) ─────────────────────────────────── */}
      <aside className="relative z-30 w-64 sky-glass border-r border-sky-200/60 p-5 flex flex-col justify-between shadow-lg">
        <div className="space-y-6">
          {/* Logo & Status Badge */}
          <div className="flex items-center gap-3 px-2">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-sky-500 to-cyan-400 flex items-center justify-center text-white text-xl font-bold shadow-md shadow-sky-500/25">
              ✦
            </div>
            <div>
              <div className="text-base font-bold text-slate-900 tracking-tight">Genie AI</div>
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-sky-700">
                <span className={`w-2 h-2 rounded-full ${isBackendConnected ? 'bg-sky-500 animate-pulse' : 'bg-amber-500'}`} />
                <span>{isBackendConnected ? 'Connected' : 'Connecting'}</span>
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="space-y-1">
            <NavItem icon="⌂" label="Home" active={activeNav === 'home'} onClick={() => setActiveNav('home')} />
            <NavItem icon="✨" label="Companion" active={activeNav === 'companion'} onClick={() => setActiveNav('companion')} tag={companion.mode.toUpperCase()} />
            <NavItem icon="▣" label="Projects" active={activeNav === 'projects'} onClick={() => setActiveNav('projects')} />
            <NavItem icon="🧠" label="Memory" active={activeNav === 'memory'} onClick={() => setActiveNav('memory')} />
            <NavItem icon="⚙" label="Settings" active={activeNav === 'settings'} onClick={() => setActiveNav('settings')} />
          </nav>
        </div>

        {/* Sidebar Footer Controls */}
        <div className="space-y-3 border-t border-sky-200/60 pt-4">
          <button
            onClick={handleToggleCompanion}
            className={`w-full py-2.5 px-3 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 shadow-sm ${
              companion.mode !== 'off'
                ? 'bg-sky-500 text-white shadow-sky-500/20 hover:bg-sky-600'
                : 'bg-white border border-sky-200 text-slate-700 hover:bg-sky-50'
            }`}
          >
            <span>✨</span>
            <span>Desktop Overlay: {companion.mode.toUpperCase()}</span>
          </button>

          <div className="flex items-center justify-between text-[11px] font-medium text-slate-500 px-1">
            <span>Genie OS v6</span>
            <MinimalControls embedded />
          </div>
        </div>
      </aside>

      {/* ── Main Workspace Area ────────────────────────────────────────────── */}
      <section className="relative z-20 flex-1 flex flex-col justify-between overflow-hidden">
        {/* Top Action Bar */}
        <header className="p-5 flex items-center justify-between border-b border-sky-200/40 sky-glass-subtle">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold text-sky-800 uppercase tracking-wide">
              {activeNav}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <HeaderButton icon="👁" label="Quick Look" onClick={handleTriggerQuickLook} title="Quick Look (Ctrl+Shift+G)" />
            <HeaderButton icon="📷" label="Camera" onClick={() => setShowCamera((v) => !v)} active={showCamera} />
            <HeaderButton icon="📊" label="Dashboard" onClick={() => setShowDashboard((v) => !v)} active={showDashboard} />
            <HeaderButton icon="💬" label="Chat" onClick={() => setShowChatPanel((v) => !v)} active={showChatPanel} />
          </div>
        </header>

        {/* Dynamic Page Views */}
        {activeNav === 'home' && <HomeView onNavigate={(p) => setActiveNav(p)} />}
        {activeNav === 'companion' && <CompanionConfigView />}
        {activeNav === 'projects' && <ProjectsView />}
        {activeNav === 'memory' && <MemoryView />}
        {activeNav === 'settings' && <SettingsView />}

        {/* Bottom Floating Control Dock */}
        <footer className="p-4 flex items-center justify-between sky-glass-subtle border-t border-sky-200/40">
          <div className="text-xs text-slate-500 font-medium">
            Press <span className="text-sky-600 font-bold">Ctrl+Shift+G</span> for Quick Look
          </div>

          <MicrophoneButton />

          <button
            onClick={() => setShowTextInput((v) => !v)}
            className={`px-3 py-1.5 rounded-xl border text-xs font-semibold backdrop-blur-xl transition-all flex items-center gap-1.5 ${
              showTextInput
                ? 'bg-sky-500 text-white border-sky-500'
                : 'bg-white/80 border-sky-200 text-slate-700 hover:bg-white'
            }`}
          >
            <span>✍</span>
            <span>Type Message</span>
          </button>
        </footer>
      </section>

      {/* Floating Text Input Bar */}
      <AnimatePresence>
        {showTextInput && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="fixed bottom-20 left-1/2 -translate-x-1/2 z-40 w-full max-w-md px-4"
          >
            <div className="flex items-center gap-3 rounded-2xl p-3 sky-glass shadow-2xl">
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendText()}
                placeholder="Ask Genie anything…"
                autoFocus
                className="flex-1 bg-transparent outline-none border-none text-xs font-medium text-slate-900 placeholder:text-slate-400"
              />
              <button
                onClick={() => handleSendText()}
                className="px-4 py-1.5 rounded-xl bg-sky-500 text-white text-xs font-bold hover:bg-sky-600 transition-all shadow-sm"
              >
                Send
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Side Chat Drawer */}
      <ChatPanel
        isOpen={showChatPanel}
        onClose={() => setShowChatPanel(false)}
        onSendText={(txt) => handleSendText(txt)}
      />

      {/* First-Run Walkthrough */}
      <FirstRunWalkthrough />

      {/* Standalone / Web Companion Overlay Router */}
      <CompanionWindow />

      {/* Tool Execution Feedback Overlay */}
      <ToolFeedback />

      {/* Companion Dashboard Slide-In Panel */}
      <CompanionDashboard isOpen={showDashboard} onClose={() => setShowDashboard(false)} />

      {/* Camera Vision Modal */}
      <CameraCompanion isOpen={showCamera} onClose={() => setShowCamera(false)} />
    </main>
  );
}

function NavItem({ icon, label, active, onClick, tag }: { icon: string; label: string; active: boolean; onClick: () => void; tag?: string }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between p-2.5 rounded-xl text-xs font-bold transition-all ${
        active
          ? 'bg-sky-500 text-white shadow-md shadow-sky-500/20'
          : 'text-slate-700 hover:bg-sky-100/60'
      }`}
    >
      <div className="flex items-center gap-2.5">
        <span className="text-sm">{icon}</span>
        <span>{label}</span>
      </div>
      {tag && (
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${active ? 'bg-white/20 text-white' : 'bg-sky-100 text-sky-700'}`}>
          {tag}
        </span>
      )}
    </button>
  );
}

function HeaderButton({ icon, label, onClick, active = false, title }: { icon: string; label: string; onClick: () => void; active?: boolean; title?: string }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={`px-3 py-1.5 rounded-xl border text-xs font-semibold backdrop-blur-xl transition-all flex items-center gap-1.5 ${
        active
          ? 'bg-sky-500 text-white border-sky-500 shadow-sm'
          : 'bg-white/80 border-sky-200 text-slate-700 hover:bg-white'
      }`}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

// ── Root: Auto-pin entry ──────────────────────────────────────────────────────
export default function App() {
  const [pin, setPin] = useState<string | null>('1234');

  return <GenieApp pin={pin || '1234'} />;
}
