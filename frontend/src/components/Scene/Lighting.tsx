import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { AssistantState } from '../../types';

interface LightingProps {
  assistantState: AssistantState;
}

export function Lighting({ assistantState }: LightingProps) {
  const rimLightRef = useRef<THREE.PointLight>(null);
  const keyLightRef = useRef<THREE.DirectionalLight>(null);

  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    
    // Dynamic light pulsing according to state
    if (rimLightRef.current) {
      if (assistantState === 'speaking') {
        rimLightRef.current.intensity = 4 + Math.sin(time * 8) * 1.5;
        rimLightRef.current.color.set('#00f0ff');
      } else if (assistantState === 'processing') {
        rimLightRef.current.intensity = 3.5 + Math.sin(time * 12) * 1.2;
        rimLightRef.current.color.set('#8b5cf6');
      } else if (assistantState === 'listening' || assistantState === 'recording') {
        rimLightRef.current.intensity = 3.8 + Math.sin(time * 5) * 1.0;
        rimLightRef.current.color.set('#06b6d4');
      } else {
        rimLightRef.current.intensity = 2.5 + Math.sin(time * 2) * 0.4;
        rimLightRef.current.color.set('#3b82f6');
      }
    }
  });

  return (
    <>
      {/* Ambient Fill */}
      <ambientLight intensity={0.6} color="#0f172a" />

      {/* Main Front Key Light */}
      <directionalLight
        ref={keyLightRef}
        position={[3, 5, 4]}
        intensity={2.2}
        color="#ffffff"
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-bias={-0.0001}
      />

      {/* Soft Fill Light */}
      <directionalLight position={[-4, 3, -2]} intensity={0.8} color="#64748b" />

      {/* Futuristic Blue/Cyan Rim Light behind character */}
      <pointLight
        ref={rimLightRef}
        position={[0, 2.5, -2.5]}
        intensity={3.0}
        distance={10}
        color="#00f0ff"
      />

      {/* Floor Spotlight for subtle pedestal glow */}
      <spotLight
        position={[0, -0.5, 0]}
        target-position={[0, 1.5, 0]}
        intensity={1.2}
        angle={0.6}
        penumbra={1}
        color="#3b82f6"
      />
    </>
  );
}
