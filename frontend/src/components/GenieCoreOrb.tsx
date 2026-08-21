import React, { useRef, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../store/appStore';

interface GenieCoreOrbProps {
  state: string; // idle, listening, waking, thinking, planning, executing, speaking, error, sleeping
  size?: number; // default 240
}

interface StateColorProfile {
  primary: string;
  secondary: string;
  accent: string;
  glow: string;
  ring1: string;
  ring2: string;
  speed: number;
  particleSpeed: number;
  bloom: string;
  label: string;
}

const COLOR_PROFILES: Record<string, StateColorProfile> = {
  listening: {
    primary: '#00f2fe',
    secondary: '#4facfe',
    accent: '#00c6ff',
    glow: 'rgba(0, 242, 254, 0.65)',
    ring1: 'rgba(79, 172, 254, 0.7)',
    ring2: 'rgba(0, 198, 255, 0.4)',
    speed: 2.2,
    particleSpeed: 1.8,
    bloom: '0 0 70px rgba(0, 242, 254, 0.5), inset 0 0 40px rgba(255, 255, 255, 0.6)',
    label: 'Listening',
  },
  follow_up_listening: {
    primary: '#00f2fe',
    secondary: '#4facfe',
    accent: '#38ef7d',
    glow: 'rgba(0, 242, 254, 0.55)',
    ring1: 'rgba(56, 239, 125, 0.6)',
    ring2: 'rgba(0, 242, 254, 0.4)',
    speed: 2.0,
    particleSpeed: 1.5,
    bloom: '0 0 65px rgba(0, 242, 254, 0.45)',
    label: 'Listening',
  },
  waking: {
    primary: '#c471ed',
    secondary: '#f64f59',
    accent: '#12c2e9',
    glow: 'rgba(196, 113, 237, 0.75)',
    ring1: 'rgba(246, 79, 89, 0.8)',
    ring2: 'rgba(18, 194, 233, 0.6)',
    speed: 3.5,
    particleSpeed: 3.0,
    bloom: '0 0 85px rgba(196, 113, 237, 0.65)',
    label: 'Waking',
  },
  transcribing: {
    primary: '#8a2387',
    secondary: '#e94057',
    accent: '#f27121',
    glow: 'rgba(233, 64, 87, 0.65)',
    ring1: 'rgba(242, 113, 33, 0.7)',
    ring2: 'rgba(138, 35, 135, 0.5)',
    speed: 2.6,
    particleSpeed: 2.2,
    bloom: '0 0 70px rgba(233, 64, 87, 0.5)',
    label: 'Transcribing',
  },
  thinking: {
    primary: '#7f00ff',
    secondary: '#e100ff',
    accent: '#00d2ff',
    glow: 'rgba(127, 0, 255, 0.65)',
    ring1: 'rgba(225, 0, 255, 0.6)',
    ring2: 'rgba(0, 210, 255, 0.5)',
    speed: 2.8,
    particleSpeed: 2.5,
    bloom: '0 0 80px rgba(127, 0, 255, 0.55), inset 0 0 45px rgba(225, 0, 255, 0.4)',
    label: 'Thinking',
  },
  searching: {
    primary: '#00c6ff',
    secondary: '#0072ff',
    accent: '#38ef7d',
    glow: 'rgba(0, 198, 255, 0.7)',
    ring1: 'rgba(0, 114, 255, 0.75)',
    ring2: 'rgba(56, 239, 125, 0.6)',
    speed: 3.0,
    particleSpeed: 2.6,
    bloom: '0 0 85px rgba(0, 198, 255, 0.6), inset 0 0 45px rgba(56, 239, 125, 0.5)',
    label: 'Searching',
  },
  planning: {
    primary: '#6a11cb',
    secondary: '#2575fc',
    accent: '#00f2fe',
    glow: 'rgba(37, 117, 252, 0.65)',
    ring1: 'rgba(106, 17, 203, 0.7)',
    ring2: 'rgba(0, 242, 254, 0.5)',
    speed: 2.5,
    particleSpeed: 2.0,
    bloom: '0 0 75px rgba(37, 117, 252, 0.5)',
    label: 'Planning',
  },
  executing: {
    primary: '#11998e',
    secondary: '#38ef7d',
    accent: '#00f2fe',
    glow: 'rgba(56, 239, 125, 0.65)',
    ring1: 'rgba(17, 153, 142, 0.7)',
    ring2: 'rgba(0, 242, 254, 0.5)',
    speed: 2.6,
    particleSpeed: 2.2,
    bloom: '0 0 75px rgba(56, 239, 125, 0.5)',
    label: 'Executing',
  },
  speaking: {
    primary: '#00c6ff',
    secondary: '#0072ff',
    accent: '#f857a6',
    glow: 'rgba(0, 198, 255, 0.7)',
    ring1: 'rgba(248, 87, 166, 0.7)',
    ring2: 'rgba(0, 114, 255, 0.6)',
    speed: 2.2,
    particleSpeed: 2.0,
    bloom: '0 0 80px rgba(0, 198, 255, 0.6), inset 0 0 50px rgba(255, 255, 255, 0.7)',
    label: 'Speaking',
  },
  error: {
    primary: '#ff416c',
    secondary: '#ff4b2b',
    accent: '#f9d423',
    glow: 'rgba(255, 75, 43, 0.65)',
    ring1: 'rgba(255, 65, 108, 0.7)',
    ring2: 'rgba(249, 212, 35, 0.4)',
    speed: 1.6,
    particleSpeed: 1.0,
    bloom: '0 0 70px rgba(255, 75, 43, 0.5)',
    label: 'Attention',
  },
  sleeping: {
    primary: '#2c3e50',
    secondary: '#4ca1af',
    accent: '#6c5ce7',
    glow: 'rgba(76, 161, 175, 0.25)',
    ring1: 'rgba(108, 92, 231, 0.25)',
    ring2: 'rgba(76, 161, 175, 0.2)',
    speed: 0.6,
    particleSpeed: 0.5,
    bloom: '0 0 40px rgba(76, 161, 175, 0.2)',
    label: 'Resting',
  },
  idle: {
    primary: '#667eea',
    secondary: '#764ba2',
    accent: '#00f2fe',
    glow: 'rgba(118, 75, 162, 0.55)',
    ring1: 'rgba(102, 126, 234, 0.5)',
    ring2: 'rgba(0, 242, 254, 0.35)',
    speed: 1.2,
    particleSpeed: 1.0,
    bloom: '0 0 65px rgba(118, 75, 162, 0.45), inset 0 0 35px rgba(255, 255, 255, 0.4)',
    label: 'Genie OS',
  },
};

export function GenieCoreOrb({ state = 'idle', size = 240 }: GenieCoreOrbProps) {
  const amplitude = useAppStore((s) => s.amplitude);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const profile = useMemo(() => {
    const norm = (state || 'idle').toLowerCase();
    return COLOR_PROFILES[norm] || COLOR_PROFILES.idle;
  }, [state]);

  // High-performance Particle Plasma Core
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let time = 0;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const centerX = size / 2;
    const centerY = size / 2;
    const radius = size * 0.38;

    // Generate orbiting particles
    const particleCount = 42;
    const particles = Array.from({ length: particleCount }).map((_, i) => ({
      angle: (i / particleCount) * Math.PI * 2,
      radiusOffset: (Math.random() - 0.5) * 26,
      speed: (0.008 + Math.random() * 0.012) * (Math.random() > 0.5 ? 1 : -1),
      size: 1.2 + Math.random() * 2.4,
      alpha: 0.3 + Math.random() * 0.7,
      color: i % 3 === 0 ? profile.accent : i % 2 === 0 ? profile.primary : profile.secondary,
    }));

    const render = () => {
      time += 0.015 * profile.speed;
      ctx.clearRect(0, 0, size, size);

      // 1. Dynamic Energy Plasma Fill
      const grad = ctx.createRadialGradient(
        centerX + Math.cos(time * 1.5) * 16,
        centerY + Math.sin(time * 1.5) * 16,
        radius * 0.1,
        centerX,
        centerY,
        radius * 1.05
      );

      grad.addColorStop(0, '#ffffff');
      grad.addColorStop(0.25, profile.primary);
      grad.addColorStop(0.65, profile.secondary);
      grad.addColorStop(0.95, profile.accent);
      grad.addColorStop(1, 'rgba(10, 10, 20, 0.9)');

      // Draw Main Liquid Orb
      ctx.save();
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius + amplitude * 12, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.shadowColor = profile.glow;
      ctx.shadowBlur = 35 + amplitude * 25;
      ctx.fill();
      ctx.restore();

      // 2. Swirling Internal Plasma Waves
      ctx.save();
      ctx.globalCompositeOperation = 'overlay';
      for (let i = 0; i < 3; i++) {
        ctx.beginPath();
        const waveAngle = time * (1 + i * 0.4);
        const waveX = centerX + Math.cos(waveAngle) * (radius * 0.4);
        const waveY = centerY + Math.sin(waveAngle) * (radius * 0.4);
        const waveGrad = ctx.createRadialGradient(waveX, waveY, 5, waveX, waveY, radius * 0.6);
        waveGrad.addColorStop(0, 'rgba(255, 255, 255, 0.7)');
        waveGrad.addColorStop(1, 'transparent');
        ctx.fillStyle = waveGrad;
        ctx.arc(waveX, waveY, radius * 0.6, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();

      // 3. Orbiting Celestial Particles
      ctx.save();
      particles.forEach((p) => {
        p.angle += p.speed * profile.particleSpeed;
        const currentRadius = radius + p.radiusOffset + Math.sin(time * 2 + p.angle) * 8;
        const px = centerX + Math.cos(p.angle) * currentRadius;
        const py = centerY + Math.sin(p.angle) * currentRadius;

        ctx.beginPath();
        ctx.arc(px, py, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.alpha;
        ctx.shadowColor = p.color;
        ctx.shadowBlur = 10;
        ctx.fill();
      });
      ctx.restore();

      // 4. Glass Specular Highlights
      ctx.save();
      ctx.beginPath();
      ctx.ellipse(
        centerX - radius * 0.35,
        centerY - radius * 0.35,
        radius * 0.45,
        radius * 0.22,
        -Math.PI / 4,
        0,
        Math.PI * 2
      );
      const specGrad = ctx.createLinearGradient(
        centerX - radius * 0.6,
        centerY - radius * 0.6,
        centerX,
        centerY
      );
      specGrad.addColorStop(0, 'rgba(255, 255, 255, 0.85)');
      specGrad.addColorStop(1, 'rgba(255, 255, 255, 0)');
      ctx.fillStyle = specGrad;
      ctx.fill();
      ctx.restore();

      animId = requestAnimationFrame(render);
    };

    render();

    return () => cancelAnimationFrame(animId);
  }, [size, profile, amplitude]);

  return (
    <div
      className="relative flex items-center justify-center select-none"
      style={{ width: size, height: size }}
    >
      {/* Outer Ambient Volumetric Atmosphere */}
      <motion.div
        animate={{
          scale: [1, 1.1 + amplitude * 0.2, 1],
          opacity: [0.65, 0.95, 0.65],
        }}
        transition={{
          duration: 3.5 / profile.speed,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        className="absolute inset-0 rounded-full pointer-events-none blur-3xl"
        style={{
          background: `radial-gradient(circle, ${profile.glow} 0%, rgba(0,0,0,0) 70%)`,
        }}
      />

      {/* Futuristic Concentric Gyro Ring 1 */}
      <motion.div
        animate={{ rotate: 360 }}
        transition={{
          duration: 20 / profile.speed,
          repeat: Infinity,
          ease: 'linear',
        }}
        className="absolute inset-[-12%] rounded-full border border-dashed pointer-events-none"
        style={{
          borderColor: profile.ring1,
          borderWidth: '1.5px',
          boxShadow: `0 0 18px ${profile.ring1}`,
        }}
      >
        <span
          className="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full shadow-lg"
          style={{ backgroundColor: profile.primary, boxShadow: `0 0 10px ${profile.primary}` }}
        />
      </motion.div>

      {/* Counter-Rotating Concentric Gyro Ring 2 */}
      <motion.div
        animate={{ rotate: -360 }}
        transition={{
          duration: 28 / profile.speed,
          repeat: Infinity,
          ease: 'linear',
        }}
        className="absolute inset-[-20%] rounded-full border pointer-events-none"
        style={{
          borderColor: profile.ring2,
          borderWidth: '1px',
          borderStyle: 'dotted',
        }}
      >
        <span
          className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full shadow-lg"
          style={{ backgroundColor: profile.secondary, boxShadow: `0 0 10px ${profile.secondary}` }}
        />
      </motion.div>

      {/* Living Canvas Plasma Energy Sphere */}
      <div
        className="relative rounded-full overflow-hidden flex items-center justify-center shadow-2xl transition-all"
        style={{
          width: size,
          height: size,
          boxShadow: profile.bloom,
        }}
      >
        <canvas
          ref={canvasRef}
          style={{
            width: size,
            height: size,
            display: 'block',
          }}
        />
      </div>

      <span className="sr-only">{profile.label}</span>
    </div>
  );
}
