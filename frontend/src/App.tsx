/**
 * App.tsx — Genie AI Operating System Spatial Desktop Shell.
 *
 * Designed from scratch with Apple VisionOS / macOS Sonoma aesthetics:
 * - Top Dynamic Island (Status, Audio Waves, Telemetry, Quick Tools)
 * - Hero AI Core & Dynamic Subtitle Aura
 * - macOS / iOS Dynamic Stacked Stage Deck (Missions, Dialogue, Perception, Memory)
 * - Floating Luxury Glass Command Dock (Multi-mode, Reactive Voice, Attachments)
 * - Full-screen Mission Control Room (TaskWorkspace modal)
 * - Global ⌘K Command Palette
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { useAppStore } from './store/appStore';
import { useCompanionStore } from './store/companionStore';
import { useTaskStore } from './store/taskStore';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioPlayer } from './hooks/useAudioPlayer';
import { useVoicePipeline } from './hooks/useVoicePipeline';
import { useCompanion } from './hooks/useCompanion';
import { resumeAnalyser } from './services/audioAnalyser';
import { ChatPanel } from './components/ChatPanel';
import BackgroundPlayer from './components/BackgroundPlayer';
import CompanionDashboard from './components/Companion/CompanionDashboard';
import CameraCompanion from './components/Companion/CameraCompanion';
import DesktopCompanionOverlay from './components/Companion/DesktopCompanionOverlay';
import HomeView from './components/MainApp/HomeView';
import CompanionConfigView from './components/MainApp/CompanionConfigView';
import MemoryView from './components/MainApp/MemoryView';
import ProjectsView from './components/MainApp/ProjectsView';
import SettingsView from './components/MainApp/SettingsView';
import { TasksView } from './components/Tasks/TasksView';
import { TaskWorkspace } from './components/TaskWorkspace/TaskWorkspace';
import { GlobalCommandBar } from './components/CommandBar/GlobalCommandBar';
import { FloatingDock } from './components/CommandBar/FloatingDock';
import { DynamicIsland } from './components/Navigation/DynamicIsland';
import { FirstRunWalkthrough } from './components/FirstRun/FirstRunWalkthrough';
import { motion, AnimatePresence } from 'framer-motion';

function GenieApp({ pin }: { pin: string }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [activeView, setActiveView] = useState<string>('home');
  const [showChatPanel, setShowChatPanel] = useState(false);
  const [showDashboard, setShowDashboard] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const [isCommandBarOpen, setIsCommandBarOpen] = useState(false);
  const [isSkyTheme, setIsSkyTheme] = useState(false);

  // Dedicated Electron overlay check
  const genie = (typeof window !== 'undefined' && (window as any).genie) || {};
  const isDedicatedElectronOverlay =
    genie.isCompanionOverlay ||
    (typeof window !== 'undefined' && window.location.search.includes('companion=1'));

  if (isDedicatedElectronOverlay) {
    return <DesktopCompanionOverlay />;
  }

  // Audio Player & Full WebSocket Bridge
  const { queueAudioChunk, stopAudio, notifyTtsDone } = useAudioPlayer(audioRef);
  const { sendText, sendImage, sendGoal, sendTaskAction, cancel } = useWebSocket(
    pin,
    queueAudioChunk,
    stopAudio,
    notifyTtsDone
  );
  useVoicePipeline();

  const wsStatus = useAppStore((s) => s.wsStatus);
  const genieState = useAppStore((s) => s.genieState);
  const companion = useCompanionStore();
  const { startCompanion, stopCompanion } = useCompanion();

  const isTaskWorkspaceOpen = useTaskStore((s) => s.isTaskWorkspaceOpen);
  const openTaskWorkspace = useTaskStore((s) => s.openTaskWorkspace);

  const isBackendConnected = wsStatus === 'authed' || wsStatus === 'connected';

  // Global Keyboard Shortcuts (Ctrl+K / Cmd+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsCommandBarOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // One-time user gesture audio unlock (ensures browser doesn't block incoming TTS audio)
  useEffect(() => {
    const unlockAudio = () => {
      resumeAnalyser();
      if (audioRef.current) {
        audioRef.current.play().catch(() => {});
        audioRef.current.pause();
      }
      window.removeEventListener('pointerdown', unlockAudio);
      window.removeEventListener('keydown', unlockAudio);
    };
    window.addEventListener('pointerdown', unlockAudio);
    window.addEventListener('keydown', unlockAudio);
    return () => {
      window.removeEventListener('pointerdown', unlockAudio);
      window.removeEventListener('keydown', unlockAudio);
    };
  }, []);

  // Sync state with Electron Companion
  useEffect(() => {
    const genie = (window as any).genie;
    if (!genie?.isElectron || genie.isCompanionOverlay) return;

    const publish = () => {
      const app = useAppStore.getState();
      const comp = useCompanionStore.getState();
      genie.publishCompanionState?.({
        app: {
          messages: app.messages.slice(-30),
          genieState: app.genieState,
          liveTranscript: app.liveTranscript,
          wsStatus: app.wsStatus,
          amplitude: app.amplitude,
          voiceState: app.voiceState,
          isTTSPlaying: app.isTTSPlaying,
          systemNote: app.systemNote,
          sessionId: app.sessionId,
          visionSupported: app.visionSupported,
          visionReason: app.visionReason,
        },
        companion: {
          mode: comp.mode,
          subMode: comp.subMode,
          screenAware: comp.screenAware,
          micActive: comp.micActive,
          cameraActive: comp.cameraActive,
          overlayState: comp.overlayState,
        },
      });
    };

    publish();
    const unApp = useAppStore.subscribe(publish);
    const unCompanion = useCompanionStore.subscribe(publish);
    const unAction = genie.onCompanionAction?.((action: any) => {
      const ws = useAppStore.getState().ws;
      switch (action?.type) {
        case 'text': sendText(action.text); break;
        case 'goal': sendGoal(action.text); break;
        case 'image': sendImage(action.payload || {}); break;
        case 'manual_wake':
          if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'manual_wake' }));
          break;
        case 'cancel': cancel(); break;
        case 'quick_look':
          if (ws?.readyState === WebSocket.OPEN)
            ws.send(JSON.stringify({ type: 'companion_quick_look', text: action.text || undefined }));
          break;
        case 'pause':
          if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'companion_pause' }));
          break;
        case 'resume':
          if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'companion_resume' }));
          break;
        case 'open_settings':
          setActiveView('settings');
          break;
      }
    });

    return () => {
      unApp();
      unCompanion();
      unAction?.();
    };
  }, [sendText, sendGoal, sendImage, cancel]);

  const handleToggleCompanion = useCallback(() => {
    if (companion.mode === 'active') {
      stopCompanion();
    } else {
      startCompanion('general');
    }
  }, [companion.mode, startCompanion, stopCompanion]);

  const handleTriggerQuickLook = useCallback(() => {
    const ws = useAppStore.getState().ws;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'companion_quick_look' }));
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setIsSkyTheme((prev) => {
      const next = !prev;
      document.documentElement.setAttribute('data-theme', next ? 'sky' : 'nebula');
      return next;
    });
  }, []);

  return (
    <main className="relative w-screen h-screen overflow-hidden flex flex-col justify-between bg-[#030409] text-white select-none">
      {/* Hidden TTS & Background Player */}
      <audio ref={audioRef} style={{ display: 'none' }} />
      <BackgroundPlayer />

      {/* Spatial Ambient Canvas Layer */}
      <div className="spatial-canvas">
        <div className="spatial-grid" />
      </div>

      {/* ── 1. Top Dynamic Island Header ── */}
      <div className="relative z-30 pt-1">
        <DynamicIsland
          onTriggerQuickLook={handleTriggerQuickLook}
          onToggleCamera={() => setShowCamera((v) => !v)}
          isCameraOpen={showCamera}
          onToggleChat={() => setShowChatPanel((v) => !v)}
          isChatOpen={showChatPanel}
          onOpenCommandBar={() => setIsCommandBarOpen(true)}
          isSkyTheme={isSkyTheme}
          onToggleTheme={toggleTheme}
        />
      </div>

      {/* ── 2. Central Spatial Assistant Workspace ── */}
      <section className="relative z-20 flex-1 overflow-hidden px-4">
        {activeView === 'home' && (
          <HomeView
            onNavigate={(p) => setActiveView(p)}
            genieState={genieState}
            onToggleCompanion={handleToggleCompanion}
            onQuickLook={handleTriggerQuickLook}
            onOpenCamera={() => setShowCamera(true)}
            onOpenChat={() => setShowChatPanel(true)}
            onOpenWorkspace={(id) => openTaskWorkspace(id)}
          />
        )}

        {activeView === 'tasks' && (
          <div className="h-full relative">
            <div className="flex items-center justify-between px-6 py-2">
              <button
                onClick={() => setActiveView('home')}
                className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1.5 font-semibold"
              >
                ← Back to Core Stage
              </button>
            </div>
            <TasksView
              onOpenWorkspace={(id) => openTaskWorkspace(id)}
              onSendGoal={(goal) => sendGoal(goal)}
            />
          </div>
        )}

        {activeView === 'companion' && (
          <div className="h-full relative">
            <div className="flex items-center justify-between px-6 py-2">
              <button
                onClick={() => setActiveView('home')}
                className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1.5 font-semibold"
              >
                ← Back to Core Stage
              </button>
            </div>
            <CompanionConfigView />
          </div>
        )}

        {activeView === 'projects' && (
          <div className="h-full relative">
            <div className="flex items-center justify-between px-6 py-2">
              <button
                onClick={() => setActiveView('home')}
                className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1.5 font-semibold"
              >
                ← Back to Core Stage
              </button>
            </div>
            <ProjectsView />
          </div>
        )}

        {activeView === 'memory' && (
          <div className="h-full relative">
            <div className="flex items-center justify-between px-6 py-2">
              <button
                onClick={() => setActiveView('home')}
                className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1.5 font-semibold"
              >
                ← Back to Core Stage
              </button>
            </div>
            <MemoryView />
          </div>
        )}

        {activeView === 'settings' && (
          <div className="h-full relative">
            <div className="flex items-center justify-between px-6 py-2">
              <button
                onClick={() => setActiveView('home')}
                className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1.5 font-semibold"
              >
                ← Back to Core Stage
              </button>
            </div>
            <SettingsView />
          </div>
        )}

        {/* Full Autonomous Task Workspace Modal / Overlay */}
        <AnimatePresence>
          {isTaskWorkspaceOpen && (
            <motion.div
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={{ duration: 0.25, ease: 'easeOut' }}
              className="absolute inset-0 z-40 p-3"
            >
              <TaskWorkspace onSendTaskAction={sendTaskAction} />
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      {/* ── 3. Bottom Floating Command Dock ── */}
      <div className="relative z-30 pb-4 pt-1">
        <FloatingDock
          onSendGoal={(goal) => sendGoal(goal)}
          onSendText={(text) => sendText(text)}
          onTriggerCamera={() => setShowCamera(true)}
          isBackendConnected={isBackendConnected}
        />
      </div>

      {/* ── Global Overlays & Drawers ── */}
      <GlobalCommandBar
        isOpen={isCommandBarOpen}
        onClose={() => setIsCommandBarOpen(false)}
        onSendGoal={(goal) => sendGoal(goal)}
        onSendText={(text) => sendText(text)}
      />

      {showChatPanel && (
        <ChatPanel
          isOpen={showChatPanel}
          onClose={() => setShowChatPanel(false)}
          onSendText={sendText}
        />
      )}

      {showDashboard && <CompanionDashboard isOpen={showDashboard} onClose={() => setShowDashboard(false)} />}
      {showCamera && <CameraCompanion isOpen={showCamera} onClose={() => setShowCamera(false)} />}
      <FirstRunWalkthrough onComplete={() => {}} />
    </main>
  );
}

export default function App() {
  const [pin, setPin] = useState<string>('1234');

  useEffect(() => {
    const fetchDesktopPin = async () => {
      try {
        const desktopPin = await (window as any).genie?.getDesktopPin?.();
        if (desktopPin) {
          setPin(desktopPin);
        }
      } catch (err) {
        console.debug('Failed to query desktop PIN:', err);
      }
    };
    fetchDesktopPin();
  }, []);

  return <GenieApp pin={pin} />;
}
