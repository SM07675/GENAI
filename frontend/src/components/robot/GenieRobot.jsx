import React, { useRef, useMemo, useEffect } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';
import { useAppStore } from '../../store/appStore.js';
import { useRobotEmotion } from '../../hooks/useRobotEmotion.js';
import { useAudioLipSync } from '../../hooks/useAudioLipSync.js';
import { useCursorTracking } from '../../hooks/useCursorTracking.js';
import EmotionParticles from './EmotionParticles.jsx';

export default function GenieRobot() {
  const containerRef = useRef(null);
  const orbState = useAppStore((s) => s.orbState);
  const assistantAudioElement = useAppStore((s) => s.assistantAudioElement);

  const { emotion } = useRobotEmotion();
  const mouthOpennessRef = useAudioLipSync(assistantAudioElement);
  
  // Use existing hook that returns MotionValues (lookX, lookY)
  const { lookX, lookY } = useCursorTracking(containerRef);

  // Colors based on orbState (listening, thinking, speaking)
  const colors = useMemo(() => {
    switch (orbState) {
      case 'listening': return { bg: '#22d3ee', feature: '#083344' }; // Cyan
      case 'thinking':  return { bg: '#a855f7', feature: '#3b0764' }; // Purple
      case 'speaking':  return { bg: '#ec4899', feature: '#4c0519' }; // Pink
      default:          return { bg: '#e2e8f0', feature: '#334155' }; // Slate (idle)
    }
  }, [orbState]);

  // CSS border-radius blob animation for fluid circle look
  const borderRadius = useMemo(() => {
    switch (orbState) {
      case 'listening':
        return ["40% 60% 70% 30% / 40% 50% 60% 50%", "60% 40% 30% 70% / 60% 30% 70% 40%", "40% 60% 70% 30% / 40% 50% 60% 50%"];
      case 'thinking':
        return ["50% 50% 40% 60% / 50% 60% 40% 50%", "30% 70% 70% 30% / 50% 30% 70% 50%", "50% 50% 40% 60% / 50% 60% 40% 50%"];
      case 'speaking':
        return ["40% 60% 50% 50% / 40% 50% 50% 60%", "60% 40% 50% 50% / 60% 50% 50% 40%", "40% 60% 50% 50% / 40% 50% 50% 60%"];
      default:
        // Idle fluid motion
        return ["45% 55% 45% 55% / 55% 45% 55% 45%", "55% 45% 55% 45% / 45% 55% 45% 55%", "45% 55% 45% 55% / 55% 45% 55% 45%"];
    }
  }, [orbState]);

  // Speaking mouth logic
  const mouthRy = useMotionValue(3);
  const springRy = useSpring(mouthRy, { stiffness: 180, damping: 16 });
  const rafRef = useRef(null);

  useEffect(() => {
    if (orbState !== 'speaking') {
      mouthRy.set(3);
      return;
    }
    const tick = () => {
      const openness = mouthOpennessRef?.current ?? 0;
      mouthRy.set(3 + openness * 20); 
      rafRef.current = requestAnimationFrame(tick);
    };
    tick();
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [orbState, mouthOpennessRef, mouthRy]);

  // Emotion paths for mouth
  const getMouthPath = () => {
    const isSad = emotion === 'sad' || emotion === 'worried';
    const isHappy = ['happy', 'excited', 'loving', 'success'].includes(emotion);
    if (orbState === 'speaking') {
      return "M 15 0 Q 25 5 35 0"; // speaking top lip
    }
    if (isSad) {
      return "M 15 5 Q 25 -5 35 5"; // frown
    }
    if (isHappy) {
      return "M 15 0 Q 25 12 35 0"; // big smile
    }
    // Neutral
    return "M 15 2 Q 25 4 35 2";
  };

  // Bounce animation when happy or excited
  const isBouncy = ['happy', 'excited', 'success'].includes(emotion);

  return (
    <div
      ref={containerRef}
      className="relative flex items-center justify-center p-8 bg-white rounded-[40px] shadow-sm transition-all"
      style={{ width: 220, height: 220, margin: '0 auto', boxShadow: '0 10px 30px rgba(255,255,255,0.05)' }}
    >
      <motion.div
        animate={{
          backgroundColor: colors.bg,
          borderRadius: borderRadius,
          y: isBouncy ? [0, -10, 0, -5, 0] : 0
        }}
        transition={{
          backgroundColor: { duration: 0.6 },
          borderRadius: { duration: 4, repeat: Infinity, ease: 'easeInOut' },
          y: { duration: 0.7, ease: 'easeInOut' }
        }}
        className="relative flex flex-col items-center justify-center shadow-lg"
        style={{ width: 130, height: 130 }}
      >
        {/* Face Wrapper (moves with cursor) */}
        <motion.div
          style={{ x: lookX, y: lookY }}
          className="relative w-full h-full flex flex-col items-center justify-center"
        >
          {/* Eyes */}
          <div className="flex gap-6 mb-2">
            <motion.div
              animate={{ backgroundColor: colors.feature, height: emotion === 'sleepy' ? 4 : 14 }}
              className="w-3.5 rounded-full"
            />
            <motion.div
              animate={{ backgroundColor: colors.feature, height: emotion === 'sleepy' ? 4 : 14 }}
              className="w-3.5 rounded-full"
            />
          </div>

          {/* Mouth */}
          <div className="relative mt-1 flex justify-center" style={{ width: 50, height: 20 }}>
            {orbState === 'speaking' ? (
              <motion.div
                style={{
                  width: 20,
                  height: springRy,
                  backgroundColor: colors.feature,
                  borderRadius: 10,
                  originY: 0
                }}
              />
            ) : emotion === 'surprised' ? (
              <motion.div
                animate={{ width: 12, height: 16, backgroundColor: "transparent", border: `3px solid ${colors.feature}` }}
                className="rounded-full"
              />
            ) : (
              <svg width="50" height="20" viewBox="0 0 50 20" className="overflow-visible">
                <motion.path
                  d={getMouthPath()}
                  initial={false}
                  animate={{ d: getMouthPath(), stroke: colors.feature }}
                  fill="none"
                  strokeWidth="3.5"
                  strokeLinecap="round"
                  transition={{ type: 'spring', stiffness: 200, damping: 20 }}
                />
              </svg>
            )}
          </div>
        </motion.div>
      </motion.div>
      
      {/* Retain emotion particles for added cuteness */}
      <EmotionParticles emotion={emotion} />
    </div>
  );
}
