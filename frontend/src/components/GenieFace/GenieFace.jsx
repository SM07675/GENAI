/**
 * GenieFace.jsx — Premium 2D Animated Companion Avatar
 *
 * Architecture:
 * - CSS + SVG + Framer Motion: pure 2D, lightweight, no WebGL overhead
 * - Full emotional state system with smooth transitions
 * - Audio-driven lip-sync via useAudioLipSync
 * - Natural blinking, head micro-movements, eye tracking
 * - Gesture system: idle, thinking orbit, listening ripple, speaking waves
 * - Particle/glow effects per state
 *
 * Props:
 *   size        — diameter of the face area (default 280)
 *   showBody    — whether to show the body/torso below the face (default true)
 *   minimal     — compact mode for floating companion (default false)
 */
import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { motion, AnimatePresence, useMotionValue, useSpring, animate } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import { useAudioLipSync } from '../../hooks/useAudioLipSync';

// ── Expression mapping ──────────────────────────────────────────────────────

/**
 * Map from Genie pipeline state → companion expression.
 * Each expression drives color, eye shape, mouth shape, and animations.
 */
const STATE_TO_EXPRESSION = {
  idle:               'idle',
  sleeping:           'sleeping',
  waking:             'waking',
  listening:          'listening',
  follow_up_listening:'listening',
  transcribing:       'thinking',
  thinking:           'thinking',
  executing:          'thinking',
  speaking:           'speaking',
  success:            'happy',
  error:              'confused',
  interrupted:        'surprised',
  initializing:       'idle',
  offline:            'sleeping',
};

// ── Theme / color per expression ─────────────────────────────────────────────

const EXPRESSION_THEME = {
  idle: {
    primary:  '#2998FF',   // sky blue
    glow:     'rgba(41,152,255,0.35)',
    face:     'linear-gradient(150deg, #FFFFFF 0%, #EAF8FF 45%, #BFEAFF 100%)',
    eyeColor: '#0B5ED7',
    bodyGrad: ['#f0f9ff', '#e0f2fe', '#bae6fd'],
  },
  sleeping: {
    primary:  '#8B7FE8',   // soft indigo
    glow:     'rgba(139,127,232,0.22)',
    face:     'linear-gradient(150deg, #FFFFFF 0%, #F3F1FF 50%, #DCD9FF 100%)',
    eyeColor: '#6D5FD1',
    bodyGrad: ['#f5f3ff', '#ede9fe', '#ddd6fe'],
  },
  waking: {
    primary:  '#2998FF',
    glow:     'rgba(41,152,255,0.5)',
    face:     'linear-gradient(150deg, #FFFFFF 0%, #EAF8FF 40%, #9FE0FF 100%)',
    eyeColor: '#0B5ED7',
    bodyGrad: ['#f0f9ff', '#e0f2fe', '#bae6fd'],
  },
  listening: {
    primary:  '#12B8D6',   // cyan
    glow:     'rgba(18,184,214,0.5)',
    face:     'linear-gradient(150deg, #FFFFFF 0%, #E3FBFF 40%, #8FE9FF 100%)',
    eyeColor: '#0A7C92',
    bodyGrad: ['#ecfeff', '#cffafe', '#a5f3fc'],
  },
  thinking: {
    primary:  '#2998FF',   // sky blue pulse
    glow:     'rgba(41,152,255,0.5)',
    face:     'linear-gradient(150deg, #FFFFFF 0%, #EAF8FF 42%, #BFEAFF 100%)',
    eyeColor: '#0B5ED7',
    bodyGrad: ['#f0f9ff', '#e0f2fe', '#bae6fd'],
  },
  speaking: {
    primary:  '#1FB988',   // mint
    glow:     'rgba(31,185,136,0.4)',
    face:     'linear-gradient(150deg, #FFFFFF 0%, #EAFFF6 40%, #9BEFD1 100%)',
    eyeColor: '#0E8A63',
    bodyGrad: ['#ecfdf5', '#d1fae5', '#a7f3d0'],
  },
  happy: {
    primary:  '#2998FF',
    glow:     'rgba(41,152,255,0.45)',
    face:     'linear-gradient(150deg, #FFFFFF 0%, #EAF8FF 45%, #BFEAFF 100%)',
    eyeColor: '#0B5ED7',
    bodyGrad: ['#f0f9ff', '#e0f2fe', '#bae6fd'],
  },
  excited: {
    primary:  '#2998FF',
    glow:     'rgba(41,152,255,0.6)',
    face:     'linear-gradient(150deg, #FFFFFF 0%, #DDF3FF 35%, #72D4FF 100%)',
    eyeColor: '#0B5ED7',
    bodyGrad: ['#f0f9ff', '#e0f2fe', '#bae6fd'],
  },
  confused: {
    primary:  '#E4536B',
    glow:     'rgba(228,83,107,0.3)',
    face:     'linear-gradient(150deg, #FFFFFF 0%, #FFF1F2 45%, #FFD3D8 100%)',
    eyeColor: '#C23A52',
    bodyGrad: ['#fff1f2', '#ffe4e6', '#fecdd3'],
  },
  surprised: {
    primary:  '#2998FF',
    glow:     'rgba(41,152,255,0.55)',
    face:     'linear-gradient(150deg, #FFFFFF 0%, #EAF8FF 38%, #BFEAFF 100%)',
    eyeColor: '#0B5ED7',
    bodyGrad: ['#f0f9ff', '#e0f2fe', '#bae6fd'],
  },
  concerned: {
    primary:  '#4C7FE0',
    glow:     'rgba(76,127,224,0.3)',
    face:     'linear-gradient(150deg, #FFFFFF 0%, #EFF6FF 45%, #C7DBFF 100%)',
    eyeColor: '#2E52B8',
    bodyGrad: ['#eff6ff', '#dbeafe', '#bfdbfe'],
  },
};

// ── Blink pattern presets per expression ─────────────────────────────────────

const BLINK_INTERVAL = {
  idle:      [3000, 5000],
  sleeping:  [0,    0],     // eyes closed
  waking:    [500,  1500],  // rapid blinking
  listening: [2000, 4000],
  thinking:  [4000, 8000],  // focused, rarely blinks
  speaking:  [1800, 3000],
  happy:     [1500, 3000],
  excited:   [800,  2000],
  confused:  [2000, 4000],
  surprised: [3000, 6000],  // wide eyes, delayed blink
  concerned: [2500, 4500],
};

// ── Eye shape per expression ──────────────────────────────────────────────────

const EYE_SHAPE = {
  idle:      { ry: 0.9, rx: 1.0, yOffset: 0,  squint: 0 },
  sleeping:  { ry: 0.1, rx: 1.0, yOffset: 3,  squint: 0 },
  waking:    { ry: 1.1, rx: 1.0, yOffset: -1, squint: 0 },
  listening: { ry: 1.0, rx: 1.0, yOffset: 0,  squint: 0 },
  thinking:  { ry: 0.85,rx: 0.9, yOffset: -2, squint: 0.1 },
  speaking:  { ry: 0.95,rx: 1.0, yOffset: 0,  squint: 0 },
  happy:     { ry: 0.5, rx: 1.1, yOffset: 1,  squint: 0.3 },   // squinting happy
  excited:   { ry: 1.2, rx: 1.1, yOffset: -2, squint: 0 },      // wide!
  confused:  { ry: 0.9, rx: 0.9, yOffset: 0,  squint: 0.1 },
  surprised: { ry: 1.3, rx: 1.1, yOffset: -3, squint: 0 },      // very wide
  concerned: { ry: 0.95,rx: 1.0, yOffset: 1,  squint: 0.05 },
};

// ── Head sway presets ─────────────────────────────────────────────────────────

const HEAD_SWAY = {
  idle:      { x: [-2, 2, -2],  y: [0, -8, 0],   d: 5.5 },
  sleeping:  { x: [0, 3, 0],    y: [4, 8, 4],    d: 4.5 },
  waking:    { x: [-3, 3, -3],  y: [-4, 0, -4],  d: 1.2 },
  listening: { x: [-3, 3, -3],  y: [0, -6, 0],   d: 4.0 },
  thinking:  { x: [0, -4, 0],   y: [-2, -6, -2], d: 3.5 },
  speaking:  { x: [-3, 3, -3],  y: [-2, -8, -2], d: 3.0 },
  happy:     { x: [-4, 4, -4],  y: [-4, -10,-4], d: 3.0 },
  excited:   { x: [-6, 6, -6],  y: [-6, -12,-6], d: 1.8 },
  confused:  { x: [0, -6, 0],   y: [0, -2, 0],   d: 4.0 },
  surprised: { x: [-2, 2, -2],  y: [-6, -10,-6], d: 2.0 },
  concerned: { x: [-2, 2, -2],  y: [2, -4, 2],   d: 4.5 },
};

// ── Mouth curve per expression ────────────────────────────────────────────────

// SVG path for 50x25 viewBox mouth
const MOUTH_PATH = {
  idle:      'M 10 10 Q 25 18 40 10',         // small smile
  sleeping:  'M 15 10 Q 25 15 35 10',         // tiny peaceful curve
  waking:    'M 8 6 Q 25 20 42 6',            // yawning/opening
  listening: 'M 12 10 Q 25 16 38 10',         // soft curve
  thinking:  'M 18 12 Q 25 9 32 12',          // small flat tilt
  speaking:  'M 10 12 Q 25 18 40 12',         // speaking
  happy:     'M 8 6 Q 25 22 42 6',            // big smile
  excited:   'M 8 5 Q 25 24 42 5',            // huge smile
  confused:  'M 14 14 Q 25 9 36 16',          // tilted
  surprised: 'M 22 5 A 6 7 0 1 0 28 5 A 6 7 0 1 0 22 5', // O
  concerned: 'M 12 14 Q 25 9 38 14',          // slight frown
};


// ═══════════════════════════════════════════════════════════════════════════════
// Main GenieFace Component
// ═══════════════════════════════════════════════════════════════════════════════

export default function GenieFace({ size = 280, showBody = true, minimal = false }) {
  const genieState = useAppStore((s) => s.genieState);
  const isTTSPlaying = useAppStore((s) => s.isTTSPlaying);
  const assistantAudioElement = useAppStore((s) => s.assistantAudioElement);

  // Lip-sync from audio analyser
  const mouthOpennessRef = useAudioLipSync(assistantAudioElement);

  // Current expression
  const expression = STATE_TO_EXPRESSION[genieState] ?? 'idle';
  const theme = EXPRESSION_THEME[expression] ?? EXPRESSION_THEME.idle;
  const eyeShape = EYE_SHAPE[expression] ?? EYE_SHAPE.idle;
  const sway = HEAD_SWAY[expression] ?? HEAD_SWAY.idle;

  // Blinking state
  const [isBlinking, setIsBlinking] = useState(false);
  const blinkTimeoutRef = useRef(null);

  // Eye gaze (micro-random movement)
  const gazeX = useMotionValue(0);
  const gazeY = useMotionValue(0);
  const springGazeX = useSpring(gazeX, { stiffness: 80, damping: 18 });
  const springGazeY = useSpring(gazeY, { stiffness: 80, damping: 18 });

  // Mouth openness (from TTS audio)
  const mouthAnimRef = useRef(null);
  const [mouthOpen, setMouthOpen] = useState(0);

  // ── Blinking logic ─────────────────────────────────────────────────────────
  useEffect(() => {
    const [minMs, maxMs] = BLINK_INTERVAL[expression] ?? [3000, 5000];

    if (minMs === 0) {
      // Force-closed (sleeping) — no blinking loop
      setIsBlinking(true);
      return () => {};
    }

    setIsBlinking(false);

    const schedule = () => {
      const delay = minMs + Math.random() * (maxMs - minMs);
      blinkTimeoutRef.current = setTimeout(() => {
        setIsBlinking(true);
        setTimeout(() => {
          setIsBlinking(false);
          schedule();
        }, 110 + Math.random() * 60);
      }, delay);
    };

    schedule();
    return () => clearTimeout(blinkTimeoutRef.current);
  }, [expression]);

  // ── Eye micro-gaze ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (expression === 'sleeping') {
      gazeX.set(0);
      gazeY.set(0);
      return;
    }

    const randomGaze = () => {
      const nx = (Math.random() - 0.5) * 6;
      const ny = (Math.random() - 0.5) * 4;
      gazeX.set(nx);
      gazeY.set(ny);
    };

    const interval = setInterval(randomGaze, 1500 + Math.random() * 2000);
    return () => clearInterval(interval);
  }, [expression, gazeX, gazeY]);

  // ── Mouth lip-sync loop ───────────────────────────────────────────────────
  useEffect(() => {
    if (!isTTSPlaying) {
      setMouthOpen(0);
      return;
    }

    const tick = () => {
      const raw = mouthOpennessRef?.current ?? 0;
      setMouthOpen(raw);
      mouthAnimRef.current = requestAnimationFrame(tick);
    };
    mouthAnimRef.current = requestAnimationFrame(tick);
    return () => {
      if (mouthAnimRef.current) cancelAnimationFrame(mouthAnimRef.current);
    };
  }, [isTTSPlaying, mouthOpennessRef]);

  // ── Derived dimensions ────────────────────────────────────────────────────
  const faceR = size * 0.42;           // face circle radius
  const eyeW  = size * 0.09;          // eye width
  const eyeH  = size * 0.115;         // eye max-height
  const eyeSep = size * 0.19;         // eye separation from center

  // ── Particle props ────────────────────────────────────────────────────────
  const orbitParticles = [0, 1, 2];

  // ── Speaking mouth height from lip-sync ──────────────────────────────────
  const speakingMouthH = eyeH * 0.4 + mouthOpen * eyeH * 0.6;

  const isMinimal = minimal;

  return (
    <div
      className="relative flex flex-col items-center justify-center select-none"
      style={{
        width: size,
        height: showBody ? size * 1.3 : size,
      }}
    >
      {/* ── Ambient background bloom ──────────────────────────────────────── */}
      <motion.div
        className="absolute pointer-events-none rounded-full"
        style={{
          width: size * 1.4,
          height: size * 1.4,
          top: '50%',
          left: '50%',
          x: '-50%',
          y: '-50%',
          background: `radial-gradient(circle, ${theme.glow} 0%, transparent 70%)`,
          filter: `blur(${size * 0.1}px)`,
        }}
        animate={{
          opacity: [0.6, 1, 0.6],
          scale: [1, 1.08, 1],
        }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* ── Thinking orbit particles ──────────────────────────────────────── */}
      <AnimatePresence>
        {expression === 'thinking' && orbitParticles.map((i) => (
          <motion.div
            key={`orbit-${i}`}
            className="absolute pointer-events-none rounded-full"
            style={{
              width: size * 0.03,
              height: size * 0.03,
              background: theme.primary,
              boxShadow: `0 0 ${size * 0.02}px ${theme.primary}`,
              top: '50%',
              left: '50%',
              marginLeft: -size * 0.015,
              marginTop: -size * 0.015,
            }}
            initial={{ opacity: 0 }}
            animate={{
              opacity: [0, 1, 0.8, 1, 0],
              rotate: 360,
              x: Math.cos((i * 2 * Math.PI) / 3) * size * 0.45,
              y: Math.sin((i * 2 * Math.PI) / 3) * size * 0.45,
            }}
            exit={{ opacity: 0 }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: 'linear',
              delay: i * 1,
              rotate: { duration: 2.5, repeat: Infinity, ease: 'linear', delay: i * 0.83 },
            }}
          />
        ))}
      </AnimatePresence>

      {/* ── Listening ripple rings ────────────────────────────────────────── */}
      <AnimatePresence>
        {expression === 'listening' && [0, 1, 2].map((i) => (
          <motion.div
            key={`ripple-${i}`}
            className="absolute pointer-events-none rounded-full"
            style={{
              border: `2px solid ${theme.primary}`,
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
            }}
            initial={{ width: size * 0.85, height: size * 0.85, opacity: 0.7 }}
            animate={{ width: size * 1.5, height: size * 1.5, opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'easeOut', delay: i * 0.6 }}
          />
        ))}
      </AnimatePresence>

      {/* ── Excited bounce energy sparks ─────────────────────────────────── */}
      <AnimatePresence>
        {expression === 'excited' && [0, 1, 2, 3, 4].map((i) => {
          const angle = (i / 5) * Math.PI * 2;
          return (
            <motion.div
              key={`spark-${i}`}
              className="absolute pointer-events-none rounded-full"
              style={{
                width: size * 0.025,
                height: size * 0.025,
                background: theme.primary,
                boxShadow: `0 0 8px ${theme.primary}`,
                top: '50%',
                left: '50%',
              }}
              initial={{ x: 0, y: 0, opacity: 1, scale: 1 }}
              animate={{
                x: [0, Math.cos(angle) * size * 0.55],
                y: [0, Math.sin(angle) * size * 0.55],
                opacity: [1, 0],
                scale: [1, 0.3],
              }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.2, repeat: Infinity, ease: 'easeOut', delay: i * 0.24 }}
            />
          );
        })}
      </AnimatePresence>

      {/* ── Head / Face container (floats and sways) ─────────────────────── */}
      <motion.div
        className="relative"
        style={{ zIndex: 2 }}
        animate={{
          x: sway.x,
          y: sway.y,
        }}
        transition={{ duration: sway.d, repeat: Infinity, ease: 'easeInOut' }}
      >
        {/* Face backdrop glow ring */}
        <motion.div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: size * 0.86,
            height: size * 0.86,
            top: '50%',
            left: '50%',
            x: '-50%',
            y: '-50%',
            border: `2px solid ${theme.primary}`,
            opacity: 0.25,
          }}
          animate={{ opacity: [0.15, 0.4, 0.15], scale: [1, 1.04, 1] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
        />

        {/* ── FACE CIRCLE ──────────────────────────────────────────────── */}
        <motion.div
          style={{
            width: size * 0.84,
            height: size * 0.84,
            borderRadius: '50%',
            background: theme.face,
            border: `2px solid ${theme.primary}33`,
            boxShadow: `0 0 ${size * 0.12}px ${theme.glow}, 0 ${size * 0.03}px ${size * 0.1}px rgba(15,43,85,0.12), inset 0 ${size * 0.025}px ${size * 0.1}px rgba(255,255,255,0.95), inset 0 -${size * 0.06}px ${size * 0.12}px ${theme.primary}22`,
            position: 'relative',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          animate={expression === 'excited' ? { scale: [1, 1.03, 1] } : {}}
          transition={{ duration: 0.5, repeat: Infinity, ease: 'easeInOut' }}
        >
          {/* Face scanline overlay */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background: `repeating-linear-gradient(
                0deg,
                transparent,
                transparent 2px,
                ${theme.primary}06 2px,
                ${theme.primary}06 4px
              )`,
              borderRadius: '50%',
            }}
          />

          {/* ── EYES container ─────────────────────────────────────────── */}
          <div
            style={{
              display: 'flex',
              gap: eyeSep,
              marginTop: size * -0.04,
              position: 'relative',
              zIndex: 5,
            }}
          >
            {/* Left Eye */}
            <GenieEye
              side="left"
              size={size}
              eyeW={eyeW}
              eyeH={eyeH}
              shape={eyeShape}
              blinking={isBlinking}
              gazeX={springGazeX}
              gazeY={springGazeY}
              color={theme.eyeColor}
              expression={expression}
            />
            {/* Right Eye */}
            <GenieEye
              side="right"
              size={size}
              eyeW={eyeW}
              eyeH={eyeH}
              shape={eyeShape}
              blinking={isBlinking}
              gazeX={springGazeX}
              gazeY={springGazeY}
              color={theme.eyeColor}
              expression={expression}
            />
          </div>

          {/* ── MOUTH ──────────────────────────────────────────────────── */}
          <div style={{ marginTop: size * 0.06, position: 'relative', zIndex: 5 }}>
            <GenieMouthNew
              expression={expression}
              isSpeaking={isTTSPlaying}
              mouthOpen={mouthOpen}
              size={size}
              color={theme.primary}
            />
          </div>

          {/* ── NOSE dot (subtle) ──────────────────────────────────────── */}
          {!isMinimal && (
            <div
              style={{
                width: size * 0.015,
                height: size * 0.015,
                borderRadius: '50%',
                background: theme.primary,
                opacity: 0.4,
                marginBottom: size * 0.01,
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%) translateY(-8px)',
              }}
            />
          )}

          {/* ── Cheek blush ────────────────────────────────────────────── */}
          {(expression === 'happy' || expression === 'excited' || expression === 'waking') && (
            <>
              <motion.div
                className="absolute"
                style={{
                  width: size * 0.12,
                  height: size * 0.045,
                  borderRadius: '50%',
                  background: 'rgba(251,113,133,0.5)',
                  filter: `blur(${size * 0.016}px)`,
                  left: '18%',
                  top: '58%',
                }}
                animate={{ opacity: [0.4, 0.7, 0.4] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
              <motion.div
                className="absolute"
                style={{
                  width: size * 0.12,
                  height: size * 0.045,
                  borderRadius: '50%',
                  background: 'rgba(251,113,133,0.5)',
                  filter: `blur(${size * 0.016}px)`,
                  right: '18%',
                  top: '58%',
                }}
                animate={{ opacity: [0.4, 0.7, 0.4] }}
                transition={{ duration: 1.5, repeat: Infinity, delay: 0.2 }}
              />
            </>
          )}

          {/* ── Sleeping ZZZ ───────────────────────────────────────────── */}
          <AnimatePresence>
            {expression === 'sleeping' && (
              <motion.div
                key="sleeping-z1"
                className="absolute"
                style={{ top: '15%', right: '20%', color: theme.primary, fontSize: size * 0.08, fontWeight: 700 }}
                initial={{ opacity: 0, scale: 0.5, y: 0 }}
                animate={{ opacity: [0, 1, 0], y: -size * 0.12, scale: [0.5, 0.9, 0.5] }}
                exit={{ opacity: 0 }}
                transition={{ duration: 2, repeat: Infinity, delay: 0.5 }}
              >
                z
              </motion.div>
            )}
            {expression === 'sleeping' && (
              <motion.div
                key="sleeping-z2"
                className="absolute"
                style={{ top: '8%', right: '12%', color: theme.primary, fontSize: size * 0.11, fontWeight: 700 }}
                initial={{ opacity: 0, scale: 0.5, y: 0 }}
                animate={{ opacity: [0, 1, 0], y: -size * 0.14, scale: [0.5, 1, 0.5] }}
                exit={{ opacity: 0 }}
                transition={{ duration: 2, repeat: Infinity, delay: 1.0 }}
              >
                Z
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Thinking question marks / dots ─────────────────────────── */}
          <AnimatePresence>
            {expression === 'thinking' && (
              <motion.div
                key="thinking-qmark"
                className="absolute"
                style={{ top: '10%', right: '15%', color: theme.primary, fontSize: size * 0.09 }}
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: [0, 1, 0.8, 1, 0], scale: [0.6, 1, 0.8, 1, 0.6], y: [0, -size * 0.08] }}
                exit={{ opacity: 0 }}
                transition={{ duration: 2.5, repeat: Infinity }}
              >
                ?
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Confused forehead sweat ─────────────────────────────────── */}
          <AnimatePresence>
            {expression === 'confused' && (
              <motion.div
                key="confused-sweat"
                className="absolute rounded-full"
                style={{
                  width: size * 0.025,
                  height: size * 0.04,
                  background: 'rgba(147,197,253,0.8)',
                  left: '28%',
                  top: '25%',
                  borderRadius: '50%',
                }}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: [0, 1, 1, 0], y: [0, size * 0.05] }}
                exit={{ opacity: 0 }}
                transition={{ duration: 1.2, repeat: Infinity, delay: 0.8 }}
              />
            )}
          </AnimatePresence>

          {/* ── Face inner glow (state-specific) ───────────────────────── */}
          <div
            className="absolute inset-0 pointer-events-none rounded-full"
            style={{
              background: `radial-gradient(circle at 50% 40%, ${theme.primary}10, transparent 70%)`,
            }}
          />
        </motion.div>
      </motion.div>

      {/* ── Body (if showBody) ─────────────────────────────────────────────── */}
      {showBody && !isMinimal && (
        <BodySection size={size} theme={theme} expression={expression} sway={sway} />
      )}

      {/* ── State label badge ─────────────────────────────────────────────── */}
      {!isMinimal && (
        <StateLabel expression={expression} theme={theme} size={size} />
      )}

      {/* ── Reflective ground shadow ─────────────────────────────────────── */}
      <motion.div
        className="absolute pointer-events-none rounded-full"
        style={{
          bottom: showBody ? size * 0.02 : size * -0.06,
          width: size * 0.6,
          height: size * 0.06,
          background: `radial-gradient(ellipse, ${theme.glow}, transparent 70%)`,
          filter: `blur(${size * 0.02}px)`,
        }}
        animate={{ scaleX: [1, 0.88, 1], opacity: [0.5, 0.3, 0.5] }}
        transition={{ duration: sway.d, repeat: Infinity, ease: 'easeInOut' }}
      />
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// Sub-components
// ═══════════════════════════════════════════════════════════════════════════════

function GenieEye({ side, size, eyeW, eyeH, shape, blinking, gazeX, gazeY, color, expression }) {
  const isSleeping = expression === 'sleeping';
  const eyelidHeight = isSleeping ? 1 : (blinking ? 1 : (EYE_SHAPE[expression]?.squint ?? 0));

  // Eyebrow config
  const browsY     = expression === 'surprised' ? -eyeH * 0.9 : expression === 'concerned' ? -eyeH * 0.55 : -eyeH * 0.7;
  const browsRot   = side === 'left'
    ? (expression === 'concerned' ? 10 : expression === 'confused' ? -12 : 0)
    : (expression === 'concerned' ? -10 : expression === 'confused' ? 12 : 0);
  const browsOpac  = isSleeping ? 0 : 1;

  const scaleX = shape.rx;
  const scaleY = shape.ry;

  return (
    <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {/* Eyebrow */}
      <motion.div
        style={{
          position: 'absolute',
          top: browsY,
          width: eyeW * 0.9,
          height: Math.max(2, eyeW * 0.1),
          background: color,
          borderRadius: 99,
          opacity: browsOpac,
          transformOrigin: side === 'left' ? 'left center' : 'right center',
        }}
        animate={{ y: browsY, rotate: browsRot, opacity: browsOpac }}
        transition={{ type: 'spring', stiffness: 150, damping: 18 }}
      />

      {/* Eye body — outer div handles shape/scale animation */}
      <motion.div
        animate={{
          scaleX,
          scaleY,
          y: shape.yOffset,
        }}
        transition={{ type: 'spring', stiffness: 200, damping: 22 }}
        style={{ transformOrigin: 'center bottom' }}
      >
        {/* Inner div carries gaze MotionValues (x/y must be in style, not animate) */}
        <motion.div
          style={{
            width: eyeW,
            height: eyeH,
            borderRadius: '45% 45% 55% 55%',
            background: `radial-gradient(circle at 38% 30%, #ffffff 0 14%, #172554 16%, ${color}22 45%, #030812 75%)`,
            boxShadow: `0 0 ${eyeW * 0.4}px ${color}80`,
            position: 'relative',
            overflow: 'hidden',
            x: gazeX,
            y: gazeY,
          }}
        >
          {/* Inner eye highlight */}
          <div
            style={{
              position: 'absolute',
              top: '18%',
              left: '22%',
              width: '28%',
              height: '28%',
              borderRadius: '50%',
              background: 'rgba(255,255,255,0.85)',
            }}
          />

          {/* Eyelid (closes on blink) */}
          <motion.div
            style={{
              position: 'absolute',
              inset: -1,
              background: '#03070f',
              transformOrigin: 'top center',
              borderRadius: '0 0 50% 50%',
            }}
            animate={{ scaleY: eyelidHeight }}
            transition={{ duration: 0.09 }}
          />

          {/* Pupil glow dot */}
          <motion.div
            style={{
              position: 'absolute',
              width: eyeW * 0.32,
              height: eyeW * 0.32,
              borderRadius: '50%',
              background: color,
              filter: `blur(${eyeW * 0.06}px)`,
              top: '55%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              opacity: 0.6,
            }}
            animate={{ opacity: [0.4, 0.8, 0.4] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
          />
        </motion.div>
      </motion.div>
    </div>
  );
}



function GenieMouthNew({ expression, isSpeaking, mouthOpen, size, color }) {
  const mouthW = size * 0.26;
  const mouthH = size * 0.12;

  const mouthPath = MOUTH_PATH[expression] ?? MOUTH_PATH.idle;

  if (isSpeaking) {
    // Live lip-sync — animated mouth opening
    const openHeight = Math.max(size * 0.018, mouthOpen * size * 0.095);
    return (
      <motion.div
        style={{
          width: mouthW * 0.55,
          borderRadius: mouthH,
          background: 'rgba(0,0,0,0.7)',
          border: `2px solid ${color}88`,
          boxShadow: `0 0 8px ${color}60`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          position: 'relative',
        }}
        animate={{ height: openHeight }}
        transition={{ duration: 0.06 }}
      >
        {/* Teeth glint when speaking */}
        <div
          style={{
            position: 'absolute',
            top: 2,
            left: '10%',
            right: '10%',
            height: '35%',
            background: 'rgba(255,255,255,0.15)',
            borderRadius: '0 0 4px 4px',
          }}
        />
        {/* Tongue */}
        <motion.div
          style={{
            position: 'absolute',
            bottom: 2,
            width: '40%',
            height: '40%',
            borderRadius: '50% 50% 50% 50%',
            background: 'rgba(248,113,113,0.5)',
          }}
          animate={{ scaleY: [1, 0.8, 1] }}
          transition={{ duration: 0.3, repeat: Infinity }}
        />
      </motion.div>
    );
  }

  // Static expression mouth
  return (
    <svg
      width={mouthW}
      height={mouthH}
      viewBox="0 0 50 25"
      overflow="visible"
      style={{ overflow: 'visible' }}
    >
      {/* Mouth shadow */}
      <motion.path
        d={mouthPath}
        fill="none"
        stroke="rgba(0,0,0,0.4)"
        strokeWidth="5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Mouth shape */}
      <motion.path
        d={mouthPath}
        fill="none"
        stroke={color}
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        filter={`drop-shadow(0 0 4px ${color}80)`}
        initial={false}
        animate={{ d: mouthPath }}
        transition={{ type: 'spring', stiffness: 220, damping: 26 }}
      />
    </svg>
  );
}


function BodySection({ size, theme, expression, sway }) {
  const bodyW = size * 0.6;
  const bodyH = size * 0.35;

  return (
    <motion.div
      style={{
        position: 'relative',
        marginTop: size * -0.04,
        zIndex: 1,
      }}
      animate={{ x: sway.x.map(v => v * 0.5), y: sway.y.map(v => v * 0.3 + size * 0.05) }}
      transition={{ duration: sway.d, repeat: Infinity, ease: 'easeInOut' }}
    >
      <svg width={bodyW} height={bodyH} viewBox="0 0 100 60" overflow="visible">
        <defs>
          <linearGradient id="bodyGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={theme.bodyGrad[0]} />
            <stop offset="55%" stopColor={theme.bodyGrad[1]} />
            <stop offset="100%" stopColor={theme.bodyGrad[2]} />
          </linearGradient>
          <filter id="bodyBlur">
            <feDropShadow dx="0" dy="8" stdDeviation="8" floodColor={theme.primary} floodOpacity="0.22" />
          </filter>
        </defs>

        {/* Left arm */}
        <motion.ellipse
          cx="14" cy="32" rx="10" ry="20"
          fill="url(#bodyGrad)"
          filter="url(#bodyBlur)"
          animate={{
            rotate: expression === 'happy' || expression === 'excited' ? [-10, 14, -10] : [0, 5, 0],
          }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
          style={{ transformOrigin: '14px 18px' }}
        />

        {/* Right arm */}
        <motion.ellipse
          cx="86" cy="32" rx="10" ry="20"
          fill="url(#bodyGrad)"
          filter="url(#bodyBlur)"
          animate={{
            rotate: expression === 'happy' || expression === 'excited' ? [10, -14, 10] : [0, -5, 0],
          }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
          style={{ transformOrigin: '86px 18px' }}
        />

        {/* Torso */}
        <rect x="24" y="4" width="52" height="48" rx="26" fill="url(#bodyGrad)" filter="url(#bodyBlur)" />

        {/* Chest highlight */}
        <ellipse cx="42" cy="20" rx="14" ry="8" fill="rgba(255,255,255,0.55)" />

        {/* Chest badge / LED */}
        <motion.circle
          cx="50" cy="38" r="5"
          fill={theme.primary}
          opacity="0.85"
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 1.8, repeat: Infinity }}
        />
        <circle cx="50" cy="38" r="3" fill="rgba(255,255,255,0.3)" />
      </svg>
    </motion.div>
  );
}


function StateLabel({ expression, theme, size }) {
  const LABELS = {
    idle:      null,
    sleeping:  'Sleeping',
    waking:    'Waking up…',
    listening: 'Listening…',
    thinking:  'Thinking…',
    speaking:  null,
    happy:     null,
    excited:   'Excited!',
    confused:  'Confused…',
    surprised: 'Oh!',
    concerned: 'Concerned',
  };

  const label = LABELS[expression];
  if (!label) return null;

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={expression}
        initial={{ opacity: 0, y: 8, scale: 0.9 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -4, scale: 0.95 }}
        transition={{ duration: 0.2 }}
        style={{
          marginTop: size * 0.06,
          padding: '4px 12px',
          borderRadius: 99,
          background: `${theme.primary}22`,
          border: `1px solid ${theme.primary}55`,
          color: theme.primary,
          fontSize: size * 0.045,
          fontFamily: "'Inter', sans-serif",
          fontWeight: 600,
          letterSpacing: '0.04em',
        }}
      >
        {label}
      </motion.div>
    </AnimatePresence>
  );
}
