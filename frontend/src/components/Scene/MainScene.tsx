import { Canvas } from '@react-three/fiber';
import { ContactShadows } from '@react-three/drei';
import * as THREE from 'three';
import { Lighting } from './Lighting';
import { Particles } from './Particles';
import { CyberGrid } from './CyberGrid';
import { CinematicCamera } from './CinematicCamera';
import { CharacterContainer } from '../Character/CharacterContainer';
import { AssistantState } from '../../types';

interface MainSceneProps {
  assistantState: AssistantState;
  onClipsDetected?: (clips: string[]) => void;
}

export function MainScene({ assistantState, onClipsDetected }: MainSceneProps) {
  return (
    <div className="relative w-full h-full overflow-hidden bg-slate-950">
      {/* Dynamic Animated Moving Dark Cyber-Aurora Backdrop ("blackish & moving") */}
      <div 
        className="absolute inset-0 pointer-events-none z-0 opacity-80"
        style={{
          background: 'radial-gradient(ellipse at 50% 50%, rgba(15, 23, 42, 0.9) 0%, rgba(2, 6, 23, 1) 100%)'
        }}
      />
      
      {/* Moving Ambient Radial Light Blob */}
      <div className="absolute inset-0 pointer-events-none z-0 genie-bg-moving" />

      {/* R3F 3D Canvas */}
      <Canvas
        shadows
        camera={{ position: [0, 1.4, 3.8], fov: 45 }}
        gl={{
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.15,
          antialias: true,
          powerPreference: 'high-performance'
        }}
        className="w-full h-full z-10"
      >
        {/* Cinematic Slow Floating Camera */}
        <CinematicCamera speed={0.5} />

        {/* Ambient & Cyber Rim Lighting */}
        <Lighting assistantState={assistantState} />

        {/* Reactive Particle Field */}
        <Particles assistantState={assistantState} count={1400} />

        {/* Moving Cyber Grid Floor */}
        <CyberGrid />

        {/* Soft Contact Shadow beneath character */}
        <ContactShadows
          position={[0, -0.15, 0]}
          opacity={0.7}
          scale={5}
          blur={2.0}
          far={4}
          color="#0284c7"
        />

        {/* Center 3D Character Model */}
        <group position={[0, -0.15, 0]}>
          <CharacterContainer
            assistantState={assistantState}
            onClipsDetected={onClipsDetected}
          />
        </group>
      </Canvas>
    </div>
  );
}
