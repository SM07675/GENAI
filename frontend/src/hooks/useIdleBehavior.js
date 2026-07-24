/**
 * useIdleBehavior — fires subtle micro-animations every 8–15 seconds
 * when the robot is idle. Each action lasts ~1.5 s then resets to null.
 *
 * Actions: 'lookLeft' | 'lookRight' | 'lookUp' | 'tiltLeft' | 'tiltRight'
 *          | 'smile' | 'cheekPulse' | 'earWiggle'
 *
 * Also manages the sleepy state: if the robot stays idle for > 30 seconds
 * with no user interaction, it transitions to 'sleepy'. Wakes immediately on
 * mouse movement, keydown, or touch.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { setRobotEmotion } from '../services/emotionController.js';
import { ROBOT_EMOTIONS } from '../types/robotEmotion.js';

const IDLE_ACTIONS = [
  'lookLeft', 'lookRight', 'lookUp',
  'tiltLeft', 'tiltRight',
  'smile', 'cheekPulse', 'earWiggle',
];

export function useIdleBehavior({ active = true } = {}) {
  const [idleAction, setIdleAction] = useState(null);
  const timerRef      = useRef(null);
  const sleepTimerRef = useRef(null);
  const isMounted     = useRef(true);
  const isSleepy      = useRef(false);

  const wake = useCallback(() => {
    if (!isSleepy.current) return;
    isSleepy.current = false;
    setRobotEmotion({ emotion: ROBOT_EMOTIONS.NEUTRAL, intensity: 1.0, source: 'system_force' });
  }, []);

  const scheduleSleep = useCallback(() => {
    if (sleepTimerRef.current) clearTimeout(sleepTimerRef.current);
    sleepTimerRef.current = setTimeout(() => {
      if (!isMounted.current || !active) return;
      isSleepy.current = true;
      setRobotEmotion({ emotion: ROBOT_EMOTIONS.SLEEPY, intensity: 1.0, source: 'idle_timeout' });
    }, 30_000);
  }, [active]);

  const scheduleNextAction = useCallback(() => {
    if (!isMounted.current || !active) return;
    const delay = 8000 + Math.random() * 7000; // 8–15 s
    timerRef.current = setTimeout(() => {
      if (!isMounted.current || !active) return;
      const action = IDLE_ACTIONS[Math.floor(Math.random() * IDLE_ACTIONS.length)];
      setIdleAction(action);
      setTimeout(() => {
        if (isMounted.current) setIdleAction(null);
      }, 1500);
      scheduleNextAction();
    }, delay);
  }, [active]);

  // Clear and restart idle/sleep timers on user activity
  const handleActivity = useCallback(() => {
    wake();
    scheduleSleep();
  }, [wake, scheduleSleep]);

  useEffect(() => {
    isMounted.current = true;

    if (active) {
      scheduleNextAction();
      scheduleSleep();
    }

    const events = ['mousemove', 'keydown', 'touchstart', 'mousedown'];
    events.forEach((e) => window.addEventListener(e, handleActivity, { passive: true }));

    return () => {
      isMounted.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
      if (sleepTimerRef.current) clearTimeout(sleepTimerRef.current);
      events.forEach((e) => window.removeEventListener(e, handleActivity));
    };
  }, [active, scheduleNextAction, scheduleSleep, handleActivity]);

  return { idleAction };
}
