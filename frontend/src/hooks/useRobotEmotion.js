/**
 * useRobotEmotion — React hook that reads the current robot emotion from the
 * Zustand store and exposes the setRobotEmotion controller helper.
 */
import { useAppStore } from '../store/appStore.js';
import { setRobotEmotion } from '../services/emotionController.js';

export function useRobotEmotion() {
  const robotEmotion = useAppStore((s) => s.robotEmotion);
  return {
    emotion:    robotEmotion?.emotion   ?? 'neutral',
    intensity:  robotEmotion?.intensity ?? 1.0,
    source:     robotEmotion?.source    ?? 'idle',
    setEmotion: setRobotEmotion,
  };
}
