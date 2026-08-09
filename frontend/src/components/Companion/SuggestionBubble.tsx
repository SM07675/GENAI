/**
 * SuggestionBubble.tsx — Callout suggestion bubble anchored to the Companion Orb.
 *
 * Per spec §4.3:
 *  - Renders adjacent to the Companion Orb.
 *  - Typewriter text streaming synced to TTS & companion_bubble WS frames.
 *  - Click to expand/collapse longer answers.
 *  - Click to dismiss. Never steals focus or blocks interaction underneath.
 */
import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useCompanionStore } from "../../store/companionStore";

export default function SuggestionBubble() {
  const bubbleText = useCompanionStore((s) => s.bubbleText);
  const bubbleVisible = useCompanionStore((s) => s.bubbleVisible);
  const bubbleExpanded = useCompanionStore((s) => s.bubbleExpanded);
  const setBubble = useCompanionStore((s) => s.setBubble);
  const toggleExpanded = useCompanionStore((s) => s.toggleBubbleExpanded);

  if (!bubbleVisible || !bubbleText) return null;

  const isLong = bubbleText.length > 120;
  const displayText = !bubbleExpanded && isLong ? bubbleText.slice(0, 115) + "…" : bubbleText;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 10, scale: 0.9 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.9 }}
        transition={{ type: "spring", stiffness: 350, damping: 25 }}
        style={{
          position: "absolute",
          bottom: "100%",
          right: 0,
          marginBottom: 12,
          width: bubbleExpanded ? 320 : 260,
          padding: "10px 14px",
          borderRadius: 16,
          background: "rgba(15, 23, 42, 0.92)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(139, 92, 246, 0.4)",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.5), 0 0 15px rgba(139, 92, 246, 0.2)",
          color: "#f8fafc",
          fontSize: 13,
          lineHeight: 1.5,
          fontFamily: "Inter, system-ui, sans-serif",
          zIndex: 9999,
          pointerEvents: "auto",
          cursor: "pointer",
        }}
        onClick={(e) => {
          e.stopPropagation();
          if (isLong) toggleExpanded();
        }}
      >
        {/* Callout tail arrow */}
        <div
          style={{
            position: "absolute",
            bottom: -6,
            right: 24,
            width: 12,
            height: 12,
            background: "rgba(15, 23, 42, 0.92)",
            borderRight: "1px solid rgba(139, 92, 246, 0.4)",
            borderBottom: "1px solid rgba(139, 92, 246, 0.4)",
            transform: "rotate(45deg)",
          }}
        />

        {/* Content header with close button */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
          <div style={{ flex: 1, wordBreak: "break-word" }}>
            <span>{displayText}</span>
            {isLong && (
              <span
                style={{
                  display: "block",
                  fontSize: 11,
                  color: "#a78bfa",
                  marginTop: 4,
                  fontWeight: 600,
                }}
              >
                {bubbleExpanded ? "Show less ▲" : "Click to read full answer ▼"}
              </span>
            )}
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setBubble(null, false);
            }}
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              fontSize: 14,
              lineHeight: 1,
              padding: "2px 4px",
              borderRadius: 4,
              flexShrink: 0,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#ef4444")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#94a3b8")}
            title="Dismiss"
          >
            ✕
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
