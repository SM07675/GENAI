import { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { useAnimations } from '@react-three/drei';
import { AssistantState } from '../types';
import { DEFAULT_STATE_MAPPINGS, DEFAULT_CROSSFADE_DURATION } from '../animation/AnimationState';
import { mapStateToClipName } from '../utils/animationUtils';

export interface UseAnimationManagerReturn {
  availableClips: string[];
  activeClipName: string | null;
  playAnimation: (clipOrStateName: string, duration?: number) => void;
  actions: Record<string, THREE.AnimationAction | null>;
}

/**
 * Central Animation Controller for Genie.
 * Manages 3D character animation transitions, crossfading, state priority, and idle variation.
 */
export function useAnimationManager(
  animations: THREE.AnimationClip[],
  groupRef: React.RefObject<THREE.Group>,
  assistantState: AssistantState | string
): UseAnimationManagerReturn {
  const { actions, names } = useAnimations(animations, groupRef);
  const [activeClipName, setActiveClipName] = useState<string | null>(null);
  const currentActionRef = useRef<THREE.AnimationAction | null>(null);
  const currentClipNameRef = useRef<string | null>(null);

  const availableClips = names;

  const playAnimation = useCallback(
    (targetName: string, duration: number = DEFAULT_CROSSFADE_DURATION) => {
      if (!names || names.length === 0) return;

      const clipToPlay = mapStateToClipName(targetName, names);
      if (!clipToPlay || !actions[clipToPlay]) return;

      const nextAction = actions[clipToPlay];
      if (!nextAction) return;

      // Prevent restarting the exact same animation if already running cleanly
      if (currentActionRef.current === nextAction && nextAction.isRunning()) {
        return;
      }

      nextAction.reset();
      nextAction.setEffectiveTimeScale(1);
      nextAction.setEffectiveWeight(1);
      nextAction.play();

      if (currentActionRef.current && currentActionRef.current !== nextAction) {
        currentActionRef.current.crossFadeTo(nextAction, duration, true);
      }

      currentActionRef.current = nextAction;
      currentClipNameRef.current = clipToPlay;
      setActiveClipName(clipToPlay);
    },
    [actions, names]
  );

  // Synchronize 3D model animation with AssistantState
  useEffect(() => {
    const stateKey = String(assistantState).toLowerCase();
    const mappedTarget = DEFAULT_STATE_MAPPINGS[stateKey] || DEFAULT_STATE_MAPPINGS['idle'] || 'Idle';

    console.log(`[AnimationController] State change: '${assistantState}' -> target clip: '${mappedTarget}'`);
    playAnimation(mappedTarget);
  }, [assistantState, playAnimation]);

  return {
    availableClips,
    activeClipName,
    playAnimation,
    actions,
  };
}
