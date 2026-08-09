import * as THREE from 'three';

export interface ProceduralParams {
  breathingSpeed?: number;
  breathingIntensity?: number;
  swaySpeed?: number;
  swayIntensity?: number;
  assistantState?: string;
}

/**
 * High-performance, ultra-smooth procedural motion controller.
 * Uses frame-rate independent damping (THREE.MathUtils.damp) for butter-smooth motion.
 */
export class ProceduralMotionController {
  private initialPositions: Map<THREE.Object3D, THREE.Vector3> = new Map();
  private initialRotations: Map<THREE.Object3D, THREE.Euler> = new Map();

  private headBone: THREE.Object3D | null = null;
  private neckBone: THREE.Object3D | null = null;
  private spineBone: THREE.Object3D | null = null;
  private leftShoulder: THREE.Object3D | null = null;
  private rightShoulder: THREE.Object3D | null = null;

  private targetLookAt = new THREE.Vector3(0, 1.4, 4);
  private currentLookAt = new THREE.Vector3(0, 1.4, 4);

  // Micro-blinking state
  private blinkTimer = 0;
  private blinkDuration = 0.15;
  private blinkInterval = 3.5;

  constructor(sceneObject: THREE.Object3D) {
    this.findBones(sceneObject);
  }

  private findBones(root: THREE.Object3D) {
    root.traverse((child) => {
      const name = child.name.toLowerCase();
      if (!this.headBone && (name.includes('head') || name.includes('face'))) {
        this.headBone = child;
      } else if (!this.neckBone && name.includes('neck')) {
        this.neckBone = child;
      } else if (!this.spineBone && (name.includes('spine') || name.includes('chest') || name.includes('upper_body'))) {
        this.spineBone = child;
      } else if (!this.leftShoulder && (name.includes('shoulder_l') || name.includes('leftshoulder') || name.includes('clavicle_l'))) {
        this.leftShoulder = child;
      } else if (!this.rightShoulder && (name.includes('shoulder_r') || name.includes('rightshoulder') || name.includes('clavicle_r'))) {
        this.rightShoulder = child;
      }

      // Save baseline transforms
      this.initialPositions.set(child, child.position.clone());
      this.initialRotations.set(child, child.rotation.clone());
    });
  }

  public setMousePosition(normalizedX: number, normalizedY: number) {
    // Smoothly map cursor to 3D focus point
    this.targetLookAt.x = normalizedX * 1.2;
    this.targetLookAt.y = normalizedY * 0.9 + 1.3;
    this.targetLookAt.z = 3.8;
  }

  public update(delta: number, elapsedTime: number, sceneObject: THREE.Object3D, params?: ProceduralParams) {
    const state = params?.assistantState || 'idle';
    const breathSpeed = state === 'speaking' ? 2.8 : state === 'listening' ? 1.4 : 1.8;
    const breathIntensity = state === 'speaking' ? 0.025 : 0.018;
    const swaySpeed = 0.9;
    const swayIntensity = 0.012;

    // 1. Procedural Breathing (Sine wave root & spine offset)
    const breathCycle = Math.sin(elapsedTime * breathSpeed);
    const breathOffset = breathCycle * breathIntensity;

    // Dampened smooth root position offset
    sceneObject.position.y = THREE.MathUtils.damp(
      sceneObject.position.y,
      -0.15 + breathOffset * 0.06,
      3.0,
      delta
    );

    // Spine breathing flex
    if (this.spineBone) {
      const initRot = this.initialRotations.get(this.spineBone) || new THREE.Euler();
      const targetSpineX = initRot.x + breathCycle * 0.015;
      this.spineBone.rotation.x = THREE.MathUtils.damp(this.spineBone.rotation.x, targetSpineX, 4.0, delta);
    }

    // 2. Weight Shifting (Gentle lateral sway)
    const swayX = Math.sin(elapsedTime * swaySpeed) * swayIntensity;
    const swayZ = Math.cos(elapsedTime * swaySpeed * 0.7) * (swayIntensity * 0.6);

    sceneObject.rotation.z = THREE.MathUtils.damp(sceneObject.rotation.z, swayX * 0.25, 2.5, delta);
    sceneObject.rotation.x = THREE.MathUtils.damp(sceneObject.rotation.x, swayZ * 0.2, 2.5, delta);

    // 3. Smooth Eye / Head Cursor Tracking (Exponential Decay Dampening)
    this.currentLookAt.x = THREE.MathUtils.damp(this.currentLookAt.x, this.targetLookAt.x, 4.5, delta);
    this.currentLookAt.y = THREE.MathUtils.damp(this.currentLookAt.y, this.targetLookAt.y, 4.5, delta);

    if (this.headBone) {
      const initHeadRot = this.initialRotations.get(this.headBone) || new THREE.Euler();

      // State specific head motion overlays
      let extraHeadX = 0;
      let extraHeadY = 0;

      if (state === 'listening' || state === 'recording') {
        extraHeadX = Math.sin(elapsedTime * 2.0) * 0.04 - 0.05; // Attentive nod
      } else if (state === 'speaking') {
        extraHeadX = Math.sin(elapsedTime * 5.0) * 0.03; // Rhythmic speaking motion
        extraHeadY = Math.cos(elapsedTime * 3.5) * 0.04;
      } else if (state === 'processing' || state === 'thinking') {
        extraHeadX = -0.08; // Pondering tilt
        extraHeadY = 0.10;
      } else if (state === 'error') {
        extraHeadX = 0.08;  // Confused tilt
        extraHeadY = -0.08;
      } else if (state === 'success') {
        extraHeadX = -0.05; // Joyful posture
      } else if (state === 'waking') {
        extraHeadX = -0.12; // Waking head raise
      }

      const targetHeadY = initHeadRot.y + Math.max(-0.45, Math.min(0.45, this.currentLookAt.x * 0.25)) + extraHeadY;
      const targetHeadX = initHeadRot.x + Math.max(-0.35, Math.min(0.35, (-this.currentLookAt.y + 1.3) * 0.22)) + extraHeadX;

      this.headBone.rotation.y = THREE.MathUtils.damp(this.headBone.rotation.y, targetHeadY, 5.0, delta);
      this.headBone.rotation.x = THREE.MathUtils.damp(this.headBone.rotation.x, targetHeadX, 5.0, delta);
    }

    if (this.neckBone) {
      const initNeckRot = this.initialRotations.get(this.neckBone) || new THREE.Euler();
      const targetNeckY = initNeckRot.y + Math.max(-0.25, Math.min(0.25, this.currentLookAt.x * 0.15));
      this.neckBone.rotation.y = THREE.MathUtils.damp(this.neckBone.rotation.y, targetNeckY, 4.0, delta);
    }

    // 4. Smooth Shoulder Breathing Sways
    if (this.leftShoulder) {
      const initRot = this.initialRotations.get(this.leftShoulder) || new THREE.Euler();
      this.leftShoulder.rotation.z = THREE.MathUtils.damp(
        this.leftShoulder.rotation.z,
        initRot.z + breathCycle * 0.01,
        3.0,
        delta
      );
    }
    if (this.rightShoulder) {
      const initRot = this.initialRotations.get(this.rightShoulder) || new THREE.Euler();
      this.rightShoulder.rotation.z = THREE.MathUtils.damp(
        this.rightShoulder.rotation.z,
        initRot.z - breathCycle * 0.01,
        3.0,
        delta
      );
    }
  }
}
