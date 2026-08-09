/**
 * CompanionOrb.tsx — The floating companion orb.
 *
 * Renders in the companion overlay (either in a separate Electron BrowserWindow
 * or as a floating draggable div in the main window).
 *
 * Uses the EXISTING orb animation motion-token system — same visual language
 * as the main Genie orb, just scaled down and positioned as an overlay.
 * No second character/animation system.
 *
 * Overlay states (per spec §3):
 *   WATCHING | LISTENING | THINKING | EXCITED | WARNING | HAPPY | SAD | LAUGHING | PAUSED | NONE
 */
import { useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useCompanionStore, type CompanionOverlay } from "../../store/companionStore";
import { useCompanion } from "../../hooks/useCompanion";
import CompanionTooltip from "./CompanionTooltip";
import PrivacyIndicator from "./PrivacyIndicator";
import SuggestionBubble from "./SuggestionBubble";

// ── Orb visual configurations per overlay state ───────────────────────────────
interface OrbConfig {
  color: string;
  glow: string;
  ringColor: string;
  pulse: "none" | "gentle" | "fast" | "urgent";
  scale: number;
  emoji: string;
}

const OVERLAY_CONFIGS: Record<CompanionOverlay, OrbConfig> = {
  NONE: {
    color: "#1e293b",
    glow: "none",
    ringColor: "rgba(99,102,241,0.2)",
    pulse: "gentle",
    scale: 1.0,
    emoji: "",
  },
  WATCHING: {
    color: "#312e81",
    glow: "0 0 20px rgba(99,102,241,0.4)",
    ringColor: "rgba(99,102,241,0.35)",
    pulse: "gentle",
    scale: 1.0,
    emoji: "👁",
  },
  LISTENING: {
    color: "#14532d",
    glow: "0 0 22px rgba(34,197,94,0.5)",
    ringColor: "rgba(34,197,94,0.4)",
    pulse: "fast",
    scale: 1.04,
    emoji: "🎙",
  },
  THINKING: {
    color: "#083344",
    glow: "0 0 28px rgba(6,182,212,0.7), 0 0 50px rgba(6,182,212,0.3)",
    ringColor: "rgba(6,182,212,0.5)",
    pulse: "fast",
    scale: 1.06,
    emoji: "🔍",
  },
  EXCITED: {
    color: "#7c2d12",
    glow: "0 0 28px rgba(251,146,60,0.6)",
    ringColor: "rgba(251,146,60,0.5)",
    pulse: "fast",
    scale: 1.12,
    emoji: "🔥",
  },
  WARNING: {
    color: "#7f1d1d",
    glow: "0 0 28px rgba(239,68,68,0.7)",
    ringColor: "rgba(239,68,68,0.5)",
    pulse: "urgent",
    scale: 1.08,
    emoji: "⚠️",
  },
  HAPPY: {
    color: "#14532d",
    glow: "0 0 24px rgba(34,197,94,0.5)",
    ringColor: "rgba(34,197,94,0.4)",
    pulse: "gentle",
    scale: 1.05,
    emoji: "✨",
  },
  SAD: {
    color: "#1e3a5f",
    glow: "0 0 18px rgba(96,165,250,0.4)",
    ringColor: "rgba(96,165,250,0.3)",
    pulse: "gentle",
    scale: 0.92,
    emoji: "💙",
  },
  LAUGHING: {
    color: "#713f12",
    glow: "0 0 26px rgba(250,204,21,0.5)",
    ringColor: "rgba(250,204,21,0.4)",
    pulse: "fast",
    scale: 1.1,
    emoji: "😂",
  },
  PAUSED: {
    color: "#1e293b",
    glow: "none",
    ringColor: "rgba(148,163,184,0.2)",
    pulse: "none",
    scale: 0.88,
    emoji: "⏸",
  },
};

const PULSE_ANIMATIONS = {
  none: {},
  gentle: {
    scale: [1, 1.04, 1],
    transition: { duration: 3, repeat: Infinity, ease: "easeInOut" },
  },
  fast: {
    scale: [1, 1.08, 1],
    transition: { duration: 1.2, repeat: Infinity, ease: "easeInOut" },
  },
  urgent: {
    scale: [1, 1.1, 1],
    opacity: [1, 0.85, 1],
    transition: { duration: 0.7, repeat: Infinity, ease: "easeInOut" },
  },
};

const ACTIVE_ORB_SIZE = 64;   // px
const LAUNCHER_ORB_SIZE = 44; // px

export default function CompanionOrb() {
  const overlayState = useCompanionStore((s) => s.overlayState);
  const overlayIntensity = useCompanionStore((s) => s.overlayIntensity);
  const mode = useCompanionStore((s) => s.mode);
  const launcherVisible = useCompanionStore((s) => s.launcherVisible);
  const position = useCompanionStore((s) => s.position);
  const setPosition = useCompanionStore((s) => s.setPosition);
  const lastEvent = useCompanionStore((s) => s.lastEvent);

  const { startCompanion, stopCompanion, requestQuickLook } = useCompanion();

  const [hovered, setHovered] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const [dragging, setDragging] = useState(false);
  const dragStartRef = useRef<{ mx: number; my: number; ox: number; oy: number } | null>(null);
  const clickStartRef = useRef<{ time: number; x: number; y: number } | null>(null);
  const clickTimerRef = useRef<NodeJS.Timeout | null>(null);

  const isActiveMode = mode !== "off";
  const orbSize = isActiveMode ? ACTIVE_ORB_SIZE : LAUNCHER_ORB_SIZE;
  const config = OVERLAY_CONFIGS[overlayState] ?? OVERLAY_CONFIGS.WATCHING;
  const pulseAnim = PULSE_ANIMATIONS[config.pulse];

  // ── Drag to reposition ────────────────────────────────────────────────────
  const onPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      dragStartRef.current = { mx: e.clientX, my: e.clientY, ox: position.x, oy: position.y };
      clickStartRef.current = { time: Date.now(), x: e.clientX, y: e.clientY };
      setDragging(false);
      setShowTooltip(false);
    },
    [position]
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragStartRef.current) return;
      const dx = e.clientX - dragStartRef.current.mx;
      const dy = e.clientY - dragStartRef.current.my;
      if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
        setDragging(true);
      }
      const nx = Math.max(0, Math.min(window.innerWidth - orbSize, dragStartRef.current.ox + dx));
      const ny = Math.max(0, Math.min(window.innerHeight - orbSize, dragStartRef.current.oy + dy));
      setPosition({ x: nx, y: ny });
    },
    [setPosition, orbSize]
  );

  const onPointerUp = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const clickInfo = clickStartRef.current;
      dragStartRef.current = null;
      clickStartRef.current = null;

      if (!clickInfo) return;

      const duration = Date.now() - clickInfo.time;
      const dist = Math.hypot(e.clientX - clickInfo.x, e.clientY - clickInfo.y);

      if (dist < 6) {
        // Handle gestures (§4.2):
        if (duration >= 500) {
          // Long-press -> Toggle continuous Companion Mode
          if (isActiveMode) stopCompanion();
          else startCompanion("general");
        } else {
          // Click -> Schedule single click for Quick Look, or double click for mode toggle
          if (clickTimerRef.current) {
            // Double-click -> Toggle continuous Companion Mode
            clearTimeout(clickTimerRef.current);
            clickTimerRef.current = null;
            if (isActiveMode) stopCompanion();
            else startCompanion("general");
          } else {
            clickTimerRef.current = setTimeout(() => {
              clickTimerRef.current = null;
              // Single click -> Trigger Quick Look ("Look & Answer" fast path)
              requestQuickLook("What is on my screen right now?");
            }, 250);
          }
        }
      }
      setDragging(false);
    },
    [isActiveMode, startCompanion, stopCompanion, requestQuickLook]
  );

  if (mode === "off" && !launcherVisible) return null;

  return (
    <div
      style={{
        position: "fixed",
        left: position.x,
        top: position.y,
        zIndex: 9998,
        userSelect: "none",
        touchAction: "none",
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onMouseEnter={() => {
        setHovered(true);
        setShowTooltip(true);
      }}
      onMouseLeave={() => {
        setHovered(false);
        setShowTooltip(false);
      }}
    >
      {/* Suggestion Callout Bubble anchored to Orb (§4.3) */}
      <SuggestionBubble />

      {/* Hover Tooltip */}
      <CompanionTooltip visible={showTooltip && !dragging} />

      {/* Orb body */}
      <motion.div
        animate={pulseAnim}
        style={{
          width: orbSize,
          height: orbSize,
          borderRadius: "50%",
          background: isActiveMode
            ? `radial-gradient(circle at 35% 35%, ${config.color}dd, ${config.color}88)`
            : "radial-gradient(circle at 35% 35%, #4f46e5dd, #312e8188)",
          boxShadow: isActiveMode
            ? `${config.glow}, inset 0 1px 0 rgba(255,255,255,0.12)`
            : "0 0 14px rgba(99,102,241,0.3), inset 0 1px 0 rgba(255,255,255,0.12)",
          border: isActiveMode ? `2px solid ${config.ringColor}` : "1.5px solid rgba(99,102,241,0.4)",
          opacity: isActiveMode ? 1.0 : 0.75,
          cursor: dragging ? "grabbing" : "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: isActiveMode ? 24 : 18,
          transition: "width 0.3s, height 0.3s, background 0.4s, box-shadow 0.4s, border-color 0.4s, opacity 0.3s",
          transform: `scale(${isActiveMode ? config.scale * (hovered ? 1.06 : 1.0) : hovered ? 1.1 : 1.0})`,
          transformOrigin: "center",
        }}
      >
        {isActiveMode ? (
          config.emoji && <span style={{ fontSize: 22 }}>{config.emoji}</span>
        ) : (
          <span style={{ fontSize: 18, filter: "drop-shadow(0 0 4px rgba(255,255,255,0.5))" }}>👁</span>
        )}

        {/* Inner orb glow ring */}
        {isActiveMode && (
          <motion.div
            style={{
              position: "absolute",
              inset: 4,
              borderRadius: "50%",
              border: `1px solid ${config.ringColor}`,
              opacity: overlayIntensity * 0.6,
            }}
            animate={
              config.pulse !== "none"
                ? { opacity: [overlayIntensity * 0.3, overlayIntensity * 0.8, overlayIntensity * 0.3] }
                : {}
            }
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
          />
        )}
      </motion.div>

      {/* Privacy indicator below orb */}
      {isActiveMode && (
        <div style={{ marginTop: 6, display: "flex", justifyContent: "center" }}>
          <PrivacyIndicator />
        </div>
      )}

      {/* Event flash notification */}
      <AnimatePresence>
        {lastEvent && lastEvent.importance === "critical" && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.8 }}
            animate={{ opacity: 1, y: -orbSize - 36, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            style={{
              position: "absolute",
              left: "50%",
              transform: "translateX(-50%)",
              background: "rgba(239,68,68,0.9)",
              color: "#fff",
              fontSize: 10,
              fontWeight: 700,
              padding: "3px 8px",
              borderRadius: 6,
              whiteSpace: "nowrap",
              fontFamily: "'Inter', sans-serif",
            }}
          >
            {lastEvent.type.replace(/_/g, " ")}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
