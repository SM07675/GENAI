import React, { useEffect, useRef } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import { useAudioLipSync } from '../../hooks/useAudioLipSync';

export default function GenieMouth({ emotion, isSpeaking }) {
  const assistantAudioElement = useAppStore((s) => s.assistantAudioElement);
  const opennessRef = useAudioLipSync(assistantAudioElement);
  
  const mouthRy = useMotionValue(3);
  const springRy = useSpring(mouthRy, { stiffness: 200, damping: 15 });
  const rafRef = useRef(null);

  useEffect(() => {
    if (!isSpeaking) {
      mouthRy.set(3);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      return;
    }
    const tick = () => {
      const openness = opennessRef?.current ?? 0;
      mouthRy.set(3 + openness * 22);
      rafRef.current = requestAnimationFrame(tick);
    };
    tick();
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [isSpeaking, opennessRef, mouthRy]);

  const getMouthPath = () => {
    switch (emotion) {
      case 'sleeping': return "M 15 10 Q 25 14 35 10"; // peaceful small smile
      case 'happy': 
      case 'excited': 
      case 'waking': return "M 10 5 Q 25 22 40 5"; // wide smile
      case 'sad': return "M 15 15 Q 25 8 35 15"; // frown
      case 'surprised': return "M 25 5 A 4 4 0 1 0 25 15 A 4 4 0 1 0 25 5"; // O shape
      case 'confused': return "M 15 12 Q 25 8 35 15"; // tilted mouth
      case 'thinking': return "M 20 12 Q 25 10 30 12"; // small curved thinking
      case 'error': return "M 15 15 Q 25 13 35 15"; // concerned
      case 'idle':
      case 'listening':
      default: return "M 15 8 Q 25 14 35 8"; // small happy curve
    }
  };

  return (
    <div className="relative flex justify-center items-center mt-3" style={{ width: 50, height: 25 }}>
      {isSpeaking ? (
        <motion.div
          style={{
            width: 24,
            height: springRy,
            backgroundColor: "#07142f",
            borderRadius: 12,
            originY: 0.5
          }}
        />
      ) : (
        <svg width="50" height="25" viewBox="0 0 50 25" className="overflow-visible absolute">
          <motion.path
            d={getMouthPath()}
            initial={false}
            animate={{ d: getMouthPath() }}
            fill="none"
            stroke="#07142f"
            strokeWidth="3.5"
            strokeLinecap="round"
            transition={{ type: 'spring', stiffness: 200, damping: 20 }}
          />
        </svg>
      )}
    </div>
  );
}
