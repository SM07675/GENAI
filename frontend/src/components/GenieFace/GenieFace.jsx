import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useAppStore } from "../../store/appStore";

export default function GenieFace() {
  const genieState = useAppStore((s) => s.genieState);
  
  // Map genieState to AuraRobot expression
  const mapStateToExpression = (state) => {
    switch(state) {
      case 'listening': return 'listening';
      case 'thinking': return 'thinking';
      case 'speaking': return 'happy';
      case 'sleeping': return 'calm';
      case 'waking': return 'love'; // Waking can be love or calm
      default: return 'happy';
    }
  };

  const expression = mapStateToExpression(genieState);
  const [blink, setBlink] = useState(false);

  // Natural blinking
  useEffect(() => {
    let timeout;
    const loop = () => {
      const next = 2200 + Math.random() * 2600;
      timeout = setTimeout(() => {
        setBlink(true);
        setTimeout(() => setBlink(false), 140);
        loop();
      }, next);
    };
    loop();
    return () => clearTimeout(timeout);
  }, []);

  const eyeHeight = blink ? 4 : 34;
  const cheekGlow =
    expression === "love" ? "#ff8fc7" : expression === "calm" ? "#8B5CF6" : "#5EEAD4";

  return (
    <div className="relative flex items-center justify-center select-none" style={{ width: 320, height: 360 }}>
      {/* Ambient bloom behind robot */}
      <motion.div
        className="absolute rounded-full pointer-events-none"
        style={{
          width: 300,
          height: 300,
          background:
            "radial-gradient(circle, rgba(94,234,212,0.45), rgba(78,168,255,0.4) 45%, transparent 70%)",
          filter: "blur(30px)",
        }}
        animate={{ scale: [1, 1.12, 1], opacity: [0.7, 1, 0.7] }}
        transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Orbiting thinking particles */}
      {expression === "thinking" &&
        [0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="absolute rounded-full"
            style={{
              width: 10,
              height: 10,
              background: "linear-gradient(135deg,#00D4FF,#8B5CF6)",
              top: 40,
            }}
            animate={{ rotate: 360 }}
            transition={{ duration: 3, repeat: Infinity, ease: "linear", delay: i * 0.4 }}
          />
        ))}

      {/* Floating body */}
      <motion.div
        className="relative"
        animate={{ y: [0, -14, 0] }}
        transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
      >
        <svg width="240" height="270" viewBox="0 0 240 270" fill="none">
          <defs>
            <linearGradient id="bodyGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ffffff" />
              <stop offset="55%" stopColor="#f4f7ff" />
              <stop offset="100%" stopColor="#dbe6ff" />
            </linearGradient>
            <radialGradient id="faceGlow" cx="50%" cy="45%" r="60%">
              <stop offset="0%" stopColor="#101826" />
              <stop offset="100%" stopColor="#03060d" />
            </radialGradient>
            <filter id="soft" x="-40%" y="-40%" width="180%" height="180%">
              <feDropShadow dx="0" dy="18" stdDeviation="18" floodColor="#2458FF" floodOpacity="0.28" />
            </filter>
          </defs>

          {/* Tiny arms */}
          <motion.ellipse
            cx="34" cy="150" rx="16" ry="26" fill="url(#bodyGrad)"
            animate={{ rotate: expression === "happy" || expression === "love" ? [-8, 12, -8] : [0, 4, 0] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
            style={{ transformOrigin: "34px 130px" }}
          />
          <motion.ellipse
            cx="206" cy="150" rx="16" ry="26" fill="url(#bodyGrad)"
            animate={{ rotate: expression === "happy" || expression === "love" ? [8, -12, 8] : [0, -4, 0] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
            style={{ transformOrigin: "206px 130px" }}
          />

          {/* Head / body — one rounded glossy capsule */}
          <rect x="46" y="34" width="148" height="180" rx="74" fill="url(#bodyGrad)" filter="url(#soft)" />
          {/* Specular highlight */}
          <ellipse cx="90" cy="70" rx="34" ry="18" fill="#ffffff" opacity="0.7" />

          {/* Perfect circular OLED face */}
          <circle cx="120" cy="112" r="60" fill="url(#faceGlow)" />
          <circle cx="120" cy="112" r="60" fill="none" stroke="#2b3550" strokeWidth="2" />

          {/* Listening ring */}
          {expression === "listening" && (
            <motion.circle
              cx="120" cy="112" r="66" fill="none" stroke="#00D4FF" strokeWidth="3"
              initial={{ opacity: 0.9, r: 62 }}
              animate={{ opacity: [0.9, 0], r: [62, 82] }}
              transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
            />
          )}
        </svg>

        {/* Face features rendered as HTML for easy animation */}
        <div className="absolute inset-0 flex flex-col items-center" style={{ top: 52 }}>
          {expression === "love" ? (
            <div className="flex gap-4" style={{ marginTop: 34 }}>
              {[0, 1].map((i) => (
                <motion.div
                  key={i}
                  animate={{ scale: [1, 1.18, 1] }}
                  transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
                  style={{ color: "#ff8fc7", fontSize: 26 }}
                >
                  ♥
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-5" style={{ marginTop: 34 }}>
              {[0, 1].map((i) => (
                <motion.div
                  key={i}
                  style={{
                    width: 20,
                    borderRadius: 10,
                    background: "linear-gradient(180deg,#8fefff,#00D4FF)",
                    boxShadow: "0 0 14px rgba(0,212,255,0.9)",
                  }}
                  animate={{ height: eyeHeight }}
                  transition={{ duration: 0.1 }}
                />
              ))}
            </div>
          )}

          {/* Mouth / smile */}
          <motion.div
            style={{
              marginTop: 10,
              width: expression === "listening" ? 10 : 26,
              height: expression === "listening" ? 10 : 12,
              borderBottom: "3px solid #00D4FF",
              borderRadius: expression === "listening" ? "50%" : "0 0 20px 20px",
              boxShadow: "0 2px 8px rgba(0,212,255,0.6)",
            }}
            animate={
              expression === "happy" || expression === "love"
                ? { scaleY: [1, 0.4, 1] }
                : { scaleY: 1 }
            }
            transition={{ duration: 0.4, repeat: Infinity }}
          />

          {/* Glowing cheeks */}
          <div className="flex justify-between w-full absolute" style={{ top: 44, paddingInline: 66 }}>
            {[0, 1].map((i) => (
              <div
                key={i}
                style={{
                  width: 14,
                  height: 8,
                  borderRadius: 8,
                  background: cheekGlow,
                  filter: "blur(2px)",
                  opacity: 0.85,
                }}
              />
            ))}
          </div>
        </div>
      </motion.div>

      {/* Reflective platform */}
      <motion.div
        className="absolute rounded-full pointer-events-none"
        style={{
          bottom: 20,
          width: 180,
          height: 26,
          background: "radial-gradient(ellipse, rgba(78,168,255,0.35), transparent 70%)",
          filter: "blur(6px)",
        }}
        animate={{ scaleX: [1, 0.86, 1], opacity: [0.6, 0.4, 0.6] }}
        transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}
