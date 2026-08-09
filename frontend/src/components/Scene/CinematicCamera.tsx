import { useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

interface CinematicCameraProps {
  speed?: number;
}

export function CinematicCamera({ speed = 0.5 }: CinematicCameraProps) {
  const { camera, pointer } = useThree();
  const basePosition = useRef(new THREE.Vector3(0, 1.4, 3.8));
  const baseLookAt = useRef(new THREE.Vector3(0, 1.2, 0));

  useFrame((state) => {
    const time = state.clock.getElapsedTime() * speed;

    // 1. Slow subtle orbital drift (Very small movement & tiny rotation)
    const floatX = Math.sin(time * 0.4) * 0.18;
    const floatY = Math.cos(time * 0.3) * 0.12;
    
    // 2. Very slow zoom oscillation
    const zoomZ = Math.sin(time * 0.2) * 0.15;

    // 3. Mouse Parallax (tiny response to cursor)
    const parallaxX = pointer.x * 0.15;
    const parallaxY = pointer.y * 0.12;

    // Compute target camera position
    const targetX = basePosition.current.x + floatX + parallaxX;
    const targetY = basePosition.current.y + floatY + parallaxY;
    const targetZ = basePosition.current.z + zoomZ;

    // Smooth lerp camera position
    camera.position.x = THREE.MathUtils.lerp(camera.position.x, targetX, 0.04);
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, targetY, 0.04);
    camera.position.z = THREE.MathUtils.lerp(camera.position.z, targetZ, 0.04);

    // Look at character upper chest/head area with subtle float
    const targetLookX = baseLookAt.current.x + floatX * 0.2;
    const targetLookY = baseLookAt.current.y + floatY * 0.2;
    camera.lookAt(targetLookX, targetLookY, baseLookAt.current.z);
  });

  return null;
}
