/**
 * useBlinkAnimation — drives natural eye-blinking for the Genie robot.
 *
 * - Blinks every 3–7 seconds (random interval)
 * - Occasionally performs a double-blink (every 5th blink)
 * - Returns `blinkTarget` (1.0 = open, 0.05 = closed)
 *   which components use as the `scaleY` animate target
 * - Can be disabled (e.g. for the sleepy state where eyes are half-closed)
 */
import { useState, useEffect, useRef, useCallback } from 'react';

export function useBlinkAnimation({ disabled = false } = {}) {
  const [blinkTarget, setBlinkTarget] = useState(1.0);
  const timerRef      = useRef(null);
  const isMounted     = useRef(true);
  const blinkCount    = useRef(0);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const scheduleNextBlink = useCallback(() => {
    if (!isMounted.current || disabled) return;
    const delay = 3000 + Math.random() * 4000; // 3–7 s
    timerRef.current = setTimeout(doBlink, delay);
  }, [disabled]); // eslint-disable-line react-hooks/exhaustive-deps

  const doBlink = useCallback(() => {
    if (!isMounted.current || disabled) return;

    const close = () => {
      if (!isMounted.current) return;
      setBlinkTarget(0.05);
    };
    const open = (cb) => {
      if (!isMounted.current) return;
      timerRef.current = setTimeout(() => {
        if (!isMounted.current) return;
        setBlinkTarget(1.0);
        if (cb) cb();
      }, 90);
    };

    close();
    open(() => {
      blinkCount.current++;
      const doDouble = blinkCount.current % 5 === 0;
      if (doDouble) {
        // Short pause then blink again
        timerRef.current = setTimeout(() => {
          if (!isMounted.current) return;
          close();
          open(scheduleNextBlink);
        }, 200);
      } else {
        scheduleNextBlink();
      }
    });
  }, [disabled, scheduleNextBlink]);

  useEffect(() => {
    isMounted.current = true;
    if (!disabled) scheduleNextBlink();
    return () => {
      isMounted.current = false;
      clearTimer();
    };
  }, [disabled, scheduleNextBlink, clearTimer]);

  return { blinkTarget }; // 1.0 = fully open, 0.05 = fully closed
}
