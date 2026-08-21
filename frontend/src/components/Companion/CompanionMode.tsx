/**
 * CompanionMode.tsx — Living Floating Desktop & Web Companion Overlay.
 *
 * Requirements:
 * - Constantly visible on screen when enabled.
 * - Overlay on screen with smooth drag & drop positioning.
 * - High aesthetic animations, crystal crisp UI, neon/sky glass styling.
 * - Display modes: FULL, FLOATING, MINI, INVISIBLE.
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import { useCompanionStore } from '../../store/companionStore';
import { useCompanion } from '../../hooks/useCompanion';
import GenieFace from '../GenieFace/GenieFace';
import PrivacyPanel from './PrivacyPanel';
import VoiceWaveform from './VoiceWaveform';
import ContextStatusBar from './ContextStatusBar';
import {
  EyeIcon,
  CameraIcon,
  PauseIcon,
  PlayIcon,
  MinimizeIcon,
  MaximizeIcon,
  CloseIcon,
  SparklesIcon,
  MicIcon,
  SettingsIcon,
} from '../UI/Icons';

const MODE_CONFIG = {
  full: { avatarSize: 200, panelW: 380 },
  floating: { avatarSize: 110, panelW: 160 },
  mini: { avatarSize: 52, panelW: 64 },
  invisible: { avatarSize: 0, panelW: 0 },
} as const;

type DisplayMode = keyof typeof MODE_CONFIG;

const STATE_COLORS: Record<string, string> = {
  idle: '#22d3ee',
  sleeping: '#818cf8',
  waking: '#f59e0b',
  listening: '#38bdf8',
  follow_up_listening: '#38bdf8',
  transcribing: '#a855f7',
  thinking: '#c084fc',
  executing: '#818cf8',
  speaking: '#34d399',
  success: '#f472b6',
  error: '#f87171',
  interrupted: '#fbbf24',
};

const STATE_LABELS: Record<string, string> = {
  idle: 'Ready',
  sleeping: 'Sleeping',
  waking: 'Waking up…',
  listening: 'Listening…',
  follow_up_listening: 'Listening…',
  transcribing: 'Processing…',
  thinking: 'Thinking…',
  executing: 'Working…',
  speaking: 'Speaking',
  success: 'Done ✓',
  error: 'Error',
};

export default function CompanionMode() {
  const genieState = useAppStore((s) => s.genieState);
  const wsStatus = useAppStore((s) => s.wsStatus);
  const liveText = useAppStore((s) => s.liveTranscript);
  const companion = useCompanionStore();
  const { stopCompanion, pauseCompanion, resumeCompanion, requestQuickLook } = useCompanion();

  const displayMode = companion.displayMode;
  const setDisplayMode = companion.setDisplayMode;

  const [position, setPosition] = useState({ x: companion.position.x, y: companion.position.y });
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<{ startX: number; startY: number; startPosX: number; startPosY: number } | null>(null);

  const stateColor = STATE_COLORS[genieState] ?? '#22d3ee';
  const stateLabel = STATE_LABELS[genieState] ?? 'Ready';
  const cfg = MODE_CONFIG[displayMode as DisplayMode] || MODE_CONFIG.floating;

  const isActive = companion.mode !== 'off' && companion.mode !== 'stopping';
  const isConnected = wsStatus === 'authed' || wsStatus === 'connected';

  // Sync position from store
  useEffect(() => {
    setPosition({ x: companion.position.x, y: companion.position.y });
  }, [companion.position.x, companion.position.y]);

  // Drag handlers
  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      dragRef.current = {
        startX: e.clientX,
        startY: e.clientY,
        startPosX: position.x,
        startPosY: position.y,
      };
      setIsDragging(false);
    },
    [position]
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragRef.current) return;
      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) setIsDragging(true);
      const nx = Math.max(10, Math.min(window.innerWidth - (cfg.panelW || 80) - 10, dragRef.current.startPosX + dx));
      const ny = Math.max(10, Math.min(window.innerHeight - 100, dragRef.current.startPosY + dy));
      setPosition({ x: nx, y: ny });
      companion.setPosition({ x: nx, y: ny });
    },
    [cfg.panelW, companion]
  );

  const onPointerUp = useCallback((e: React.PointerEvent) => {
    dragRef.current = null;
    setIsDragging(false);
  }, []);

  if (!isActive) return null;

  if (displayMode === 'invisible') {
    return <InvisibleModeIndicator stateColor={stateColor} onRestore={() => setDisplayMode('floating')} />;
  }

  if (displayMode === 'mini') {
    return (
      <MiniCompanion
        position={position}
        stateColor={stateColor}
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

// Sub-components

function InvisibleModeIndicator({ stateColor, onRestore }: { stateColor: string; onRestore: () => void }) {
  return (
    <motion.div
      className="fixed bottom-6 right-6 z-[9999] flex items-center gap-2 px-3 py-1.5 rounded-full cyber-glass cursor-pointer select-none"
      style={{ border: `1px solid ${stateColor}44` }}
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
      onClick={onRestore}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
    >
      <motion.div
        className="w-2.5 h-2.5 rounded-full"
        style={{ background: stateColor, boxShadow: `0 0 10px ${stateColor}` }}
        animate={{ opacity: [1, 0.4, 1] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      />
      <span className="text-xs font-semibold text-slate-200">Genie Voice Active</span>
    </motion.div>
  );
}

function MiniCompanion({
  position,
  stateColor,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  isDragging,
  onExpand,
  bubbleText,
  bubbleVisible,
}: any) {
  return (
    <div
      className="fixed z-[9999] select-none touch-none"
      style={{ left: position.x, top: position.y }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      <AnimatePresence>
        {bubbleVisible && bubbleText && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.9 }}
            className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 p-2 px-3 rounded-xl cyber-glass text-[11px] text-slate-200 max-w-[180px] text-center"
            style={{ border: `1px solid ${stateColor}44` }}
          >
            {bubbleText}
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        className="w-14 h-14 rounded-full flex items-center justify-center overflow-hidden cursor-pointer"
        style={{
          background: `radial-gradient(circle at 35% 30%, ${stateColor}dd, ${stateColor}44)`,
          border: `2px solid ${stateColor}88`,
          boxShadow: `0 0 25px ${stateColor}66`,
          cursor: isDragging ? 'grabbing' : 'pointer',
        }}
        animate={{ scale: [1, 1.06, 1] }}
        transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
        onDoubleClick={onExpand}
        title="Double-click to expand"
      >
        <GenieFace size={52} showBody={false} minimal />
      </motion.div>
    </div>
  );
}

function FloatingCompanion({
  position,
  stateColor,
  genieState,
  liveText,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  isDragging,
  onExpand,
  onMini,
  onHide,
  onStop,
  onPause,
  isPaused,
  bubbleText,
  bubbleVisible,
  isConnected,
  screenAware,
  micActive,
  requestQuickLook,
}: any) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div
      className="fixed z-[9999] select-none touch-none"
      style={{ left: position.x, top: position.y }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      {/* Speech callout bubble */}
      <AnimatePresence>
        {bubbleVisible && bubbleText && (
          <motion.div
            initial={{ opacity: 0, x: -10, scale: 0.9 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: -10, scale: 0.9 }}
            className="absolute right-[105%] top-2 p-3 rounded-2xl cyber-glass text-xs text-slate-100 max-w-[220px] shadow-2xl pointer-events-none"
            style={{ border: `1px solid ${stateColor}66` }}
          >
            <div className="text-[10px] font-bold tracking-wider uppercase mb-1" style={{ color: stateColor }}>
              ✦ Genie AI
            </div>
            {bubbleText}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Live transcript ticker */}
      <AnimatePresence>
        {liveText && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            className="absolute bottom-[108%] left-1/2 -translate-x-1/2 mb-1 px-3 py-1.5 rounded-xl cyber-glass text-[11px] text-slate-200 whitespace-nowrap max-w-[260px] truncate pointer-events-none"
            style={{ border: `1px solid ${stateColor}44` }}
          >
            {liveText}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Quick Option Menu */}
      <AnimatePresence>
        {showMenu && (
          <motion.div
            initial={{ opacity: 0, scale: 0.88, y: -6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.88, y: -6 }}
            className="absolute bottom-[105%] right-0 min-w-[170px] rounded-2xl cyber-glass p-1.5 shadow-2xl z-[10000] text-xs font-semibold space-y-1"
          >
            <MenuOption icon={<MaximizeIcon size={14} />} label="Expand Card" onClick={onExpand} />
            <MenuOption icon={<MinimizeIcon size={14} />} label="Minimize Orb" onClick={onMini} />
            <MenuOption icon={<EyeIcon size={14} />} label="Quick Look" onClick={() => { requestQuickLook(); setShowMenu(false); }} />
            <MenuOption icon={isPaused ? <PlayIcon size={14} /> : <PauseIcon size={14} />} label={isPaused ? 'Resume' : 'Pause'} onClick={() => { isPaused ? null : onPause(); setShowMenu(false); }} />
            <MenuOption icon={<MicIcon size={14} />} label="Voice Only" onClick={onHide} />
            <MenuOption icon={<CloseIcon size={14} />} label="Exit Companion" onClick={onStop} danger />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main floating container card */}
      <motion.div
        className="relative rounded-3xl cyber-glass p-2 shadow-2xl overflow-hidden"
        style={{
          border: `1.5px solid ${stateColor}55`,
          cursor: isDragging ? 'grabbing' : 'grab',
        }}
        animate={{
          boxShadow: [
            `0 16px 50px rgba(0,0,0,0.6), 0 0 25px ${stateColor}22`,
            `0 16px 50px rgba(0,0,0,0.6), 0 0 45px ${stateColor}44`,
            `0 16px 50px rgba(0,0,0,0.6), 0 0 25px ${stateColor}22`,
          ],
        }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
      >
        {/* Avatar component */}
        <div className="flex justify-center p-1">
          <GenieFace size={110} showBody={false} minimal={false} />
        </div>

        {/* State label & privacy pill */}
        <div className="flex items-center justify-center gap-1.5 px-3 pb-2 text-[10px] font-bold tracking-wide">
          <motion.div
            className="w-2 h-2 rounded-full"
            style={{ background: stateColor, boxShadow: `0 0 8px ${stateColor}` }}
            animate={{ opacity: [1, 0.4, 1] }}
            transition={{ duration: 1.2, repeat: Infinity }}
          />
          <span style={{ color: stateColor }}>{STATE_LABELS[genieState] ?? 'Ready'}</span>
          {screenAware && <span className="text-cyan-400 opacity-80">●SCR</span>}
          {micActive && <span className="text-purple-400 animate-pulse">●MIC</span>}
        </div>

        {/* Options trigger button */}
        <button
          onClick={(e) => { e.stopPropagation(); setShowMenu((v) => !v); }}
          className="absolute top-2 right-2 w-6 h-6 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center text-slate-300 transition-all text-xs"
          title="Options"
        >
          ⋮
        </button>

        {!isConnected && (
          <div className="absolute top-2 left-2 w-2 h-2 rounded-full bg-amber-500 shadow-sm shadow-amber-500/50" title="Connecting..." />
        )}
      </motion.div>
    </div>
  );
}

function FullCompanion({
  genieState,
  stateColor,
  stateLabel,
  liveText,
  isConnected,
  companion,
  onMinimize,
  onStop,
  onPause,
  onResume,
  requestQuickLook,
  position,
  onPointerDown,
  onPointerMove,
  onPointerUp,
}: any) {
  const messages = useAppStore((s) => s.messages);

  return (
    <motion.div
      className="fixed z-[9999] select-none touch-none"
      style={{ left: position.x, top: position.y }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.92 }}
    >
      <div
        className="w-[380px] rounded-3xl cyber-glass p-5 shadow-2xl space-y-4 overflow-hidden"
        style={{ border: `1.5px solid ${stateColor}55` }}
      >
        {/* Header bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <motion.div
              className="w-2.5 h-2.5 rounded-full"
              style={{ background: isConnected ? stateColor : '#f59e0b', boxShadow: `0 0 10px ${isConnected ? stateColor : '#f59e0b'}` }}
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span className="text-xs font-bold text-slate-300 tracking-wider">GENIE OS COMPANION</span>
          </div>

          <div className="flex items-center gap-1.5">
            <IconButton onClick={requestQuickLook} title="Quick Look">
              <EyeIcon size={14} />
            </IconButton>
            <IconButton onClick={companion.mode === 'paused' ? onResume : onPause} title={companion.mode === 'paused' ? 'Resume' : 'Pause'}>
              {companion.mode === 'paused' ? <PlayIcon size={14} /> : <PauseIcon size={14} />}
            </IconButton>
            <IconButton onClick={onMinimize} title="Minimize">
              <MinimizeIcon size={14} />
            </IconButton>
            <IconButton onClick={onStop} title="Exit Companion" danger>
              <CloseIcon size={14} />
            </IconButton>
          </div>
        </div>

        {/* Avatar Display */}
        <div className="flex justify-center py-2">
          <GenieFace size={180} showBody={true} />
        </div>

        {/* State Pill */}
        <div className="flex justify-center">
          <div
            className="flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold tracking-wide"
            style={{ background: `${stateColor}18`, border: `1px solid ${stateColor}44`, color: stateColor }}
          >
            <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: stateColor }} />
            <span>{stateLabel}</span>
          </div>
        </div>

        {/* Live Text Ticker */}
        {liveText && (
          <div className="p-3 rounded-2xl bg-white/5 border border-white/10 text-xs text-slate-200 text-center leading-relaxed">
            {liveText}
          </div>
        )}

        {/* Privacy Panel */}
        <PrivacyPanel screenAware={companion.screenAware} micActive={companion.micActive} stateColor={stateColor} />

        {/* Context Status Bar */}
        <ContextStatusBar />

        {/* Last Assistant Turn */}
        {messages.length > 0 && (() => {
          const lastMsg = [...messages].reverse().find((m) => m.role === 'assistant');
          if (!lastMsg) return null;
          return (
            <div className="p-3 rounded-2xl bg-white/5 border border-white/10 text-xs text-slate-400 line-clamp-3 leading-relaxed">
              {lastMsg.text}
            </div>
          );
        })()}
      </div>
    </motion.div>
  );
}

function MenuOption({ icon, label, onClick, danger = false }: any) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      className={`w-full flex items-center gap-2.5 p-2 rounded-xl text-left transition-all ${
        danger ? 'text-rose-400 hover:bg-rose-500/10' : 'text-slate-200 hover:bg-white/10'
      }`}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function IconButton({ onClick, title, children, danger = false }: any) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      title={title}
      className={`w-7 h-7 rounded-xl flex items-center justify-center transition-all ${
        danger
          ? 'bg-rose-500/10 border border-rose-500/30 text-rose-400 hover:bg-rose-500/20'
          : 'bg-white/10 border border-white/15 text-slate-300 hover:bg-white/20'
      }`}
    >
      {children}
    </button>
  );
}
