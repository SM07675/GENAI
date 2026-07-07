// GlowOrb: the centerpiece. A layered, Framer Motion animated orb that reacts
// to the pipeline state (idle/listening/thinking/speaking) and, while
// listening, to live microphone amplitude (the "sound wave" ring).
//
// All animation is GPU-friendly (transform / opacity only) for 60fps.
import { motion } from "framer-motion";
import { ORB_STATES } from "../store/appStore";

// Per-state visual config. Colors shift + the idle/speaking pulse rates differ.
const STATE_CONFIG = {
  [ORB_STATES.IDLE]: {
    from: "#22d3ee", to: "#3b82f6",
    scale: 1.0, pulse: 4.5, glow: 0.5,
  },
  [ORB_STATES.LISTENING]: {
    from: "#22d3ee", to: "#a855f7",
    scale: 1.05, pulse: 1.4, glow: 0.9,
  },
  [ORB_STATES.THINKING]: {
    from: "#a855f7", to: "#ec4899",
    scale: 1.0, pulse: 0.8, glow: 0.95,
  },
  [ORB_STATES.SPEAKING]: {
    from: "#22d3ee", to: "#a855f7",
    scale: 1.08, pulse: 0.6, glow: 1.0,
  },
};

export default function GlowOrb({ state = ORB_STATES.IDLE, amplitude = 0 }) {
  const cfg = STATE_CONFIG[state] || STATE_CONFIG[ORB_STATES.IDLE];

  // The listening state grows the outer ring with mic amplitude; other states
  // use a fixed breathing scale.
  const reactiveScale =
    state === ORB_STATES.LISTENING ? 1 + amplitude * 0.35 : cfg.scale;

  return (
    <div className="relative flex items-center justify-center w-56 h-56 select-none">
      {/* Outer soft halo */}
      <motion.div
        className="absolute inset-0 rounded-full blur-2xl"
        style={{
          background: `radial-gradient(circle, ${cfg.from}55, transparent 70%)`,
        }}
        animate={{ opacity: [cfg.glow * 0.4, cfg.glow, cfg.glow * 0.4], scale: [1, 1.1, 1] }}
        transition={{ duration: cfg.pulse, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Sound-wave ring (only meaningful while listening) */}
      <motion.div
        className="absolute rounded-full border"
        style={{ borderColor: `${cfg.from}66`, width: "70%", height: "70%" }}
        animate={{
          scale: state === ORB_STATES.LISTENING
            ? [1, 1 + amplitude * 0.6, 1]
            : [1, 1.08, 1],
          opacity: [0.7, 0.2, 0.7],
        }}
        transition={{ duration: state === ORB_STATES.LISTENING ? 0.6 : cfg.pulse, repeat: Infinity }}
      />
      <motion.div
        className="absolute rounded-full border"
        style={{ borderColor: `${cfg.to}44`, width: "85%", height: "85%" }}
        animate={{ scale: [1.1, 1, 1.1], opacity: [0.2, 0.5, 0.2] }}
        transition={{ duration: cfg.pulse * 1.3, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Core orb */}
      <motion.div
        className="relative rounded-full"
        style={{
          width: "55%", height: "55%",
          background: `radial-gradient(circle at 35% 30%, #ffffff 0%, ${cfg.from} 35%, ${cfg.to} 75%, #05060f 100%)`,
          boxShadow: `0 0 60px ${cfg.from}aa, inset 0 0 30px ${cfg.to}66`,
        }}
        animate={{ scale: reactiveScale }}
        transition={{ duration: 0.15 }}
      >
        {/* Specular highlight to give it a glassy 3D look */}
        <div
          className="absolute rounded-full"
          style={{
            top: "12%", left: "20%", width: "40%", height: "30%",
            background: "radial-gradient(circle, rgba(255,255,255,0.8), transparent 70%)",
            filter: "blur(2px)",
          }}
        />
      </motion.div>

      {/* Rotating accent ring while thinking */}
      {state === ORB_STATES.THINKING && (
        <motion.div
          className="absolute rounded-full border-2 border-transparent"
          style={{
            width: "92%", height: "92%",
            borderTopColor: cfg.from,
            borderRightColor: cfg.to,
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
        />
      )}
    </div>
  );
}
