/**
 * emotionController — centralized, priority-based emotion state machine.
 *
 * Priority order (higher = wins):
 *   error/worried(100) > listening(90) > speaking(80) > thinking(70)
 *   > surprised(55) > excited(50) > loving(47) > success(45) > happy(40)
 *   > sad(38) > confused(35) > sleepy(20) > neutral(10) > idle(0)
 *
 * Temporary emotions auto-return to the appropriate baseline after `duration` ms.
 * Force-source ('system_force') always overrides regardless of priority.
 */
import { useAppStore } from '../store/appStore.js';
import { ROBOT_EMOTIONS } from '../types/robotEmotion.js';

const EMOTION_PRIORITY = {
  [ROBOT_EMOTIONS.WORRIED]:   100,
  [ROBOT_EMOTIONS.LISTENING]:  90,
  [ROBOT_EMOTIONS.SPEAKING]:   80,
  [ROBOT_EMOTIONS.THINKING]:   70,
  [ROBOT_EMOTIONS.SURPRISED]:  55,
  [ROBOT_EMOTIONS.EXCITED]:    50,
  [ROBOT_EMOTIONS.LOVING]:     47,
  [ROBOT_EMOTIONS.SUCCESS]:    45,
  [ROBOT_EMOTIONS.HAPPY]:      40,
  [ROBOT_EMOTIONS.SAD]:        38,
  [ROBOT_EMOTIONS.CONFUSED]:   35,
  [ROBOT_EMOTIONS.SLEEPY]:     20,
  [ROBOT_EMOTIONS.NEUTRAL]:    10,
  [ROBOT_EMOTIONS.IDLE]:        0,
};

let returnTimerId = null;

/**
 * Set the robot's emotion with priority checking.
 * @param {{ emotion: string, intensity?: number, duration?: number, source?: string }} cmd
 */
export function setRobotEmotion({ emotion, intensity = 1.0, duration = 0, source = 'system' }) {
  const current = useAppStore.getState().robotEmotion;
  const currentPri = EMOTION_PRIORITY[current?.emotion] ?? 0;
  const newPri     = EMOTION_PRIORITY[emotion] ?? 0;

  // 'system_force' always overrides (used for orbState transitions).
  // Otherwise, a lower-priority emotion can't override a higher one.
  if (source !== 'system_force' && newPri < currentPri) return;

  // Cancel any pending auto-return timer
  if (returnTimerId) {
    clearTimeout(returnTimerId);
    returnTimerId = null;
  }

  useAppStore.setState({ robotEmotion: { emotion, intensity, source } });

  // Schedule auto-return to baseline if a duration is given
  if (duration > 0) {
    returnTimerId = setTimeout(returnToBaseline, duration);
  }
}

/**
 * Return to the correct baseline emotion based on the current orb state.
 * Called automatically after a temporary emotion expires.
 */
export function returnToBaseline() {
  const { genieState } = useAppStore.getState();
  let baseEmotion = ROBOT_EMOTIONS.NEUTRAL;
  if (genieState === 'speaking')  baseEmotion = ROBOT_EMOTIONS.SPEAKING;
  else if (genieState === 'listening' || genieState === 'transcribing') baseEmotion = ROBOT_EMOTIONS.LISTENING;
  else if (genieState === 'thinking')  baseEmotion = ROBOT_EMOTIONS.THINKING;
  else if (genieState === 'sleeping')  baseEmotion = ROBOT_EMOTIONS.SLEEPY;

  useAppStore.setState({
    robotEmotion: { emotion: baseEmotion, intensity: 1.0, source: 'baseline' },
  });
}
