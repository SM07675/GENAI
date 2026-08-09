/**
 * GenieAvatar.jsx
 * Procedural state-driven 3D Avatar component for Genie OS.
 * Supports standard biped skeleton + new finger & jaw rig (avatar_finger_jaw_rig_v1.glb).
 */

import React, { useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { useGLTF } from '@react-three/drei';
import { clone } from 'three/examples/jsm/utils/SkeletonUtils.js';

// Comprehensive Bone Mapping including new Finger & Jaw joints
const BONE_NAMES = {
  hip: 'Hip',
  pelvis: 'Pelvis',
  waist: 'Waist',
  spine1: 'Spine01',
  spine2: 'Spine02',
  neck1: 'NeckTwist01',
  neck2: 'NeckTwist02',
  head: 'Head',
  jaw: 'Jaw',
  lClavicle: 'L_Clavicle',
  lUpperarm: 'L_Upperarm',
  lForearm: 'L_Forearm',
  lHand: 'L_Hand',
  rClavicle: 'R_Clavicle',
  rUpperarm: 'R_Upperarm',
  rForearm: 'R_Forearm',
  rHand: 'R_Hand',
  lThigh: 'L_Thigh',
  rThigh: 'R_Thigh',

  // Left Hand Fingers
  lThumb1: 'L_Thumb1', lThumb2: 'L_Thumb2', lThumb3: 'L_Thumb3',
  lIndex1: 'L_Index1', lIndex2: 'L_Index2', lIndex3: 'L_Index3',
  lMiddle1: 'L_Middle1', lMiddle2: 'L_Middle2', lMiddle3: 'L_Middle3',
  lRing1: 'L_Ring1', lRing2: 'L_Ring2', lRing3: 'L_Ring3',
  lPinky1: 'L_Pinky1', lPinky2: 'L_Pinky2', lPinky3: 'L_Pinky3',

  // Right Hand Fingers
  rThumb1: 'R_Thumb1', rThumb2: 'R_Thumb2', rThumb3: 'R_Thumb3',
  rIndex1: 'R_Index1', rIndex2: 'R_Index2', rIndex3: 'R_Index3',
  rMiddle1: 'R_Middle1', rMiddle2: 'R_Middle2', rMiddle3: 'R_Middle3',
  rRing1: 'R_Ring1', rRing2: 'R_Ring2', rRing3: 'R_Ring3',
  rPinky1: 'R_Pinky1', rPinky2: 'R_Pinky2', rPinky3: 'R_Pinky3',
};

// Finger helper: generates gentle curl offsets for all fingers
function relaxedHandCurl(deg = 15) {
  return {
    lIndex1: [0, 0, deg], lIndex2: [0, 0, deg * 1.2], lIndex3: [0, 0, deg * 0.8],
    lMiddle1: [0, 0, deg * 1.1], lMiddle2: [0, 0, deg * 1.3], lMiddle3: [0, 0, deg * 0.8],
    lRing1: [0, 0, deg * 1.2], lRing2: [0, 0, deg * 1.4], lRing3: [0, 0, deg * 0.9],
    lPinky1: [0, 0, deg * 1.3], lPinky2: [0, 0, deg * 1.5], lPinky3: [0, 0, deg * 1.0],
    lThumb1: [5, 10, 8], lThumb2: [0, 0, 10],

    rIndex1: [0, 0, -deg], rIndex2: [0, 0, -deg * 1.2], rIndex3: [0, 0, -deg * 0.8],
    rMiddle1: [0, 0, -deg * 1.1], rMiddle2: [0, 0, -deg * 1.3], rMiddle3: [0, 0, -deg * 0.8],
    rRing1: [0, 0, -deg * 1.2], rRing2: [0, 0, -deg * 1.4], rRing3: [0, 0, -deg * 0.9],
    rPinky1: [0, 0, -deg * 1.3], rPinky2: [0, 0, -deg * 1.5], rPinky3: [0, 0, -deg * 1.0],
    rThumb1: [5, -10, -8], rThumb2: [0, 0, -10],
  };
}

// Pose library with fine-tuned Euler offsets (degrees)
const POSES = {
  idle: {
    spine1: [2, 0, 0],
    spine2: [1, 0, 0],
    lClavicle: [0, 0, -4],
    rClavicle: [0, 0, 4],
    lUpperarm: [5, 0, -8],
    rUpperarm: [5, 0, 8],
    ...relaxedHandCurl(14),
  },
  wake: {
    spine2: [-6, 0, 0],
    head: [-10, 0, 0],
    lClavicle: [0, 0, -4],
    rClavicle: [0, 0, 4],
    lUpperarm: [8, 0, -10],
    rUpperarm: [8, 0, 10],
    ...relaxedHandCurl(10),
  },
  listening: {
    spine1: [5, 0, 0],
    spine2: [4, 0, 0],
    head: [-2, 0, 6],
    lUpperarm: [12, 0, -14],
    lForearm: [0, 0, -35],
    rUpperarm: [12, 0, 14],
    rForearm: [0, 0, 35],
    ...relaxedHandCurl(18),
  },
  thinking: {
    spine1: [2, 5, 0],
    head: [10, -8, 6],
    rClavicle: [0, 0, 10],
    rUpperarm: [50, 15, 35],
    rForearm: [0, 0, 115],
    lClavicle: [0, 0, 2],
    lUpperarm: [10, 0, -12],
    rIndex1: [0, 0, -25], rIndex2: [0, 0, -40], // Finger near chin/head
    rMiddle1: [0, 0, -35], rRing1: [0, 0, -40], rPinky1: [0, 0, -45],
    ...relaxedHandCurl(12),
  },
  working: {
    spine1: [4, 0, 0],
    head: [5, 0, 0],
    lClavicle: [0, 0, -2],
    rClavicle: [0, 0, 2],
    lUpperarm: [20, 10, -15],
    rUpperarm: [20, -10, 15],
    lForearm: [0, 0, -45],
    rForearm: [0, 0, 45],
    ...relaxedHandCurl(20),
  },
  speaking: {
    spine1: [2, 0, 0],
    head: [-3, 0, 0],
    lClavicle: [0, 0, -6],
    lUpperarm: [18, 0, -22],
    rClavicle: [0, 0, 6],
    rUpperarm: [18, 0, 22],
    ...relaxedHandCurl(8),
  },
  success: {
    head: [8, 0, 0],
    rClavicle: [0, 0, 8],
    rUpperarm: [25, 0, 20],
    rForearm: [0, 0, 30],
    lClavicle: [0, 0, -4],
    lUpperarm: [10, 0, -12],
    rThumb1: [20, -15, -15], rIndex1: [0, 0, -30], // Thumbs up hint
  },
  error: {
    head: [5, 0, 0],
    spine1: [-4, 0, 0],
    lClavicle: [0, 0, -2],
    rClavicle: [0, 0, 2],
    lUpperarm: [15, 0, -10],
    rUpperarm: [15, 0, 10],
    ...relaxedHandCurl(25),
  },
  sleep: {
    head: [20, 0, 0],
    spine1: [8, 0, 0],
    spine2: [5, 0, 0],
    lClavicle: [0, 0, -2],
    rClavicle: [0, 0, 2],
    lUpperarm: [2, 0, -5],
    rUpperarm: [2, 0, 5],
    ...relaxedHandCurl(30),
  },
};

const ONE_SHOTS = {
  error: { bone: 'head', axis: 'y', amplitude: 12, cycles: 2.5, duration: 700 },
  success: { bone: 'head', axis: 'x', amplitude: 8, cycles: 1.5, duration: 500 },
  wake: { bone: 'head', axis: 'x', amplitude: 6, cycles: 1, duration: 400 },
};

const TRANSITION_MS = {
  idle: 600,
  wake: 350,
  listening: 400,
  thinking: 500,
  working: 400,
  speaking: 300,
  success: 250,
  error: 250,
  sleep: 900,
};

const DEG2RAD = Math.PI / 180;
const _eulerScratch = new THREE.Euler();

function eulerDegToQuat(deg, out) {
  if (!deg) return out.identity();
  _eulerScratch.set(deg[0] * DEG2RAD, deg[1] * DEG2RAD, deg[2] * DEG2RAD, 'XYZ');
  return out.setFromEuler(_eulerScratch);
}

function singleAxisQuat(axis, degrees, out) {
  const e = [0, 0, 0];
  e[axis === 'x' ? 0 : axis === 'y' ? 1 : 2] = degrees;
  return eulerDegToQuat(e, out);
}

export function GenieAvatar({
  modelUrl = './models/avatar_finger_jaw_rig_v1.glb',
  state = 'idle',
  lookAt = null,
  gestureIntensity = 0.6,
  scale = 1,
  position = [0, 0, 0],
}) {
  const gltf = useGLTF(modelUrl);
  const scene = useMemo(() => clone(gltf.scene), [gltf.scene]);

  // Adjust material properties for modern lighting rendering
  useEffect(() => {
    scene.traverse((child) => {
      if (child.isMesh) {
        child.castShadow = true;
        child.receiveShadow = true;
        if (child.material) {
          child.material.roughness = Math.min(0.65, child.material.roughness || 0.5);
          child.material.metalness = Math.max(0.05, child.material.metalness || 0.1);
        }
      }
    });
  }, [scene]);

  const bones = useRef({});
  const restQuats = useRef({});
  const poseQuats = useRef({});

  const stateRef = useRef(state);
  const transitionStart = useRef(0);
  const oneShotStart = useRef(null);
  const activeOneShot = useRef(null);

  const clock = useRef(0);

  // Discover bone references & store initial rest quaternions
  useEffect(() => {
    const found = {};
    scene.traverse((obj) => {
      if (obj.isBone) {
        for (const key of Object.keys(BONE_NAMES)) {
          if (obj.name === BONE_NAMES[key]) found[key] = obj;
        }
      }
    });
    bones.current = found;

    const rests = {};
    const poses = {};
    for (const key of Object.keys(found)) {
      rests[key] = found[key].quaternion.clone();
      poses[key] = found[key].quaternion.clone();
    }
    restQuats.current = rests;
    poseQuats.current = poses;
  }, [scene]);

  // Trigger state transitions & one-shots
  useEffect(() => {
    const normalizedState = POSES[state] ? state : 'idle';
    if (normalizedState !== stateRef.current) {
      stateRef.current = normalizedState;
      transitionStart.current = clock.current;
      const oneShot = ONE_SHOTS[normalizedState];
      if (oneShot) {
        activeOneShot.current = oneShot;
        oneShotStart.current = clock.current;
      }
    }
  }, [state]);

  const additiveQuats = useRef({});
  const scratchQuat = useRef(new THREE.Quaternion());

  useFrame((_, delta) => {
    clock.current += delta;
    const t = clock.current;
    const keys = Object.keys(BONE_NAMES);

    // Reset additive layer
    const additive = additiveQuats.current;
    for (const key of keys) {
      if (!additive[key]) additive[key] = new THREE.Quaternion();
      else additive[key].identity();
    }

    const addToBone = (key, axis, degrees) => {
      if (!key || degrees === 0) return;
      const q = additive[key];
      if (!q) return;
      singleAxisQuat(axis, degrees, scratchQuat.current);
      q.multiply(scratchQuat.current);
    };

    // 1. Pose layer interpolation
    const activeState = stateRef.current;
    const activePose = POSES[activeState] || POSES.idle;
    const elapsedMs = (t - transitionStart.current) * 1000;
    const duration = TRANSITION_MS[activeState] || 500;
    const blend = Math.min(1, elapsedMs / duration);
    const eased = 1 - Math.pow(1 - blend, 3);

    for (const key of keys) {
      const rest = restQuats.current[key];
      const pose = poseQuats.current[key];
      if (!rest || !pose) continue;
      const targetDelta = eulerDegToQuat(activePose[key], scratchQuat.current.clone());
      const targetQuat = rest.clone().multiply(targetDelta);
      pose.slerp(targetQuat, Math.min(1, eased + delta * 2));
    }

    // 2. Base layer (Breathing and natural idle sway)
    const breathWeight = activeState === 'idle' || activeState === 'sleep' ? 1 : 0.4;
    const breathSpeed = activeState === 'sleep' ? 0.35 : 1.1;
    addToBone('spine2', 'x', Math.sin(t * breathSpeed * 1.2) * 1.5 * breathWeight);
    if (activeState === 'idle') {
      addToBone('hip', 'z', Math.sin(t * 0.3) * 2.0);
    }

    // 3. Speaking gesture layer & procedural Jaw animation
    if (activeState === 'speaking') {
      const amp = 8 + gestureIntensity * 22;
      addToBone('rUpperarm', 'z', Math.sin(t * 3.4) * amp);
      addToBone('lUpperarm', 'z', Math.sin(t * 3.4 + 0.8) * -amp * 0.65);
      addToBone('rForearm', 'z', Math.sin(t * 3.4 + 0.4) * amp * 0.5);

      // Subtle procedural jaw movement while speaking if Jaw bone is present
      const jawOpen = (Math.sin(t * 14) * 0.5 + 0.5) * (8 + gestureIntensity * 12);
      addToBone('jaw', 'x', jawOpen);
    }

    // 4. One-shot gestures (wake, success, error)
    if (activeOneShot.current && oneShotStart.current !== null) {
      const shot = activeOneShot.current;
      const elapsed = (t - oneShotStart.current) * 1000;
      if (elapsed < shot.duration) {
        const progress = elapsed / shot.duration;
        const decay = 1 - progress;
        const wave = Math.sin(progress * Math.PI * 2 * shot.cycles) * shot.amplitude * decay;
        addToBone(shot.bone, shot.axis, wave);
      } else {
        activeOneShot.current = null;
        oneShotStart.current = null;
      }
    }

    // 5. Apply pose + additive to bones
    for (const key of keys) {
      const bone = bones.current[key];
      const pose = poseQuats.current[key];
      const add = additive[key];
      if (!bone || !pose) continue;
      bone.quaternion.copy(pose);
      if (add) bone.quaternion.multiply(add);
    }

    // Head look-at tracking (bounded for natural movement)
    if (lookAt && bones.current.head) {
      const headBone = bones.current.head;
      const worldPos = new THREE.Vector3();
      headBone.getWorldPosition(worldPos);
      
      const dir = new THREE.Vector3(...lookAt).sub(worldPos).normalize();
      // Clamp direction horizontal/vertical angle
      const maxAngle = 0.55; // ~31 degrees max turn
      const forward = new THREE.Vector3(0, 0, 1);
      const angle = forward.angleTo(dir);
      
      if (angle < maxAngle) {
        const desired = new THREE.Quaternion().setFromUnitVectors(forward, dir);
        headBone.quaternion.slerp(desired, 0.08);
      }
    }
  });

  return <primitive object={scene} scale={scale} position={position} />;
}

useGLTF.preload('./models/avatar_finger_jaw_rig_v1.glb');
useGLTF.preload('./models/genie_avatar.glb');
