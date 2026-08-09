/**
 * GenieAvatarStage.jsx — Primary 3D Stage for Genie AI VRM Avatar
 * Fixed: Model properly visible with correct camera, scale, and position.
 */

import React, { useRef, useState, Suspense } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { VRMAvatar } from './VRMAvatar';
import { AvatarParticles } from './AvatarParticles';
import { useAppStore } from '../../store/appStore';

// SVG Icon Helpers
function MaximizeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
    </svg>
  );
}

function MinimizeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" />
    </svg>
  );
}

function ExternalLinkIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

// ── State mapper function ──────────────────────────────────────────────────
function mapGenieStateToAvatarState(genieState) {
  switch (genieState) {
    case 'sleeping': return 'sleep';
    case 'waking': return 'waking';
    case 'idle': return 'idle';
    case 'listening':
    case 'follow_up_listening': return 'listening';
    case 'transcribing':
    case 'thinking': return 'thinking';
    case 'executing': return 'working';
    case 'speaking': return 'speaking';
    case 'success': return 'success';
    case 'interrupted':
    case 'error': return 'error';
    default: return 'idle';
  }
}

// ── Static Camera (no dynamic updates causing flicker) ─────────────────────
function StaticCamera() {
  const { camera } = useThree();
  React.useEffect(() => {
    // Camera sits in front, looking at avatar chest/face height
    camera.position.set(0, 1.2, 2.5);
    camera.lookAt(0, 0.9, 0);
    camera.fov = 45;
    camera.near = 0.1;
    camera.far = 100;
    camera.updateProjectionMatrix();
  }, [camera]);
  return null;
}

// ── 3-Point Lighting Setup ────────────────────────────────────────────────
function StageLighting({ avatarState }) {
  let rimColor = '#38bdf8';
  if (avatarState === 'speaking') rimColor = '#34d399';
  else if (avatarState === 'listening') rimColor = '#22d3ee';
  else if (avatarState === 'thinking') rimColor = '#c084fc';
  else if (avatarState === 'working') rimColor = '#fbbf24';
  else if (avatarState === 'success') rimColor = '#f43f5e';

  return (
    <>
      {/* Strong ambient so MToon materials are fully lit */}
      <ambientLight intensity={3.0} color="#ffffff" />

      {/* Strong main front light */}
      <directionalLight position={[1, 3, 3]} intensity={3.0} color="#ffffff" castShadow />

      {/* Left fill */}
      <directionalLight position={[-2, 2, 2]} intensity={1.8} color="#c7d2fe" />

      {/* Right rim light */}
      <directionalLight position={[2, 2, -1]} intensity={1.2} color="#e0f2fe" />

      {/* Coloured back rim */}
      <pointLight position={[0, 2, -2]} intensity={4.0} color={rimColor} distance={6} />

      {/* Ground bounce */}
      <directionalLight position={[0, -1, 1]} intensity={0.8} color="#ffffff" />
    </>
  );
}

// ── Holographic Stage Platform ──────────────────────────────────────────────
function HolographicPlatform({ avatarState }) {
  const ringRef = useRef();

  let activeColor = '#38bdf8';
  if (avatarState === 'speaking') activeColor = '#34d399';
  if (avatarState === 'listening') activeColor = '#22d3ee';
  if (avatarState === 'thinking') activeColor = '#c084fc';
  if (avatarState === 'success') activeColor = '#fbbf24';

  useFrame((_, delta) => {
    if (ringRef.current) {
      ringRef.current.rotation.z += delta * 0.4;
    }
  });

  // Platform sits at y=0 (feet of avatar)
  return (
    <group position={[0, 0, 0]}>
      {/* Shadow plane */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[10, 10]} />
        <shadowMaterial opacity={0.35} />
      </mesh>

      {/* Dark disc */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
        <circleGeometry args={[1.25, 48]} />
        <meshStandardMaterial color="#090d16" roughness={0.4} metalness={0.8} />
      </mesh>

      {/* Outer glowing ring */}
      <mesh ref={ringRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.001, 0]}>
        <ringGeometry args={[1.18, 1.25, 64]} />
        <meshBasicMaterial color={activeColor} transparent opacity={0.8} side={THREE.DoubleSide} />
      </mesh>

      {/* Inner ring */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.001, 0]}>
        <ringGeometry args={[0.7, 0.73, 48]} />
        <meshBasicMaterial color={activeColor} transparent opacity={0.4} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

// ── Loading Spinner (Fallback while VRM loads) ─────────────────────────────
function AvatarLoader() {
  const meshRef = useRef();
  useFrame((_, delta) => {
    if (meshRef.current) meshRef.current.rotation.y += delta * 2;
  });
  return (
    <group position={[0, 0.9, 0]}>
      <mesh ref={meshRef}>
        <torusGeometry args={[0.3, 0.04, 16, 48]} />
        <meshBasicMaterial color="#38bdf8" />
      </mesh>
      <mesh position={[0, -0.5, 0]}>
        <sphereGeometry args={[0.18, 16, 16]} />
        <meshBasicMaterial color="#6366f1" wireframe />
      </mesh>
    </group>
  );
}

// ── Main Stage Component ───────────────────────────────────────────────────
export default function GenieAvatarStage({
  genieState = 'idle',
  gestureIntensity = 0.6,
  modelUrl,   // Resolved dynamically inside VRMAvatar using window.location
}) {
  const avatarState = mapGenieStateToAvatarState(genieState);
  const robotEmotion = useAppStore((s) => s.robotEmotion);
  const containerRef = useRef(null);

  const [lookAtPos, setLookAtPos] = useState([0, 1.2, 2.5]);
  const [displayMode, setDisplayMode] = useState('standard');
  const [interactionEmotion, setInteractionEmotion] = useState(null);
  const longPressTimer = useRef(null);

  const handlePointerMove = (e) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    setLookAtPos([x * 1.2, 1.0 + y * 0.5, 2.5]);
  };

  const handleClick = () => {
    setInteractionEmotion('happy');
    setTimeout(() => setInteractionEmotion(null), 2500);
  };

  const handleDoubleClick = () => {
    setInteractionEmotion('excited');
    setTimeout(() => setInteractionEmotion(null), 3000);
  };

  const handlePointerDown = () => {
    longPressTimer.current = setTimeout(() => {
      setInteractionEmotion('laugh');
      setTimeout(() => setInteractionEmotion(null), 3500);
    }, 600);
  };

  const handlePointerUp = () => {
    if (longPressTimer.current) clearTimeout(longPressTimer.current);
  };

  const currentEmotion = interactionEmotion || robotEmotion?.emotion || 'neutral';

  const containerStyle = displayMode === 'floating'
    ? { position: 'fixed', bottom: '5rem', right: '1.5rem', zIndex: 40, width: '18rem', height: '24rem', borderRadius: '1.5rem', border: '1px solid rgba(34,211,238,0.3)', overflow: 'hidden', boxShadow: '0 25px 50px rgba(0,0,0,0.8)', background: 'rgba(9,13,22,0.95)' }
    : displayMode === 'fullscreen'
      ? { position: 'fixed', inset: 0, zIndex: 50, background: '#020617' }
      : { position: 'relative', width: '100%', height: '100%' };

  return (
    <div
      ref={containerRef}
      onPointerMove={handlePointerMove}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      style={containerStyle}
    >
      {/* Top Controls Badge */}
      <div style={{
        position: 'absolute', top: 12, right: 12, zIndex: 20,
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '6px 12px', borderRadius: 999,
        background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(255,255,255,0.1)',
        backdropFilter: 'blur(12px)',
      }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#22d3ee', animation: 'pulse 2s infinite', display: 'inline-block' }} />
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 2, color: '#22d3ee', textTransform: 'uppercase' }}>Genie VRM</span>

        <button
          onClick={(e) => { e.stopPropagation(); setDisplayMode(displayMode === 'fullscreen' ? 'standard' : 'fullscreen'); }}
          title={displayMode === 'fullscreen' ? 'Exit Fullscreen' : 'Fullscreen'}
          style={{ padding: 5, borderRadius: 8, border: 'none', background: 'transparent', color: '#94a3b8', cursor: 'pointer' }}
        >
          {displayMode === 'fullscreen' ? <MinimizeIcon /> : <MaximizeIcon />}
        </button>

        <button
          onClick={(e) => { e.stopPropagation(); setDisplayMode(displayMode === 'floating' ? 'standard' : 'floating'); }}
          title={displayMode === 'floating' ? 'Standard Stage' : 'Floating Mini'}
          style={{ padding: 5, borderRadius: 8, border: 'none', background: 'transparent', color: '#94a3b8', cursor: 'pointer' }}
        >
          <ExternalLinkIcon />
        </button>
      </div>

      {/* Radial background glow */}
      <div style={{
        position: 'absolute', inset: 0, zIndex: 0,
        background: 'radial-gradient(ellipse 70% 60% at 50% 60%, rgba(99,102,241,0.12) 0%, rgba(7,11,20,0.98) 100%)',
        pointerEvents: 'none',
      }} />

      {/* 3D Canvas */}
      <Canvas
        shadows
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        camera={{ position: [0, 1.2, 2.5], fov: 45, near: 0.1, far: 100 }}
        style={{ width: '100%', height: '100%', position: 'relative', zIndex: 1 }}
      >
        <StaticCamera />
        <StageLighting avatarState={avatarState} />

        <Suspense fallback={<AvatarLoader />}>
          {/* VRM Avatar — positioned at origin, feet at y=0 */}
          <VRMAvatar
            modelUrl={modelUrl}
            state={avatarState}
            emotion={currentEmotion}
            lookAt={lookAtPos}
            gestureIntensity={gestureIntensity}
            scale={1.0}
            position={[0, 0, 0]}
          />

          {/* Holographic platform under avatar feet */}
          <HolographicPlatform avatarState={avatarState} />

          {/* Floating particles */}
          <AvatarParticles state={avatarState} />
        </Suspense>
      </Canvas>
    </div>
  );
}
