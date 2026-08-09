import { useRef, useEffect, useMemo } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import { AssistantState } from '../../types';
import { useAnimationManager } from '../../hooks/useAnimationManager';
import { ProceduralMotionController } from '../../animation/ProceduralMotion';

interface CharacterModelProps {
  modelPath?: string;
  assistantState: AssistantState;
  onClipsDetected?: (clips: string[]) => void;
}

export function CharacterModel({
  modelPath = '/model.glb',
  assistantState,
  onClipsDetected
}: CharacterModelProps) {
  const groupRef = useRef<THREE.Group>(null);
  const { scene, animations } = useGLTF(modelPath);
  const { pointer } = useThree();

  // Animation manager for GLB clips
  const { availableClips } = useAnimationManager(animations, groupRef, assistantState);

  // Notify parent of available clips for inspector
  useEffect(() => {
    if (availableClips && availableClips.length > 0 && onClipsDetected) {
      onClipsDetected(availableClips);
    }
  }, [availableClips, onClipsDetected]);

  // Procedural controller instance
  const proceduralController = useMemo(() => {
    if (scene) {
      return new ProceduralMotionController(scene);
    }
    return null;
  }, [scene]);

  // Model setup, centering, shadows, material enhancement
  useEffect(() => {
    if (!scene) return;

    scene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        if (mesh.material) {
          const mat = mesh.material as THREE.MeshStandardMaterial;
          mat.envMapIntensity = 1.3;
          mat.roughness = Math.max(0.2, mat.roughness ?? 0.5);
          mat.needsUpdate = true;
        }
      }
    });

    // Calculate bounding box and scale to fill ~75% of view height
    const box = new THREE.Box3().setFromObject(scene);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());

    const targetHeight = 2.2;
    const scaleFactor = size.y > 0 ? targetHeight / size.y : 1.0;

    scene.scale.setScalar(scaleFactor);

    // Center pivot
    scene.position.x = -center.x * scaleFactor;
    scene.position.y = -box.min.y * scaleFactor;
    scene.position.z = -center.z * scaleFactor;
  }, [scene]);

  // Frame update for smooth procedural motion overlay
  useFrame((state, delta) => {
    if (proceduralController && groupRef.current) {
      proceduralController.setMousePosition(pointer.x, pointer.y);
      proceduralController.update(delta, state.clock.getElapsedTime(), groupRef.current, {
        assistantState
      });
    }
  });

  return (
    <group ref={groupRef} dispose={null}>
      <primitive object={scene} />
    </group>
  );
}

useGLTF.preload('/model.glb');
