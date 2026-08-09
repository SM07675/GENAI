/**
 * DesktopCompanionOverlay.tsx — Standalone Floating Desktop Companion Overlay.
 *
 * Designed for the dedicated Electron overlay BrowserWindow.
 *
 * Features:
 * - 100% Transparent background (no rectangular container card by default)
 * - Minimal, high-aesthetic animated 2D avatar presence
 * - Non-intrusive focus management (never steals focus while user types in Chrome/VS Code)
 * - Dynamic Click-Through support (passes mouse events through transparent background)
 * - Draggable with position persistence & multi-monitor boundary safety
 * - Hover controls bar (🎤 Mic, 📷 Camera, 👁 Quick Look, ⚙ Open App, × Hide)
 * - Click to expand floating interactive card
 * - Right-click desktop context menu
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import { useCompanionStore } from '../../store/companionStore';
import { useCompanion } from '../../hooks/useCompanion';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useAudioPlayer } from '../../hooks/useAudioPlayer';
import GenieFace from '../GenieFace/GenieFace';
import PrivacyPanel from './PrivacyPanel';
import VoiceWaveform from './VoiceWaveform';
import ContextStatusBar from './ContextStatusBar';
import CameraCompanion from './CameraCompanion';
import ToolFeedback from './ToolFeedback';

export default function DesktopCompanionOverlay() {
  const genieState = useAppStore((s) => s.genieState);
  const liveTranscript = useAppStore((s) => s.liveTranscript);
  const wsStatus = useAppStore((s) => s.wsStatus);
  const companion = useCompanionStore();
  const { startCompanion, stopCompanion, pauseCompanion, resumeCompanion, requestQuickLook } = useCompanion();

  // Local state for standalone companion overlay
  const [isExpanded, setIsExpanded] = useState(false);
  const [showHoverControls, setShowHoverControls] = useState(false);
  const [showContextMenu, setShowContextMenu] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const [positionMode, setPositionMode] = useState<'free' | 'top-right' | 'bottom-right' | 'top-left' | 'bottom-left'>('free');

  const audioRef = useRef<HTMLAudioElement>(null);
  const hoverTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Audio player & WebSocket for standalone overlay mode
  const { queueAudioChunk, stopAudio, notifyTtsDone } = useAudioPlayer(audioRef);
  const { sendText } = useWebSocket('1234', queueAudioChunk, stopAudio, notifyTtsDone);

  const isConnected = wsStatus === 'authed' || wsStatus === 'connected';

  // ── Set body class to transparent overlay ────────────────────────────────
  useEffect(() => {
    document.body.classList.add('companion-overlay-mode');
    return () => {
      document.body.classList.remove('companion-overlay-mode');
    };
  }, []);

  // ── Mouse hover & click-through IPC handling ─────────────────────────────
  const handleMouseEnter = useCallback(() => {
    if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
    setShowHoverControls(true);

    const genie = (window as any).genie;
    if (genie && genie.isElectron) {
      genie.setCompanionInteractive?.(true);
      genie.setCompanionClickThrough?.(false);
    }
  }, []);

  const handleMouseLeave = useCallback(() => {
    hoverTimerRef.current = setTimeout(() => {
      setShowHoverControls(false);
      setShowContextMenu(false);

      const genie = (window as any).genie;
      if (genie && genie.isElectron && !isExpanded) {
        genie.setCompanionClickThrough?.(true);
      }
    }, 1200);
  }, [isExpanded]);

  // ── Positioning Mode preset applier ──────────────────────────────────────
  const applyPositionPreset = useCallback((preset: 'free' | 'top-right' | 'bottom-right' | 'top-left' | 'bottom-left') => {
    setPositionMode(preset);
    if (preset === 'free') return;

    const screenW = window.screen.availWidth || window.innerWidth;
    const screenH = window.screen.availHeight || window.innerHeight;

    let targetX = 20;
    let targetY = 20;

    switch (preset) {
      case 'top-right':
        targetX = screenW - 160;
        targetY = 40;
        break;
      case 'bottom-right':
        targetX = screenW - 160;
        targetY = screenH - 220;
        break;
      case 'top-left':
        targetX = 40;
        targetY = 40;
        break;
      case 'bottom-left':
        targetX = 40;
        targetY = screenH - 220;
        break;
    }

    companion.setPosition({ x: targetX, y: targetY });
    const genie = (window as any).genie;
    if (genie && genie.isElectron) {
      genie.setCompanionPosition?.(targetX, targetY);
    }
  }, [companion]);

  // ── Handle focus main app ────────────────────────────────────────────────
  const handleOpenMainApp = useCallback(() => {
    const genie = (window as any).genie;
    if (genie && genie.isElectron) {
      genie.focusMain?.();
    }
  }, []);

  return (
    <div
      className="relative w-screen h-screen overflow-hidden select-none pointer-events-none"
      style={{ background: 'transparent' }}
    >
      {/* Hidden audio element for TTS playback */}
      <audio ref={audioRef} style={{ display: 'none' }} />

      {/* Main Floating Presence Avatar Container */}
      <div
        className="pointer-events-auto absolute"
        style={{
          left: companion.position.x,
          top: companion.position.y,
          zIndex: 9999,
        }}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onContextMenu={(e) => {
          e.preventDefault();
          setShowContextMenu((v) => !v);
        }}
      >
        {/* Proactive / Live Transcript Callout Bubble */}
        <AnimatePresence>
          {liveTranscript && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.9 }}
              style={{
                position: 'absolute',
                bottom: '105%',
                left: '50%',
                transform: 'translateX(-50%)',
                marginBottom: 8,
                background: 'rgba(8,12,28,0.95)',
                border: '1px solid rgba(94,234,212,0.4)',
                borderRadius: 16,
                padding: '8px 14px',
                color: '#e2e8f0',
                fontSize: 12,
                fontFamily: "'Inter', sans-serif",
                maxWidth: 240,
                textAlign: 'center',
                backdropFilter: 'blur(16px)',
                boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
              }}
            >
              {liveTranscript}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Hover Action Controls Bar (🎤 📷 👁 ⚙ ×) */}
        <AnimatePresence>
          {showHoverControls && !isExpanded && (
            <motion.div
              initial={{ opacity: 0, y: 6, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 6, scale: 0.9 }}
              transition={{ duration: 0.15 }}
              style={{
                position: 'absolute',
                bottom: -36,
                left: '50%',
                transform: 'translateX(-50%)',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: '4px 8px',
                borderRadius: 99,
                background: 'rgba(6,10,24,0.92)',
                border: '1px solid rgba(255,255,255,0.12)',
                backdropFilter: 'blur(16px)',
                boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
              }}
            >
              <ControlButton title="Quick Look (Ctrl+Shift+G)" onClick={() => requestQuickLook()}>
                👁
              </ControlButton>
              <ControlButton title="Camera Vision" onClick={() => setShowCamera((v) => !v)}>
                📷
              </ControlButton>
              <ControlButton title="Open Main App" onClick={handleOpenMainApp}>
                ⚙
              </ControlButton>
              <ControlButton title="Hide Companion" onClick={stopCompanion} danger>
                ×
              </ControlButton>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Floating Avatar Core (Minimal Desktop Presence) */}
        <motion.div
          style={{
            cursor: 'pointer',
            filter: isConnected ? 'drop-shadow(0 0 16px rgba(94,234,212,0.35))' : 'drop-shadow(0 0 16px rgba(245,158,11,0.35))',
          }}
          whileHover={{ scale: 1.06 }}
          whileTap={{ scale: 0.94 }}
          onClick={() => setIsExpanded((v) => !v)}
        >
          <GenieFace size={isExpanded ? 130 : 95} showBody={false} minimal={!isExpanded} />
        </motion.div>

        {/* Minimal Presence Label */}
        {!isExpanded && (
          <div style={{
            textAlign: 'center',
            marginTop: 2,
            color: '#5EEAD4',
            fontSize: 10,
            fontWeight: 700,
            fontFamily: "'Inter', sans-serif",
            letterSpacing: '0.06em',
            textShadow: '0 2px 8px rgba(0,0,0,0.8)',
          }}>
            Genie
          </div>
        )}

        {/* Expanded Desktop Card */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 10 }}
              style={{
                position: 'absolute',
                top: '110%',
                left: '50%',
                transform: 'translateX(-50%)',
                width: 300,
                background: 'rgba(5,8,20,0.96)',
                border: '1.5px solid rgba(94,234,212,0.4)',
                borderRadius: 24,
                padding: 16,
                backdropFilter: 'blur(24px)',
                boxShadow: '0 24px 64px rgba(0,0,0,0.7), 0 0 40px rgba(94,234,212,0.15)',
                fontFamily: "'Inter', sans-serif",
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#5EEAD4', boxShadow: '0 0 8px #5EEAD4' }} />
                  <span style={{ color: '#e2e8f0', fontSize: 13, fontWeight: 700 }}>
                    Genie AI Companion
                  </span>
                </div>
                <button
                  onClick={() => setIsExpanded(false)}
                  style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 14 }}
                >
                  ✕
                </button>
              </div>

              {/* Privacy Panel */}
              <PrivacyPanel screenAware={companion.screenAware} micActive={companion.micActive} cameraActive={companion.cameraActive} stateColor="#5EEAD4" />

              {/* Waveform */}
              <div style={{ display: 'flex', justifyContent: 'center', margin: '10px 0' }}>
                <VoiceWaveform isActive={genieState === 'speaking' || genieState === 'listening'} color="#5EEAD4" width={180} height={32} />
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 12 }}>
                <ActionButton icon="👁" label="Quick Look" onClick={() => requestQuickLook()} />
                <ActionButton icon="📷" label="Camera" onClick={() => setShowCamera(true)} />
                <ActionButton icon="⚙" label="Main App" onClick={handleOpenMainApp} />
                <ActionButton icon="⏸" label={companion.mode === 'paused' ? 'Resume' : 'Pause'} onClick={companion.mode === 'paused' ? resumeCompanion : pauseCompanion} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Custom Context Menu */}
        <AnimatePresence>
          {showContextMenu && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              style={{
                position: 'absolute',
                top: 0,
                left: '105%',
                background: 'rgba(8,12,28,0.98)',
                border: '1px solid rgba(99,102,241,0.3)',
                borderRadius: 16,
                padding: '6px 0',
                minWidth: 170,
                backdropFilter: 'blur(20px)',
                boxShadow: '0 16px 40px rgba(0,0,0,0.6)',
                zIndex: 10000,
                fontFamily: "'Inter', sans-serif",
              }}
            >
              <ContextMenuItem icon="👁" label="Quick Look (Ctrl+Shift+G)" onClick={() => { requestQuickLook(); setShowContextMenu(false); }} />
              <ContextMenuItem icon="📌" label="Position: Top-Right" onClick={() => { applyPositionPreset('top-right'); setShowContextMenu(false); }} />
              <ContextMenuItem icon="📌" label="Position: Bottom-Right" onClick={() => { applyPositionPreset('bottom-right'); setShowContextMenu(false); }} />
              <ContextMenuItem icon="📌" label="Position: Free Drag" onClick={() => { applyPositionPreset('free'); setShowContextMenu(false); }} />
              <ContextMenuItem icon="⚙" label="Open Main App" onClick={() => { handleOpenMainApp(); setShowContextMenu(false); }} />
              <ContextMenuItem icon="✕" label="Exit Companion" onClick={() => { stopCompanion(); setShowContextMenu(false); }} danger />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Tool Execution Feedback Overlay */}
      <ToolFeedback />

      {/* Camera Vision Modal */}
      <CameraCompanion isOpen={showCamera} onClose={() => setShowCamera(false)} />
    </div>
  );
}

function ControlButton({ title, onClick, children, danger = false }: { title: string; onClick: () => void; children: React.ReactNode; danger?: boolean }) {
  return (
    <motion.button
      whileHover={{ scale: 1.15 }}
      whileTap={{ scale: 0.9 }}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      title={title}
      style={{
        width: 24,
        height: 24,
        borderRadius: '50%',
        background: danger ? 'rgba(248,113,113,0.2)' : 'rgba(255,255,255,0.08)',
        border: danger ? '1px solid rgba(248,113,113,0.4)' : '1px solid rgba(255,255,255,0.12)',
        color: danger ? '#f87171' : '#e2e8f0',
        fontSize: 11,
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {children}
    </motion.button>
  );
}

function ActionButton({ icon, label, onClick }: { icon: string; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '8px 10px',
        borderRadius: 12,
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        color: '#e2e8f0',
        fontSize: 11,
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.04)')}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function ContextMenuItem({ icon, label, onClick, danger = false }: { icon: string; label: string; onClick: () => void; danger?: boolean }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        width: '100%',
        padding: '8px 14px',
        background: 'transparent',
        border: 'none',
        color: danger ? '#f87171' : '#cbd5e1',
        fontSize: 11,
        fontWeight: 500,
        textAlign: 'left',
        cursor: 'pointer',
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = danger ? 'rgba(248,113,113,0.1)' : 'rgba(255,255,255,0.06)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </button>
  );
}
