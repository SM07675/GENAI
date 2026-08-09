import { AssistantState } from '../types';

export interface StateAnimationConfig {
  assistantState: string;
  preferredAnimation: string;
  crossfadeDuration: number;
  priority: number;
}

export const ANIMATION_PRIORITIES: Record<string, number> = {
  error: 100,
  success: 90,
  speaking: 80,
  processing: 70,
  recording: 60,
  listening: 50,
  waking: 40,
  idle: 10,
  muted: 10,
};

export const DEFAULT_STATE_MAPPINGS: Record<string, string> = {
  idle: 'Idle',
  listening: 'Idle',
  recording: 'Idle',
  processing: 'Talk_Sitting',
  speaking: 'Talk_Standing',
  muted: 'Idle',
  error: 'SneakWalk',
  success: 'Dance',
  waking: 'Idle',
};

export const DEFAULT_CROSSFADE_DURATION = 0.4;
