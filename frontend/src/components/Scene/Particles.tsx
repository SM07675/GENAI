import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { AssistantState } from '../../types';

interface ParticlesProps {
  count?: number;
  assistantState: AssistantState;
}

export function Particles({ count = 1200, assistantState }: ParticlesProps) {
  const pointsRef = useRef<THREE.Points>(null);

  const [positions, colors, scales] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);
    const sca = new Float32Array(count);

    const colorA = new THREE.Color('#00f0ff'); // Cyan glow
    const colorB = new THREE.Color('#3b82f6'); // Electric blue
    const colorC = new THREE.Color('#8b5cf6'); // Deep purple highlight

    for (let i = 0; i < count; i++) {
      // Sphere / Cylinder dispersion around character center
      const radius = 3 + Math.random() * 7;
      const theta = Math.random() * Math.PI * 2;
      const phi = (Math.random() - 0.5) * Math.PI * 0.8;

      pos[i * 3] = radius * Math.cos(theta) * Math.cos(phi);
      pos[i * 3 + 1] = radius * Math.sin(phi) + 1.0;
      pos[i * 3 + 2] = radius * Math.sin(theta) * Math.cos(phi) - 2;

      // Color gradient distribution
      const mixRatio = Math.random();
      const chosenColor = mixRatio < 0.5 ? colorA.clone().lerp(colorB, mixRatio * 2) : colorB.clone().lerp(colorC, (mixRatio - 0.5) * 2);

      col[i * 3] = chosenColor.r;
      col[i * 3 + 1] = chosenColor.g;
      col[i * 3 + 2] = chosenColor.b;

      sca[i] = Math.random() * 0.04 + 0.015;
    }

    return [pos, col, sca];
  }, [count]);

  useFrame((state, delta) => {
    if (!pointsRef.current) return;

    const time = state.clock.getElapsedTime();
    
    // State responsive motion speed
    let speedMult = 0.2;
    if (assistantState === 'speaking') speedMult = 0.8;
    else if (assistantState === 'processing') speedMult = 0.6;
    else if (assistantState === 'listening' || assistantState === 'recording') speedMult = 0.5;

    pointsRef.current.rotation.y = time * 0.03 * speedMult;
    pointsRef.current.rotation.x = Math.sin(time * 0.02) * 0.05 * speedMult;

    // Pulse size / alpha
    const geometry = pointsRef.current.geometry;
    const positionAttr = geometry.attributes.position;
    
    if (assistantState === 'speaking' || assistantState === 'processing') {
      const scaleWave = 1 + Math.sin(time * 6) * 0.2;
      pointsRef.current.scale.set(scaleWave, scaleWave, scaleWave);
    } else {
      pointsRef.current.scale.set(1, 1, 1);
    }
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
        <bufferAttribute
          attach="attributes-color"
          args={[colors, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.06}
        vertexColors
        transparent
        opacity={0.65}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}
