/**
 * PrivacyIndicator.tsx — Always-visible, always-accurate privacy indicator.
 *
 * Per spec §16: this indicator must NEVER be cached or delayed.
 * It reflects the companionStore privacy state which is updated
 * every time the backend sends a companion_privacy message.
 *
 * Design: compact pill, semi-transparent background, two states:
 *   👁  Watching   (screen_aware=true)
 *   ○   Not Watching  (screen_aware=false)
 *   🎤  Listening  (mic_active=true, shown as secondary indicator)
 */
import { memo } from "react";
import { motion } from "framer-motion";
import { useCompanionStore } from "../../store/companionStore";

const PrivacyIndicator = memo(function PrivacyIndicator() {
  const screenAware = useCompanionStore((s) => s.screenAware);
  const micActive = useCompanionStore((s) => s.micActive);
  const mode = useCompanionStore((s) => s.mode);

  if (mode === "off") return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 8 }}
      className="companion-privacy-indicator"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "6px",
        padding: "4px 10px",
        borderRadius: "20px",
        background: "rgba(0,0,0,0.55)",
        backdropFilter: "blur(8px)",
        border: "1px solid rgba(255,255,255,0.10)",
        fontSize: "11px",
        fontWeight: 500,
        fontFamily: "'Inter', sans-serif",
        color: "#e2e8f0",
        userSelect: "none",
        pointerEvents: "none",  // indicator is non-interactive
      }}
    >
      {/* Screen awareness dot */}
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: screenAware ? "#22d3ee" : "#64748b",
          boxShadow: screenAware ? "0 0 6px #22d3ee" : "none",
          flexShrink: 0,
          transition: "background 0.3s, box-shadow 0.3s",
        }}
      />
      <span style={{ color: screenAware ? "#e2e8f0" : "#94a3b8" }}>
        {screenAware ? "Watching" : "Not Watching"}
      </span>

      {/* Mic indicator (only when companion is actively listening) */}
      {micActive && (
        <>
          <span style={{ color: "#475569", margin: "0 2px" }}>·</span>
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "#a78bfa",
              boxShadow: "0 0 6px #a78bfa",
              flexShrink: 0,
            }}
          />
          <span>🎤</span>
        </>
      )}
    </motion.div>
  );
});

export default PrivacyIndicator;
