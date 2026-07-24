/**
 * All valid robot emotion states.
 * @typedef {'idle'|'neutral'|'listening'|'thinking'|'speaking'|'happy'|'excited'|'loving'|'sad'|'confused'|'surprised'|'worried'|'sleepy'|'success'} RobotEmotion
 */

export const ROBOT_EMOTIONS = {
  IDLE:      'idle',
  NEUTRAL:   'neutral',
  LISTENING: 'listening',
  THINKING:  'thinking',
  SPEAKING:  'speaking',
  HAPPY:     'happy',
  EXCITED:   'excited',
  LOVING:    'loving',
  SAD:       'sad',
  CONFUSED:  'confused',
  SURPRISED: 'surprised',
  WORRIED:   'worried',
  SLEEPY:    'sleepy',
  SUCCESS:   'success',
};

/**
 * @typedef {{ emotion: RobotEmotion, intensity: number, duration: number, source: string }} EmotionCommand
 */
