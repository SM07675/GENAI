/**
 * CompanionTooltip.tsx — Hover tooltip with mode info and companion controls.
 *
 * Shown when hovering the CompanionOrb. Contains:
 *  - Current mode + sub-mode badge
 *  - Screen-aware / voice-active status
 *  - Quick controls: Pause, Mute, Hide, Stop, Settings link
 */
import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useCompanionStore, type CompanionSubMode } from "../../store/companionStore";
import { useCompanion } from "../../hooks/useCompanion";

const SUB_MODE_LABELS: Record<CompanionSubMode, string> = {
  general: "General",
  gaming: "🎮 Gaming",
  coding: "💻 Coding",
  writing: "✍️ Writing",
  quiet: "🤫 Quiet",
};

interface CompanionTooltipProps {
  visible: boolean;
}

export default function CompanionTooltip({ visible }: CompanionTooltipProps) {
  const mode = useCompanionStore((s) => s.mode);
  const subMode = useCompanionStore((s) => s.subMode);
  const screenAware = useCompanionStore((s) => s.screenAware);
  const micActive = useCompanionStore((s) => s.micActive);

  const { stopCompanion, pauseCompanion, resumeCompanion } = useCompanion();

  const isPaused = mode === "paused";

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 6 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 6 }}
          transition={{ duration: 0.15 }}
          style={{
            position: "absolute",
            bottom: "calc(100% + 10px)",
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(10,14,26,0.92)",
            backdropFilter: "blur(12px)",
            border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: "12px",
            padding: mode === "off" ? "8px 12px" : "12px 14px",
            minWidth: mode === "off" ? "190px" : "180px",
            boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
            fontFamily: "'Inter', sans-serif",
            color: "#e2e8f0",
            zIndex: 9999,
            pointerEvents: "auto",
            whiteSpace: "nowrap",
          }}
        >
          {mode === "off" ? (
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#a78bfa" }}>
                Ask Genie About Your Screen
              </div>
              <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2 }}>
                Click to ask • Double-click for companion
              </div>
            </div>
          ) : (
            <>
              {/* Mode badge */}
              <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>
                Companion
              </div>
              <div style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                background: "rgba(99,102,241,0.15)",
                border: "1px solid rgba(99,102,241,0.3)",
                borderRadius: 6,
                padding: "3px 8px",
                fontSize: 12,
                fontWeight: 600,
                marginBottom: 10,
              }}>
                {SUB_MODE_LABELS[subMode]}
              </div>

              {/* Status pills */}
              <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
                <StatusPill label="Screen" active={screenAware} />
                <StatusPill label="Mic" active={micActive} />
              </div>

              {/* Controls */}
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <ControlButton
                  onClick={isPaused ? resumeCompanion : pauseCompanion}
                  label={isPaused ? "▶ Resume" : "⏸ Pause"}
                  color="#a78bfa"
                />
                <ControlButton
                  onClick={stopCompanion}
                  label="⏹ Stop Companion"
                  color="#f87171"
                />
              </div>
            </>
          )}

          {/* Tooltip arrow */}
          <div style={{
            position: "absolute",
            bottom: -6,
            left: "50%",
            transform: "translateX(-50%) rotate(45deg)",
            width: 10,
            height: 10,
            background: "rgba(10,14,26,0.92)",
            border: "1px solid rgba(255,255,255,0.12)",
            borderTop: "none",
            borderLeft: "none",
          }} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function StatusPill({ label, active }: { label: string; active: boolean }) {
  return (
    <div style={{
      fontSize: 10,
      padding: "2px 7px",
      borderRadius: 4,
      background: active ? "rgba(34,211,238,0.12)" : "rgba(100,116,139,0.12)",
      border: `1px solid ${active ? "rgba(34,211,238,0.3)" : "rgba(100,116,139,0.3)"}`,
      color: active ? "#22d3ee" : "#64748b",
      fontWeight: 500,
    }}>
      {label}: {active ? "On" : "Off"}
    </div>
  );
}

function ControlButton({
  onClick,
  label,
  color,
}: {
  onClick: () => void;
  label: string;
  color: string;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered ? `${color}22` : "transparent",
        border: `1px solid ${hovered ? color : "rgba(255,255,255,0.08)"}`,
        borderRadius: 6,
        padding: "5px 10px",
        color: hovered ? color : "#94a3b8",
        fontSize: 11,
        fontWeight: 500,
        cursor: "pointer",
        textAlign: "left",
        transition: "all 0.15s",
        fontFamily: "'Inter', sans-serif",
      }}
    >
      {label}
    </button>
  );
}
