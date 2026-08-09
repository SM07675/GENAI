/**
 * CompanionMode.tsx — The Dedicated Companion Mode Experience.
 *
 * This is NOT a chat screen. This is a persistent living companion.
 *
 * Display modes:
 *   FULL      — large avatar center stage, full context panel
 *   FLOATING  — small draggable orb with avatar
 *   MINI      — tiny orb, minimal footprint
 *   INVISIBLE — voice-only, no visible UI
 *
 * Always-on-top when in Electron (handled by main.cjs overlay window).
 * In browser: highest z-index fixed overlay.
 */
import React, {
  useState,
  useCallback,
  useRef,
  useEffect,
} from 'react';
import { motion, AnimatePresence, useDragControls } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import { useCompanionStore } from '../../store/companionStore';
import { useCompanion } from '../../hooks/useCompanion';
import GenieFace from '../GenieFace/GenieFace';
import PrivacyPanel from './PrivacyPanel';
import VoiceWaveform from './VoiceWaveform';
import ContextStatusBar from './ContextStatusBar';
import ProactiveBubble from './ProactiveBubble';

// ── Display mode sizes ────────────────────────────────────────────────────────

const MODE_CONFIG = {
  full: {
    avatarSize: 240,
    showBody: true,
    showContext: true,
    showWaveform: true,
    panelW: 480,
    panelH: 'auto',
    borderRadius: 32,
  },
  floating: {
    avatarSize: 110,
    showBody: false,
    showContext: false,
    showWaveform: true,
    panelW: 150,
    panelH: 'auto',
    borderRadius: 99,
  },
  mini: {
    avatarSize: 52,
    showBody: false,
    showContext: false,
    showWaveform: false,
    panelW: 72,
    panelH: 72,
    borderRadius: 99,
  },
  invisible: {
    avatarSize: 0,
    showBody: false,
    showContext: false,
    showWaveform: false,
    panelW: 0,
    panelH: 0,
    borderRadius: 99,
  },
} as const;

type DisplayMode = keyof typeof MODE_CONFIG;

// ── State → color mapping ──────────────────────────────────────────────────

const STATE_COLORS: Record<string, string> = {
  idle:              '#5EEAD4',
  sleeping:          '#6D28D9',
  waking:            '#F59E0B',
  listening:         '#22D3EE',
  follow_up_listening:'#22D3EE',
  transcribing:      '#818CF8',
  thinking:          '#818CF8',
  executing:         '#818CF8',
  speaking:          '#34D399',
  success:           '#F472B6',
  error:             '#F87171',
  interrupted:       '#A78BFA',
};

const STATE_LABELS: Record<string, string> = {
  idle:              'Ready',
  sleeping:          'Sleeping',
  waking:            'Waking up…',
  listening:         'Listening…',
  follow_up_listening:'Listening…',
  transcribing:      'Processing…',
  thinking:          'Thinking…',
  executing:         'Working…',
  speaking:          'Speaking',
  success:           'Done ✓',
  error:             'Error',
};


// ═══════════════════════════════════════════════════════════════════════════════
// CompanionMode — Main component
// ═══════════════════════════════════════════════════════════════════════════════

export default function CompanionMode() {
  const genieState  = useAppStore((s) => s.genieState);
  const wsStatus    = useAppStore((s) => s.wsStatus);
  const liveText    = useAppStore((s) => s.liveTranscript);
  const companion   = useCompanionStore();
  const { startCompanion, stopCompanion, pauseCompanion, resumeCompanion, requestQuickLook } = useCompanion();

  const [displayMode, setDisplayMode] = useState<DisplayMode>('floating');
  const [showContextPanel, setShowContextPanel] = useState(false);
  const [position, setPosition] = useState({ x: companion.position.x, y: companion.position.y });
  const [isDragging, setIsDragging] = useState(false);
  const [showModeMenu, setShowModeMenu] = useState(false);
  const dragRef = useRef<{ startX: number; startY: number; startPosX: number; startPosY: number } | null>(null);

  const stateColor = STATE_COLORS[genieState] ?? '#5EEAD4';
  const stateLabel = STATE_LABELS[genieState] ?? 'Ready';
  const cfg = MODE_CONFIG[displayMode];

  const isActive = companion.mode !== 'off' && companion.mode !== 'stopping';
  const isConnected = wsStatus === 'authed' || wsStatus === 'connected';

  // ── Sync position with store ─────────────────────────────────────────────
  useEffect(() => {
    setPosition({ x: companion.position.x, y: companion.position.y });
  }, [companion.position.x, companion.position.y]);

  // ── Drag to reposition ────────────────────────────────────────────────────
  const onPointerDown = useCallback((e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      startPosX: position.x,
      startPosY: position.y,
    };
    setIsDragging(false);
  }, [position]);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragRef.current) return;
    const dx = e.clientX - dragRef.current.startX;
    const dy = e.clientY - dragRef.current.startY;
    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) setIsDragging(true);
    const nx = Math.max(0, Math.min(window.innerWidth - (cfg.panelW || 80), dragRef.current.startPosX + dx));
    const ny = Math.max(0, Math.min(window.innerHeight - 100, dragRef.current.startPosY + dy));
    setPosition({ x: nx, y: ny });
    companion.setPosition({ x: nx, y: ny });
  }, [cfg.panelW, companion]);

  const onPointerUp = useCallback((e: React.PointerEvent) => {
    dragRef.current = null;
    setIsDragging(false);
  }, []);

  // ── Mode switching ────────────────────────────────────────────────────────
  const cycleMode = useCallback(() => {
    const modes: DisplayMode[] = ['full', 'floating', 'mini', 'invisible'];
    const current = modes.indexOf(displayMode);
    setDisplayMode(modes[(current + 1) % modes.length]);
    setShowModeMenu(false);
  }, [displayMode]);

  if (!isActive) return null;
  if (displayMode === 'invisible') return <InvisibleModeIndicator stateColor={stateColor} onRestore={() => setDisplayMode('floating')} />;

  // ── MINI MODE ─────────────────────────────────────────────────────────────
  if (displayMode === 'mini') {
    return (
      <MiniCompanion
        position={position}
        stateColor={stateColor}
        genieState={genieState}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        isDragging={isDragging}
        onExpand={() => setDisplayMode('floating')}
        bubbleText={companion.bubbleText}
        bubbleVisible={companion.bubbleVisible}
      />
    );
  }

  // ── FLOATING MODE ─────────────────────────────────────────────────────────
  if (displayMode === 'floating') {
    return (
      <FloatingCompanion
        position={position}
        stateColor={stateColor}
        genieState={genieState}
        liveText={liveText}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        isDragging={isDragging}
        onExpand={() => setDisplayMode('full')}
        onMini={() => setDisplayMode('mini')}
        onHide={() => setDisplayMode('invisible')}
        onStop={stopCompanion}
        onPause={pauseCompanion}
        isPaused={companion.mode === 'paused'}
        bubbleText={companion.bubbleText}
        bubbleVisible={companion.bubbleVisible}
        isConnected={isConnected}
        screenAware={companion.screenAware}
        micActive={companion.micActive}
        requestQuickLook={requestQuickLook}
      />
    );
  }

  // ── FULL MODE ─────────────────────────────────────────────────────────────
  return (
    <FullCompanion
      genieState={genieState}
      stateColor={stateColor}
      stateLabel={stateLabel}
      liveText={liveText}
      isConnected={isConnected}
      companion={companion}
      onMinimize={() => setDisplayMode('floating')}
      onStop={stopCompanion}
      onPause={pauseCompanion}
      onResume={resumeCompanion}
      requestQuickLook={requestQuickLook}
      position={position}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    />
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// Sub-layouts
// ═══════════════════════════════════════════════════════════════════════════════

// ── Invisible Mode ────────────────────────────────────────────────────────────
function InvisibleModeIndicator({ stateColor, onRestore }: { stateColor: string; onRestore: () => void }) {
  return (
    <motion.div
      style={{
        position: 'fixed',
        bottom: 20,
        right: 20,
        zIndex: 9997,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 12px',
        borderRadius: 99,
        background: 'rgba(0,0,0,0.7)',
        border: `1px solid ${stateColor}44`,
        backdropFilter: 'blur(12px)',
        cursor: 'pointer',
        userSelect: 'none',
      }}
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
      onClick={onRestore}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
    >
      <motion.div
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: stateColor,
          boxShadow: `0 0 8px ${stateColor}`,
        }}
        animate={{ opacity: [1, 0.3, 1] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      />
      <span style={{ color: stateColor, fontSize: 11, fontWeight: 600, fontFamily: "'Inter', sans-serif" }}>
        Genie • Voice Only
      </span>
    </motion.div>
  );
}


// ── Mini mode ─────────────────────────────────────────────────────────────────
function MiniCompanion({ position, stateColor, genieState, onPointerDown, onPointerMove, onPointerUp, isDragging, onExpand, bubbleText, bubbleVisible }) {
  return (
    <div
      style={{
        position: 'fixed',
        left: position.x,
        top: position.y,
        zIndex: 9998,
        userSelect: 'none',
        touchAction: 'none',
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      {/* Bubble text */}
      <AnimatePresence>
        {bubbleVisible && bubbleText && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.9 }}
            style={{
              position: 'absolute',
              bottom: '100%',
              left: '50%',
              transform: 'translateX(-50%)',
              marginBottom: 8,
              background: 'rgba(10,15,30,0.92)',
              border: `1px solid ${stateColor}44`,
              borderRadius: 12,
              padding: '6px 10px',
              color: '#e2e8f0',
              fontSize: 11,
              fontFamily: "'Inter', sans-serif",
              maxWidth: 180,
              whiteSpace: 'pre-wrap',
              backdropFilter: 'blur(12px)',
              boxShadow: `0 4px 20px ${stateColor}22`,
            }}
          >
            {bubbleText}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Mini orb */}
      <motion.div
        style={{
          width: 52,
          height: 52,
          borderRadius: '50%',
          background: `radial-gradient(circle at 35% 30%, ${stateColor}dd, ${stateColor}44)`,
          border: `2px solid ${stateColor}66`,
          boxShadow: `0 0 20px ${stateColor}55, inset 0 1px 0 rgba(255,255,255,0.15)`,
          cursor: isDragging ? 'grabbing' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
        }}
        animate={{ scale: [1, 1.05, 1] }}
        transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
        onDoubleClick={onExpand}
        title="Double-click to expand"
      >
        <GenieFace size={50} showBody={false} minimal />
      </motion.div>
    </div>
  );
}


// ── Floating mode ─────────────────────────────────────────────────────────────
function FloatingCompanion({
  position, stateColor, genieState, liveText,
  onPointerDown, onPointerMove, onPointerUp, isDragging,
  onExpand, onMini, onHide, onStop, onPause, isPaused,
  bubbleText, bubbleVisible, isConnected, screenAware, micActive,
  requestQuickLook,
}) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div
      style={{
        position: 'fixed',
        left: position.x,
        top: position.y,
        zIndex: 9998,
        userSelect: 'none',
        touchAction: 'none',
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      {/* Proactive bubble */}
      <AnimatePresence>
        {bubbleVisible && bubbleText && (
          <motion.div
            initial={{ opacity: 0, x: -10, scale: 0.9 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: -10, scale: 0.9 }}
            style={{
              position: 'absolute',
              right: '110%',
              top: '10%',
              background: 'rgba(8,12,26,0.96)',
              border: `1px solid ${stateColor}55`,
              borderRadius: 16,
              padding: '10px 14px',
              color: '#e2e8f0',
              fontSize: 12,
              fontFamily: "'Inter', sans-serif",
              maxWidth: 220,
              backdropFilter: 'blur(16px)',
              boxShadow: `0 8px 32px ${stateColor}22`,
              pointerEvents: 'none',
            }}
          >
            <div style={{ color: stateColor, fontSize: 10, fontWeight: 700, marginBottom: 4, letterSpacing: '0.05em' }}>
              GENIE
            </div>
            {bubbleText}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Live transcript */}
      <AnimatePresence>
        {liveText && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            style={{
              position: 'absolute',
              bottom: '110%',
              left: '50%',
              transform: 'translateX(-50%)',
              marginBottom: 4,
              background: 'rgba(8,12,26,0.92)',
              border: `1px solid ${stateColor}44`,
              borderRadius: 12,
              padding: '6px 12px',
              color: '#cbd5e1',
              fontSize: 11,
              fontFamily: "'Inter', sans-serif",
              whiteSpace: 'nowrap',
              maxWidth: 280,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              backdropFilter: 'blur(12px)',
              pointerEvents: 'none',
            }}
          >
            {liveText}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Context menu */}
      <AnimatePresence>
        {showMenu && (
          <motion.div
            initial={{ opacity: 0, scale: 0.85, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.85, y: -8 }}
            style={{
              position: 'absolute',
              bottom: '110%',
              right: 0,
              background: 'rgba(8,12,26,0.98)',
              border: '1px solid rgba(99,102,241,0.3)',
              borderRadius: 16,
              overflow: 'hidden',
              backdropFilter: 'blur(20px)',
              boxShadow: '0 16px 48px rgba(0,0,0,0.6)',
              minWidth: 180,
              fontFamily: "'Inter', sans-serif",
              zIndex: 9999,
            }}
          >
            {[
              { label: '⬆ Expand', action: onExpand },
              { label: '⬇ Minimize', action: onMini },
              { label: '👁 Quick Look', action: () => { requestQuickLook(); setShowMenu(false); } },
              { label: isPaused ? '▶ Resume' : '⏸ Pause', action: () => { isPaused ? null : onPause(); setShowMenu(false); } },
              { label: '🔇 Voice Only', action: onHide },
              { label: '✕ Stop Companion', action: onStop, danger: true },
            ].map(({ label, action, danger }) => (
              <button
                key={label}
                onClick={(e) => { e.stopPropagation(); action?.(); }}
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '10px 16px',
                  background: 'transparent',
                  border: 'none',
                  color: danger ? '#f87171' : '#e2e8f0',
                  fontSize: 13,
                  fontWeight: 500,
                  textAlign: 'left',
                  cursor: 'pointer',
                  borderBottom: '1px solid rgba(255,255,255,0.05)',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = danger ? 'rgba(248,113,113,0.1)' : 'rgba(255,255,255,0.05)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                {label}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main floating panel */}
      <motion.div
        style={{
          position: 'relative',
          background: 'rgba(5,8,18,0.88)',
          border: `1.5px solid ${stateColor}44`,
          borderRadius: 24,
          backdropFilter: 'blur(20px)',
          boxShadow: `0 16px 60px rgba(0,0,0,0.5), 0 0 40px ${stateColor}18`,
          overflow: 'hidden',
          cursor: isDragging ? 'grabbing' : 'default',
        }}
        animate={{ boxShadow: [`0 16px 60px rgba(0,0,0,0.5), 0 0 30px ${stateColor}12`, `0 16px 60px rgba(0,0,0,0.5), 0 0 50px ${stateColor}28`, `0 16px 60px rgba(0,0,0,0.5), 0 0 30px ${stateColor}12`] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
      >
        {/* Avatar */}
        <div style={{ padding: '8px 8px 4px', display: 'flex', justifyContent: 'center' }}>
          <GenieFace size={110} showBody={false} minimal={false} />
        </div>

        {/* State + privacy strip */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 6,
          padding: '4px 12px 8px',
        }}>
          <motion.div
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: stateColor,
              boxShadow: `0 0 8px ${stateColor}`,
            }}
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 1.2, repeat: Infinity }}
          />
          <span style={{ color: stateColor, fontSize: 10, fontWeight: 600, fontFamily: "'Inter', sans-serif", letterSpacing: '0.04em' }}>
            {STATE_LABELS[genieState] ?? 'Ready'}
          </span>
          {screenAware && (
            <span style={{ color: '#22d3ee', fontSize: 9, opacity: 0.7 }}>●SCR</span>
          )}
          {micActive && (
            <motion.span
              style={{ color: '#a78bfa', fontSize: 9 }}
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ duration: 0.8, repeat: Infinity }}
            >
              ●MIC
            </motion.span>
          )}
        </div>

        {/* Context menu trigger */}
        <div
          style={{
            position: 'absolute',
            top: 6,
            right: 6,
            width: 22,
            height: 22,
            borderRadius: 8,
            background: 'rgba(255,255,255,0.05)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: 'rgba(148,163,184,0.7)',
            fontSize: 13,
            zIndex: 10,
          }}
          onClick={(e) => { e.stopPropagation(); setShowMenu(v => !v); }}
          title="Options"
        >
          ⋮
        </div>

        {/* Connection indicator */}
        {!isConnected && (
          <div style={{
            position: 'absolute',
            top: 6,
            left: 6,
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: '#F59E0B',
            boxShadow: '0 0 6px #F59E0B',
          }} title="Connecting..." />
        )}
      </motion.div>
    </div>
  );
}


// ── Full mode ─────────────────────────────────────────────────────────────────
function FullCompanion({
  genieState, stateColor, stateLabel, liveText, isConnected,
  companion, onMinimize, onStop, onPause, onResume, requestQuickLook,
  position, onPointerDown, onPointerMove, onPointerUp,
}) {
  const messages = useAppStore((s) => s.messages);

  return (
    <motion.div
      style={{
        position: 'fixed',
        left: position.x,
        top: position.y,
        zIndex: 9998,
        userSelect: 'none',
        touchAction: 'none',
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
    >
      <div
        style={{
          width: 380,
          background: 'rgba(4,7,18,0.96)',
          border: `1.5px solid ${stateColor}44`,
          borderRadius: 32,
          backdropFilter: 'blur(24px)',
          boxShadow: `0 32px 80px rgba(0,0,0,0.7), 0 0 60px ${stateColor}18`,
          overflow: 'hidden',
          fontFamily: "'Inter', sans-serif",
        }}
      >
        {/* ── Header bar ─────────────────────────────────────────────────── */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 18px 0',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <motion.div
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: isConnected ? stateColor : '#F59E0B',
                boxShadow: `0 0 10px ${isConnected ? stateColor : '#F59E0B'}`,
              }}
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span style={{ color: '#94a3b8', fontSize: 11, fontWeight: 600, letterSpacing: '0.05em' }}>
              GENIE OS
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <HeaderButton onClick={requestQuickLook} title="Quick Look (Ctrl+Shift+G)">
              👁
            </HeaderButton>
            <HeaderButton onClick={companion.mode === 'paused' ? onResume : onPause} title={companion.mode === 'paused' ? 'Resume' : 'Pause'}>
              {companion.mode === 'paused' ? '▶' : '⏸'}
            </HeaderButton>
            <HeaderButton onClick={onMinimize} title="Minimize">
              ⬇
            </HeaderButton>
            <HeaderButton onClick={onStop} title="Stop Companion" danger>
              ✕
            </HeaderButton>
          </div>
        </div>

        {/* ── Avatar center stage ─────────────────────────────────────── */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '16px 0 8px' }}>
          <GenieFace size={200} showBody={true} />
        </div>

        {/* ── State indicator ─────────────────────────────────────────── */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
          <motion.div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 16px',
              borderRadius: 99,
              background: `${stateColor}18`,
              border: `1px solid ${stateColor}44`,
            }}
          >
            <motion.div
              style={{ width: 7, height: 7, borderRadius: '50%', background: stateColor, boxShadow: `0 0 8px ${stateColor}` }}
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 1, repeat: Infinity }}
            />
            <span style={{ color: stateColor, fontSize: 12, fontWeight: 700, letterSpacing: '0.05em' }}>
              {stateLabel}
            </span>
          </motion.div>
        </div>

        {/* ── Live transcript ─────────────────────────────────────────── */}
        <AnimatePresence>
          {liveText && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              style={{
                margin: '0 16px 12px',
                padding: '10px 14px',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 14,
                color: '#e2e8f0',
                fontSize: 13,
                fontWeight: 500,
                textAlign: 'center',
                lineHeight: 1.5,
              }}
            >
              {liveText}
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Privacy indicators ──────────────────────────────────────── */}
        <PrivacyPanel screenAware={companion.screenAware} micActive={companion.micActive} stateColor={stateColor} />

        {/* ── Context status ──────────────────────────────────────────── */}
        <ContextStatusBar />

        {/* ── Recent message (last assistant response) ────────────────── */}
        {messages.length > 0 && (() => {
          const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant');
          if (!lastAssistant) return null;
          return (
            <div style={{
              margin: '8px 16px 16px',
              padding: '10px 14px',
              background: `${stateColor}0a`,
              border: `1px solid ${stateColor}22`,
              borderRadius: 14,
              color: '#94a3b8',
              fontSize: 12,
              lineHeight: 1.6,
              maxHeight: 80,
              overflow: 'hidden',
              display: '-webkit-box',
              WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical',
            }}>
              {lastAssistant.text}
            </div>
          );
        })()}
      </div>
    </motion.div>
  );
}


// ── Header action button ──────────────────────────────────────────────────────
function HeaderButton({ onClick, title, children, danger = false }) {
  return (
    <motion.button
      onClick={(e) => { e.stopPropagation(); onClick?.(); }}
      title={title}
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
      style={{
        width: 26,
        height: 26,
        borderRadius: 8,
        background: danger ? 'rgba(248,113,113,0.1)' : 'rgba(255,255,255,0.06)',
        border: danger ? '1px solid rgba(248,113,113,0.3)' : '1px solid rgba(255,255,255,0.1)',
        color: danger ? '#f87171' : '#94a3b8',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 12,
        fontFamily: "'Inter', sans-serif",
        transition: 'all 0.15s',
      }}
    >
      {children}
    </motion.button>
  );
}
