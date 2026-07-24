// PinGate: security entry screen — dark aurora theme.
import { useState } from "react";
import { motion } from "framer-motion";

export default function PinGate({ onSubmit }) {
  const [pin, setPin]   = useState(["", "", "", ""]);
  const [error, setError] = useState(false);

  const update = (i, v) => {
    const digit = v.replace(/\D/g, "").slice(-1);
    const next  = [...pin];
    next[i]     = digit;
    setPin(next);
    setError(false);
    if (digit && i < 3) document.getElementById(`pin-${i + 1}`)?.focus();
    if (next.every((d) => d !== "")) onSubmit(next.join(""));
  };

  const onKeyDown = (i, e) => {
    if (e.key === "Backspace" && !pin[i] && i > 0) {
      document.getElementById(`pin-${i - 1}`)?.focus();
    }
  };

  const onPaste = (e) => {
    const text = (e.clipboardData.getData("text") || "").replace(/\D/g, "").slice(0, 4);
    if (text.length === 4) { e.preventDefault(); setPin(text.split("")); onSubmit(text); }
  };

  return (
    <motion.div
      className="flex flex-col items-center justify-center gap-8 px-8 py-12"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Orb */}
      <motion.div
        animate={{ scale: [1, 1.08, 1] }}
        transition={{ duration: 2.8, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          width: 88, height: 88,
          borderRadius: '50%',
          background: 'conic-gradient(from 0deg, #22d3ee, #6366f1, #a855f7, #22d3ee)',
          boxShadow: '0 0 40px rgba(99,102,241,0.45), 0 0 80px rgba(99,102,241,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <div style={{
          width: 72, height: 72, borderRadius: '50%',
          background: 'rgba(7,11,20,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 28, fontWeight: 800, color: '#fff',
        }}>G</div>
      </motion.div>

      {/* Text */}
      <div className="text-center">
        <h1 className="text-3xl font-bold shimmer-text mb-1">Genie</h1>
        <p style={{ color: '#64748b', fontSize: 14 }}>Enter the PIN shown on your PC</p>
      </div>

      {/* PIN inputs */}
      <div className="flex gap-3" onPaste={onPaste} style={{ WebkitAppRegion: "no-drag" }}>
        {pin.map((d, i) => (
          <input
            key={i}
            id={`pin-${i}`}
            value={d}
            onChange={(e) => update(i, e.target.value)}
            onKeyDown={(e) => onKeyDown(i, e)}
            inputMode="numeric"
            maxLength={1}
            style={{
              width: 56, height: 64,
              textAlign: 'center',
              fontSize: 24,
              fontWeight: 700,
              borderRadius: 14,
              background: 'rgba(22,28,52,0.70)',
              backdropFilter: 'blur(20px)',
              color: '#e2e8f0',
              border: `2px solid ${error ? 'rgba(248,113,113,0.6)' : d ? 'rgba(99,102,241,0.6)' : 'rgba(255,255,255,0.09)'}`,
              outline: 'none',
              boxShadow: d ? '0 0 12px rgba(99,102,241,0.25)' : '0 4px 16px rgba(0,0,0,0.3)',
              transition: 'all 0.15s ease',
            }}
          />
        ))}
      </div>

      {error && (
        <motion.p
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ color: '#f87171', fontSize: 13 }}
        >
          Incorrect PIN — try again.
        </motion.p>
      )}
    </motion.div>
  );
}
