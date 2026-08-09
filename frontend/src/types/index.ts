export type AssistantState = 
  | 'idle'
  | 'sleeping'
  | 'waking'
  | 'listening'
  | 'recording'
  | 'processing'
  | 'thinking'
  | 'speaking'
  | 'muted'
  | 'error'
  | 'success';

export type StandardAnimationName = 
  | 'Idle'
  | 'Walk'
  | 'Run'
  | 'Thinking'
  | 'Talking'
  | 'Listening'
  | 'Greeting'
  | 'Celebrate'
  | 'Dance'
  | 'Sleep'
  | 'Wake'
  | 'Waiting'
  | 'Talk_Standing'
  | 'Talk_Sitting'
  | 'SneakWalk';

export type AnimationName = StandardAnimationName | string;

export interface SettingsConfig {
  particleDensity: number;
  glowIntensity: number;
  cameraSpeed: number;
  audioSens: number;
  bloomEnabled: boolean;
  volume: number;
  autoRotate: boolean;
}

export interface AssistantServiceListener {
  onStateChange?: (state: AssistantState) => void;
  onAudioLevel?: (level: number) => void;
  onTranscript?: (text: string) => void;
}
