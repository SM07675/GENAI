// PinGate: the security entry screen. Mobile users must enter the 4-digit PIN
// (shown in the desktop Electron UI) before the WebSocket connects.
import { useState } from "react";
import { motion } from "framer-motion";

export default function PinGate({ onSubmit }) {
  const [pin, setPin] = useState(["", "", "", ""]);
  const [error, setError] = useState(false);

  const update = (i, v) => {
    const digit = v.replace(/\D/g, "").slice(-1);
    const next = [...pin];
    next[i] = digit;
    setPin(next);
    setError(false);
    if (digit && i < 3) {
      document.getElementById(`pin-${i + 1}`)?.focus();
    }
    // Auto-submit when all four digits are present.
    if (next.every((d) => d !== "")) {
      onSubmit(next.join(""));
    }
  };

  const onKeyDown = (i, e) => {
    if (e.key === "Backspace" && !pin[i] && i > 0) {
      document.getElementById(`pin-${i - 1}`)?.focus();
    }
  };

  const onPaste = (e) => {
    const text = (e.clipboardData.getData("text") || "").replace(/\D/g, "").slice(0, 4);
    if (text.length === 4) {
      e.preventDefault();
      setPin(text.split(""));
      onSubmit(text);
    }
  };

  return (
    <motion.div
      className="flex flex-col items-center justify-center h-full gap-8 px-8"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      <motion.div
        className="w-24 h-24 rounded-full bg-gradient-to-br from-neon-cyan to-neon-violet shadow-glow"
        animate={{ scale: [1, 1.08, 1], opacity: [0.8, 1, 0.8] }}
        transition={{ duration: 2.4, repeat: Infinity }}
      />
      <div className="text-center">
        <h1 className="text-3xl font-semibold neon-text">Genie</h1>
        <p className="text-sm text-gray-400 mt-1">Enter the PIN shown on your PC</p>
      </div>

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
            className={`w-14 h-16 text-center text-2xl font-bold rounded-xl bg-space-800/70 border-2
              outline-none transition-all focus:shadow-glow
              ${error ? "border-neon-pink" : "border-white/10 focus:border-neon-cyan"}`}
          />
        ))}
      </div>
      {error && <p className="text-neon-pink text-sm">Incorrect PIN. Try again.</p>}
    </motion.div>
  );
}
