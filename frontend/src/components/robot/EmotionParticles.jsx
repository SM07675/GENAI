/**
 * EmotionParticles — lightweight HTML/Framer Motion overlay particles.
 *
 * Rendered as absolutely-positioned elements over the SVG robot.
 * Avoids canvas and heavy particle systems. Each particle is a small
 * motion.div or motion.span with a short lifecycle via AnimatePresence.
 *
 * Particle types by emotion:
 * - 'excited' / 'success' → ✦ star sparkles (6–8, scatter around robot)
 * - 'loving'              → ♥ hearts (4, float upward)
 * - 'sleepy'              → Z Z Z (3, drift upward slowly)
 * - Others                → no particles
 *
 * Particle lifetime: 1.2–2.0 s. For looping emotions (loving, sleepy),
 * particles re-spawn continuously via key cycling.
 */
import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// Sparkle positions (relative to robot center = 50%)
const STAR_POSITIONS = [
  { x: -52, y: -65, delay: 0.0, char: '✦', size: 10 },
  { x:  48, y: -70, delay: 0.15, char: '✦', size: 8  },
  { x: -68, y: -30, delay: 0.3,  char: '✧', size: 7  },
  { x:  62, y: -40, delay: 0.1,  char: '✦', size: 9  },
  { x: -30, y: -82, delay: 0.25, char: '✧', size: 7  },
  { x:  28, y: -80, delay: 0.4,  char: '✦', size: 8  },
];

const HEART_POSITIONS = [
  { x: -45, y: 0, delay: 0.0  },
  { x:  45, y: 0, delay: 0.2  },
  { x: -20, y: -20, delay: 0.4 },
  { x:  20, y: -20, delay: 0.6 },
];

const Z_POSITIONS = [
  { x: 48,  y: -50, delay: 0.0, size: 16 },
  { x: 60,  y: -80, delay: 0.6, size: 12 },
  { x: 72,  y: -108, delay: 1.2, size: 9 },
];

function StarParticle({ x, y, delay, char, size }) {
  return (
    <motion.span
      initial={{ opacity: 0, x, y: y + 10, scale: 0 }}
      animate={{ opacity: [0, 1, 0], y: y - 8, scale: [0, 1.3, 0.9, 0] }}
      exit={{ opacity: 0 }}
      transition={{ duration: 1.4, delay, ease: 'easeOut' }}
      style={{
        position: 'absolute',
        left: '50%',
        top: '50%',
        color: '#fde68a',
        fontSize: size,
        pointerEvents: 'none',
        filter: 'drop-shadow(0 0 4px #fde68a)',
        userSelect: 'none',
      }}
    >
      {char}
    </motion.span>
  );
}

function HeartParticle({ x, y, delay }) {
  return (
    <motion.span
      initial={{ opacity: 0, x, y, scale: 0 }}
      animate={{ opacity: [0, 1, 0.8, 0], y: y - 50, scale: [0, 1, 0.8, 0] }}
      exit={{ opacity: 0 }}
      transition={{ duration: 1.8, delay, ease: 'easeOut' }}
      style={{
        position: 'absolute',
        left: '50%',
        top: '50%',
        color: '#f472b6',
        fontSize: 14,
        pointerEvents: 'none',
        filter: 'drop-shadow(0 0 3px #f472b6)',
        userSelect: 'none',
      }}
    >
      ♥
    </motion.span>
  );
}

function ZParticle({ x, y, delay, size }) {
  return (
    <motion.span
      initial={{ opacity: 0, x, y: y + 5, scale: 0.5 }}
      animate={{ opacity: [0, 0.9, 0.7, 0], y: y - 20, scale: [0.5, 1, 0.9, 0] }}
      exit={{ opacity: 0 }}
      transition={{ duration: 2.5, delay, ease: 'easeOut' }}
      style={{
        position: 'absolute',
        left: '50%',
        top: '45%',
        color: '#818cf8',
        fontSize: size,
        fontWeight: 700,
        fontStyle: 'italic',
        pointerEvents: 'none',
        userSelect: 'none',
      }}
    >
      Z
    </motion.span>
  );
}

export default function EmotionParticles({ emotion }) {
  // For repeating particle systems (loving, sleepy), we cycle a key to re-trigger
  const [cycle, setCycle] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (emotion === 'loving' || emotion === 'sleepy') {
      timerRef.current = setInterval(() => setCycle((c) => c + 1), 2200);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [emotion]);

  const showStars  = emotion === 'excited' || emotion === 'success';
  const showHearts = emotion === 'loving';
  const showZs     = emotion === 'sleepy';

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        overflow: 'visible',
      }}
    >
      <AnimatePresence>
        {showStars && (
          STAR_POSITIONS.map((p, i) => (
            <StarParticle key={`star-${i}`} {...p} />
          ))
        )}
        {showHearts && (
          HEART_POSITIONS.map((p, i) => (
            <HeartParticle key={`heart-${cycle}-${i}`} {...p} />
          ))
        )}
        {showZs && (
          Z_POSITIONS.map((p, i) => (
            <ZParticle key={`z-${cycle}-${i}`} {...p} />
          ))
        )}
      </AnimatePresence>
    </div>
  );
}
