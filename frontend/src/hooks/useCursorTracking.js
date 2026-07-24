/**
 * useCursorTracking — tracks the mouse position relative to the robot face
 * center and returns smooth Framer Motion MotionValues for eye pupil offsets.
 *
 * Uses useMotionValue + useSpring so updates bypass the React render cycle
 * entirely — zero re-renders, smooth 60fps tracking.
 *
 * Max offsets: ±4px horizontal, ±2px vertical (very subtle).
 */
import { useEffect } from 'react';
import { useMotionValue, useSpring } from 'framer-motion';

export function useCursorTracking(containerRef) {
  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);

  // Spring config: soft and natural, not snappy
  const lookX = useSpring(rawX, { stiffness: 55, damping: 14 });
  const lookY = useSpring(rawY, { stiffness: 55, damping: 14 });

  useEffect(() => {
    const handleMouseMove = (e) => {
      const el = containerRef?.current;
      if (!el) return;

      const rect = el.getBoundingClientRect();
      const centerX = rect.left + rect.width  / 2;
      const centerY = rect.top  + rect.height / 2;

      // Normalise to [-1, 1] based on container half-size
      const dx = (e.clientX - centerX) / Math.max(rect.width  / 2, 1);
      const dy = (e.clientY - centerY) / Math.max(rect.height / 2, 1);

      rawX.set(Math.max(-1, Math.min(1, dx)) * 4); // ±4px
      rawY.set(Math.max(-1, Math.min(1, dy)) * 2); // ±2px
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [containerRef, rawX, rawY]);

  // Return MotionValues — apply to SVG elements via style={{ x: lookX, y: lookY }}
  return { lookX, lookY };
}
