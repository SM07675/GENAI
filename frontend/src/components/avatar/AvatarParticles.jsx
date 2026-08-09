/**
 * AvatarParticles.jsx
 * Dynamic Three.js Particle System for Genie AI VRM Avatar.
 * Provides visual magic for thinking, speaking, celebration, welcome, and loading states.
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

// Helper to generate random vectors in a sphere/cylinder
function generateParticleData(count, spreadRadius = 1.2, heightRange = [0, 2.2]) {
  const positions = new Float32Array(count * 3);
  const velocities = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const r = Math.sqrt(Math.random()) * spreadRadius;
    const y = heightRange[0] + Math.random() * (heightRange[1] - heightRange[0]);

    positions[i * 3] = Math.cos(angle) * r;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = Math.sin(angle) * r;

    velocities[i * 3] = (Math.random() - 0.5) * 0.2;
    velocities[i * 3 + 1] = 0.2 + Math.random() * 0.4; // upward drift
    velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.2;

    sizes[i] = 0.02 + Math.random() * 0.04;
  }

  return { positions, velocities, colors, sizes };
}

export function AvatarParticles({ state = 'idle', triggerEffect = null }) {
  const thinkingParticlesRef = useRef();
  const celebrationRef = useRef();
  const speakingPulseRef = useRef();
  const loadingRingRef = useRef();

  // Thinking Blue Glow Particles (60 particles)
  const thinkingData = useMemo(() => generateParticleData(60, 0.8, [0.5, 2.0]), []);
  
  // Celebration Confetti/Sparkles (120 particles)
  const celebrationData = useMemo(() => {
    const data = generateParticleData(120, 1.5, [0.2, 2.5]);
    const palette = [
      new THREE.Color('#38bdf8'),
      new THREE.Color('#a855f7'),
      new THREE.Color('#34d399'),
      new THREE.Color('#fbbf24'),
      new THREE.Color('#f43f5e'),
    ];
    for (let i = 0; i < 120; i++) {
      const col = palette[Math.floor(Math.random() * palette.length)];
      data.colors[i * 3] = col.r;
      data.colors[i * 3 + 1] = col.g;
      data.colors[i * 3 + 2] = col.b;
    }
    return data;
  }, []);

  useFrame((_, delta) => {
    // 1. Thinking particle upward swirl animation
    if (thinkingParticlesRef.current && (state === 'thinking' || state === 'transcribing')) {
      const pos = thinkingParticlesRef.current.geometry.attributes.position.array;
      for (let i = 0; i < 60; i++) {
        pos[i * 3 + 1] += delta * 0.5; // Move up
        pos[i * 3] += Math.sin(pos[i * 3 + 1] * 4) * 0.003; // Swirl
        if (pos[i * 3 + 1] > 2.2) {
          pos[i * 3 + 1] = 0.5; // Reset to lower body
        }
      }
      thinkingParticlesRef.current.geometry.attributes.position.needsUpdate = true;
    }

    // 2. Celebration Sparkle Dispersion
    if (celebrationRef.current && (state === 'success' || triggerEffect === 'celebrate')) {
      const pos = celebrationRef.current.geometry.attributes.position.array;
      for (let i = 0; i < 120; i++) {
        pos[i * 3] += celebrationData.velocities[i * 3] * delta;
        pos[i * 3 + 1] += celebrationData.velocities[i * 3 + 1] * delta;
        pos[i * 3 + 2] += celebrationData.velocities[i * 3 + 2] * delta;

        // Gravity effect
        celebrationData.velocities[i * 3 + 1] -= delta * 0.3;

        if (pos[i * 3 + 1] < 0) {
          pos[i * 3 + 1] = 1.2;
          pos[i * 3] = (Math.random() - 0.5) * 0.6;
          pos[i * 3 + 2] = (Math.random() - 0.5) * 0.6;
          celebrationData.velocities[i * 3 + 1] = 0.4 + Math.random() * 0.5;
        }
      }
      celebrationRef.current.geometry.attributes.position.needsUpdate = true;
    }

    // 3. Speaking sound wave aura pulse
    if (speakingPulseRef.current) {
      if (state === 'speaking') {
        const s = 1.0 + Math.sin(Date.now() * 0.008) * 0.15;
        speakingPulseRef.current.scale.set(s, s, s);
        speakingPulseRef.current.material.opacity = 0.35 + Math.sin(Date.now() * 0.008) * 0.15;
      } else {
        speakingPulseRef.current.material.opacity = 0;
      }
    }

    // 4. Loading hologram ring rotation
    if (loadingRingRef.current) {
      if (state === 'waking' || state === 'executing' || triggerEffect === 'loading') {
        loadingRingRef.current.rotation.y += delta * 1.5;
        loadingRingRef.current.rotation.z += delta * 0.8;
      }
    }
  });

  return (
    <group position={[0, 0, 0]}>
      {/* Thinking Particles (Cyan / Purple floating dots) */}
      {(state === 'thinking' || state === 'transcribing') && (
        <points ref={thinkingParticlesRef}>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              count={60}
              array={thinkingData.positions}
              itemSize={3}
            />
          </bufferGeometry>
          <pointsMaterial
            size={0.05}
            color="#38bdf8"
            transparent
            opacity={0.8}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </points>
      )}

      {/* Celebration Sparkles / Confetti */}
      {(state === 'success' || triggerEffect === 'celebrate') && (
        <points ref={celebrationRef}>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              count={120}
              array={celebrationData.positions}
              itemSize={3}
            />
            <bufferAttribute
              attach="attributes-color"
              count={120}
              array={celebrationData.colors}
              itemSize={3}
            />
          </bufferGeometry>
          <pointsMaterial
            size={0.06}
            vertexColors
            transparent
            opacity={0.9}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </points>
      )}

      {/* Speaking Sound Ring Aura around avatar chest height */}
      <mesh ref={speakingPulseRef} position={[0, 0.95, 0]}>
        <ringGeometry args={[0.55, 0.62, 32]} />
        <meshBasicMaterial
          color="#34d399"
          transparent
          opacity={0}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Loading Hologram Floating Ring */}
      {(state === 'waking' || state === 'executing' || triggerEffect === 'loading') && (
        <mesh ref={loadingRingRef} position={[0, 1.0, 0]}>
          <torusGeometry args={[0.75, 0.015, 16, 64]} />
          <meshBasicMaterial
            color="#6366f1"
            transparent
            opacity={0.7}
            wireframe
          />
        </mesh>
      )}
    </group>
  );
}
