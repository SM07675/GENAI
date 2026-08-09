import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export function CyberGrid() {
  const gridRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (!gridRef.current) return;
    const time = state.clock.getElapsedTime();
    
    // Slow grid rotation and drift
    gridRef.current.rotation.z = Math.sin(time * 0.05) * 0.03;
    
    if (gridRef.current.material) {
      const mat = gridRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.12 + Math.sin(time * 1.5) * 0.03;
    }
  });

  return (
    <mesh
      ref={gridRef}
      position={[0, -0.16, 0]}
      rotation={[-Math.PI / 2, 0, 0]}
    >
      <planeGeometry args={[20, 20, 40, 40]} />
      <meshBasicMaterial
        color="#00f0ff"
        wireframe
        transparent
        opacity={0.12}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
}
