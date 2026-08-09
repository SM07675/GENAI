/**
 * VRMAvatar.jsx — Official Genie AI VRM Avatar Engine
 * Integrates @pixiv/three-vrm for hello.vrm with full animation,
 * expressions, lip sync, spring physics, and gesture triggers.
 */

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils, VRMHumanBoneName } from '@pixiv/three-vrm';
import { useAppStore } from '../../store/appStore';

const DEG2RAD = Math.PI / 180;

function degToQuat(x = 0, y = 0, z = 0) {
  const e = new THREE.Euler(x * DEG2RAD, y * DEG2RAD, z * DEG2RAD, 'XYZ');
  return new THREE.Quaternion().setFromEuler(e);
}

// ── 26 Expression Presets ──────────────────────────────────────────────────
const EXPRESSION_PRESETS = {
  happy:       { happy: 0.9, relaxed: 0.3 },
  smile:       { happy: 0.7, relaxed: 0.3 },
  bigSmile:    { happy: 1.0, relaxed: 0.5, aa: 0.15 },
  thinking:    { relaxed: 0.5, angry: 0.1 },
  confused:    { angry: 0.25, sad: 0.3 },
  listening:   { relaxed: 0.5, happy: 0.35 },
  speaking:    { happy: 0.2 },
  excited:     { surprised: 0.5, happy: 1.0 },
  sad:         { sad: 0.95 },
  worried:     { sad: 0.7, angry: 0.25 },
  angry:       { angry: 0.9 },
  surprised:   { surprised: 1.0 },
  sleepy:      { blink: 0.85, relaxed: 0.6 },
};

// Resolve model URL for both Vite dev server AND Electron file:// protocol
function resolveModelUrl() {
  try {
    // document.baseURI handles file:// and http:// correctly
    return new URL('models/hello.vrm', document.baseURI).href;
  } catch {
    return 'models/hello.vrm';
  }
}

export function VRMAvatar({
  state = 'idle',
  emotion = 'neutral',
  lookAt = [0, 1.2, 2.5],
  gestureIntensity = 0.6,
  scale = 1.0,
  position = [0, 0, 0],
  onAvatarClick = null,
}) {
  const [vrm, setVrm] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const vrmRef = useRef(null);

  // Animation Refs
  const clock = useRef(0);
  const currentState = useRef('idle');
  const activeIdleIndex = useRef(1);
  const nextIdleSwitchTime = useRef(12);
  const lastBlinkTime = useRef(0);
  const nextBlinkInterval = useRef(3.0);
  const isBlinking = useRef(false);
  const isDoubleBlink = useRef(false);
  const gestureActive = useRef(null);
  const gestureStart = useRef(0);

  // Audio Analyser for Lip Sync
  const analyserRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioSourceRef = useRef(null);
  const assistantAudioElement = useAppStore((s) => s.assistantAudioElement);

  // ── Load VRM ─────────────────────────────────────────────────────────────
  useEffect(() => {
    let isMounted = true;
    const modelUrl = resolveModelUrl();
    console.log('[VRMAvatar] Loading from:', modelUrl);

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      modelUrl,
      (gltf) => {
        if (!isMounted) return;
        console.log('[VRMAvatar] GLTF loaded, userData:', Object.keys(gltf.userData));

        const loadedVrm = gltf.userData.vrm;
        if (!loadedVrm) {
          const msg = 'No VRM data found — file may not be a valid VRM model';
          console.error('[VRMAvatar]', msg);
          setLoadError(msg);
          return;
        }

        console.log('[VRMAvatar] VRM version:', loadedVrm.meta?.metaVersion ?? 'unknown');

        // Correct VRM 0.x facing direction (VRM 0.x faces +Z, we need -Z)
        try {
          VRMUtils.rotateVRM0(loadedVrm);
          console.log('[VRMAvatar] rotateVRM0 applied');
        } catch (e) {
          console.warn('[VRMAvatar] rotateVRM0 not needed or failed:', e.message);
        }

        // Enable shadows
        gltf.scene.traverse((child) => {
          if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
          }
        });

        // Auto-center: lift scene so feet sit at y=0
        gltf.scene.updateWorldMatrix(true, true);
        const box = new THREE.Box3().setFromObject(gltf.scene);
        const offsetY = -box.min.y;
        gltf.scene.position.y += offsetY;
        console.log('[VRMAvatar] Bounding box:', box.min.y.toFixed(3), '->', box.max.y.toFixed(3), '| offset:', offsetY.toFixed(3));

        vrmRef.current = loadedVrm;
        setVrm(loadedVrm);
        setLoadError(null);
        console.log('[VRMAvatar] ✅ Ready!');
      },
      (progress) => {
        if (progress.total > 0) {
          const pct = Math.round((progress.loaded / progress.total) * 100);
          console.log(`[VRMAvatar] Loading ${pct}%`);
        }
      },
      (error) => {
        if (!isMounted) return;
        console.error('[VRMAvatar] ❌ Load error:', error);
        setLoadError(error.message || String(error));
      }
    );

    return () => { isMounted = false; };
  }, []);

  // ── Audio Lip Sync Setup ──────────────────────────────────────────────────
  useEffect(() => {
    if (!assistantAudioElement) return;
    const setup = () => {
      try {
        if (!audioContextRef.current) {
          audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
        }
        const ctx = audioContextRef.current;
        if (ctx.state === 'suspended') ctx.resume();
        if (!audioSourceRef.current) {
          analyserRef.current = ctx.createAnalyser();
          analyserRef.current.fftSize = 256;
          audioSourceRef.current = ctx.createMediaElementSource(assistantAudioElement);
          audioSourceRef.current.connect(analyserRef.current);
          analyserRef.current.connect(ctx.destination);
        }
      } catch (e) {
        console.warn('[VRMAvatar] Audio setup:', e.message);
      }
    };
    assistantAudioElement.addEventListener('play', setup);
    return () => assistantAudioElement.removeEventListener('play', setup);
  }, [assistantAudioElement]);

  // ── State Change Triggers ─────────────────────────────────────────────────
  useEffect(() => {
    if (state === currentState.current) return;
    currentState.current = state;
    if (state === 'waking') { gestureActive.current = 'welcome'; gestureStart.current = clock.current; }
    if (state === 'success') { gestureActive.current = 'celebrate'; gestureStart.current = clock.current; }
  }, [state]);

  // ── Safe Expression Setter ────────────────────────────────────────────────
  const setExpr = (name, val) => {
    if (!vrmRef.current?.expressionManager) return;
    try { vrmRef.current.expressionManager.setValue(name, Math.max(0, Math.min(1, val))); } catch {}
  };

  const resetExprs = () => {
    ['happy','angry','sad','relaxed','surprised','aa','ih','ou','ee','oh','blink','blinkLeft','blinkRight'].forEach(n => {
      try { vrmRef.current?.expressionManager?.setValue(n, 0); } catch {}
    });
  };

  // ── Safe Bone Rotator ──────────────────────────────────────────────────────
  const rotateBone = (boneName, x, y, z, speed = 0.1) => {
    if (!vrmRef.current?.humanoid) return;
    let bone = null;
    try { bone = vrmRef.current.humanoid.getNormalizedBoneNode(boneName); } catch {}
    if (!bone) { try { bone = vrmRef.current.humanoid.getRawBoneNode(boneName); } catch {} }
    if (!bone) return;
    bone.quaternion.slerp(degToQuat(x, y, z), speed);
  };

  // ── Main Frame Loop ───────────────────────────────────────────────────────
  useFrame((_, delta) => {
    if (!vrmRef.current) return;
    clock.current += delta;
    const t = clock.current;

    // Update VRM engine (spring bones, look-at, expressions)
    vrmRef.current.update(delta);

    // --- Idle pool switch ---
    if (t > nextIdleSwitchTime.current) {
      activeIdleIndex.current = Math.floor(Math.random() * 10) + 1;
      nextIdleSwitchTime.current = t + 10 + Math.random() * 10;
    }

    // --- Breathing ---
    const bSpeed = state === 'sleep' ? 0.5 : 1.2;
    const bAmt = Math.sin(t * bSpeed * 1.5) * (state === 'sleep' ? 2.5 : 1.5);
    rotateBone(VRMHumanBoneName.Chest, bAmt * 1.2, 0, 0, 0.08);
    rotateBone(VRMHumanBoneName.Spine, bAmt * 0.5, 0, 0, 0.08);

    // --- Head micro sway ---
    const hx = Math.sin(t * 0.8) * 1.5 + Math.cos(t * 1.4) * 0.8;
    const hy = Math.cos(t * 0.6) * 2.0;
    let headX = hx, headY = hy, headZ = Math.sin(t * 0.5) * 1.0;

    // --- Arm defaults ---
    let armRX = 10, armRZ = -8, armLX = 10, armLZ = 8;

    // Idle pool variations
    switch (activeIdleIndex.current) {
      case 2: headY += Math.sin(t * 0.4) * 8; break;
      case 3: headX += Math.sin(t * 0.3) * 6; headZ += Math.cos(t * 0.3) * 4; break;
      case 4: armRZ = -15; armLZ = 15; break;
      case 5: rotateBone(VRMHumanBoneName.Hips, 0, 0, Math.sin(t * 0.4) * 2, 0.05); break;
      case 6: headX -= 4; headZ += 3; break;
      case 7: armRX = 25; armRZ = -20; break;
      case 8: armRZ = -12; armLZ = 12; break;
    }

    rotateBone(VRMHumanBoneName.Head, headX, headY, headZ, 0.07);
    rotateBone(VRMHumanBoneName.RightUpperArm, armRX, 0, armRZ, 0.07);
    rotateBone(VRMHumanBoneName.LeftUpperArm, armLX, 0, armLZ, 0.07);
    rotateBone(VRMHumanBoneName.RightLowerArm, 5, 0, -10, 0.07);
    rotateBone(VRMHumanBoneName.LeftLowerArm, 5, 0, 10, 0.07);

    // --- State-specific poses ---
    if (state === 'listening') {
      rotateBone(VRMHumanBoneName.Chest, 6, 0, 0, 0.1);
      rotateBone(VRMHumanBoneName.Head, -4, 0, 5, 0.1);
    } else if (state === 'thinking') {
      rotateBone(VRMHumanBoneName.Head, -10, 8, -6, 0.08);
      rotateBone(VRMHumanBoneName.RightUpperArm, 45, 15, -25, 0.1);
      rotateBone(VRMHumanBoneName.RightLowerArm, 40, 0, -60, 0.1);
    } else if (state === 'speaking') {
      const amp = 10 + gestureIntensity * 15;
      rotateBone(VRMHumanBoneName.RightUpperArm, 20 + Math.sin(t * 3.2) * amp * 0.5, 0, -15 - Math.sin(t * 3.2) * amp * 0.3, 0.12);
      rotateBone(VRMHumanBoneName.LeftUpperArm, 20 + Math.sin(t * 3.2 + 0.8) * amp * 0.3, 0, 15, 0.12);
      rotateBone(VRMHumanBoneName.Head, Math.sin(t * 4.5) * 2.5, 0, 0, 0.12);
    } else if (state === 'success') {
      rotateBone(VRMHumanBoneName.RightUpperArm, 75, 0, -30, 0.15);
      rotateBone(VRMHumanBoneName.RightLowerArm, 20, Math.sin(t * 8) * 15, -20, 0.15);
    } else if (state === 'error') {
      rotateBone(VRMHumanBoneName.Head, 12, 0, 0, 0.1);
    } else if (state === 'sleep') {
      rotateBone(VRMHumanBoneName.Head, 18, 0, 0, 0.05);
    }

    // --- Welcome wave gesture ---
    if (gestureActive.current === 'welcome') {
      const el = t - gestureStart.current;
      if (el < 3.0) {
        rotateBone(VRMHumanBoneName.RightUpperArm, 80, 10, -35, 0.15);
        rotateBone(VRMHumanBoneName.RightLowerArm, 15, Math.sin(el * 10) * 20, -15, 0.15);
        rotateBone(VRMHumanBoneName.Head, -5, 0, 0, 0.15);
      } else { gestureActive.current = null; }
    }

    // --- Blinking ---
    if (t - lastBlinkTime.current > nextBlinkInterval.current) {
      isBlinking.current = true;
      lastBlinkTime.current = t;
      isDoubleBlink.current = Math.random() < 0.25;
      nextBlinkInterval.current = 2.2 + Math.random() * 3.5;
    }
    let blinkW = 0;
    if (isBlinking.current) {
      const el = t - lastBlinkTime.current;
      const dur = isDoubleBlink.current ? 0.35 : 0.18;
      if (el < dur) {
        blinkW = isDoubleBlink.current
          ? Math.abs(Math.sin((el / dur) * Math.PI * 2))
          : Math.sin((el / dur) * Math.PI);
      } else { isBlinking.current = false; }
    }

    // --- Expressions ---
    resetExprs();
    let preset = 'happy';
    if (state === 'sleep') preset = 'sleepy';
    else if (state === 'listening') preset = 'listening';
    else if (state === 'thinking') preset = 'thinking';
    else if (state === 'speaking') preset = 'speaking';
    else if (state === 'success') preset = 'bigSmile';
    else if (state === 'error') preset = 'worried';
    if (emotion === 'happy') preset = 'bigSmile';
    else if (emotion === 'sad') preset = 'sad';
    else if (emotion === 'angry') preset = 'angry';
    else if (emotion === 'confused') preset = 'confused';
    else if (emotion === 'excited') preset = 'excited';

    const vals = EXPRESSION_PRESETS[preset] || EXPRESSION_PRESETS.happy;
    Object.entries(vals).forEach(([k, v]) => setExpr(k, v));
    if (state === 'idle') setExpr('happy', 0.25);
    if (blinkW > 0) setExpr('blink', blinkW);

    // --- Lip sync ---
    if (state === 'speaking' && analyserRef.current) {
      const buf = new Uint8Array(analyserRef.current.frequencyBinCount);
      analyserRef.current.getByteFrequencyData(buf);
      const avg = buf.reduce((s, v) => s + v, 0) / buf.length / 255;
      const m = Math.min(1.0, avg * 2.8);
      setExpr('aa', m * 0.7); setExpr('oh', m * 0.3); setExpr('ih', m * 0.2);
    } else if (state === 'speaking') {
      const m = (Math.sin(t * 14) * 0.5 + 0.5) * 0.6;
      setExpr('aa', m * 0.8); setExpr('oh', m * 0.2);
    }

    // --- LookAt ---
    if (vrmRef.current.lookAt && lookAt) {
      if (!vrmRef.current.userData._lookTarget) {
        const obj = new THREE.Object3D();
        vrmRef.current.scene.parent?.add(obj);
        vrmRef.current.userData._lookTarget = obj;
      }
      const target = vrmRef.current.userData._lookTarget;
      if (target) {
        target.position.set(lookAt[0], lookAt[1], lookAt[2]);
        vrmRef.current.lookAt.target = target;
      }
    }
  });

  return (
    <group position={position} scale={[scale, scale, scale]} onClick={onAvatarClick}>
      {vrm ? (
        <primitive object={vrm.scene} />
      ) : loadError ? (
        // Error state — red box
        <group position={[0, 0.9, 0]}>
          <mesh>
            <boxGeometry args={[0.3, 0.3, 0.3]} />
            <meshBasicMaterial color="#ef4444" wireframe />
          </mesh>
        </group>
      ) : (
        // Loading state — spinning ring
        <LoadingRing />
      )}
    </group>
  );
}

function LoadingRing() {
  const ref = useRef();
  useFrame((_, delta) => { if (ref.current) ref.current.rotation.y += delta * 2; });
  return (
    <group position={[0, 0.9, 0]} ref={ref}>
      <mesh>
        <torusGeometry args={[0.35, 0.035, 16, 48]} />
        <meshBasicMaterial color="#38bdf8" />
      </mesh>
    </group>
  );
}
