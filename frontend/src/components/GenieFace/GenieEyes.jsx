import React, { useEffect, useState } from 'react';
import { motion, useAnimation } from 'framer-motion';

export default function GenieEyes({ emotion, lookX, lookY }) {
  const isSleeping = emotion === 'sleeping';
  
  // Blinking logic
  const leftEyelidCtrl = useAnimation();
  const rightEyelidCtrl = useAnimation();

  useEffect(() => {
    if (isSleeping) return;

    let timeoutId;
    const blink = async () => {
      // Natural blink is about 150ms down, 150ms up
      leftEyelidCtrl.start({ scaleY: 1, transition: { duration: 0.15 } });
      await rightEyelidCtrl.start({ scaleY: 1, transition: { duration: 0.15 } });
      
      leftEyelidCtrl.start({ scaleY: 0, transition: { duration: 0.15 } });
      await rightEyelidCtrl.start({ scaleY: 0, transition: { duration: 0.15 } });

      const nextBlink = Math.random() * 4000 + 2000; // 2 to 6 seconds
      timeoutId = setTimeout(blink, nextBlink);
    };

    timeoutId = setTimeout(blink, 3000);
    return () => clearTimeout(timeoutId);
  }, [isSleeping, leftEyelidCtrl, rightEyelidCtrl]);

  // Handle specific emotional eye states
  const getEyeTransform = (isLeft) => {
    let y = 0;
    let scaleY = 1;
    let scaleX = 1;
    
    if (emotion === 'thinking') {
      y = -6; // Look up
    } else if (emotion === 'sad') {
      y = 4; // Look down
    } else if (emotion === 'excited' || emotion === 'waking' || emotion === 'surprised') {
      scaleY = 1.1; // Wide eyes
      scaleX = 1.05;
    } else if (emotion === 'confused' && isLeft) {
      scaleY = 0.8; // One eye smaller
      scaleX = 0.8;
    }
    
    return { y, scaleX, scaleY };
  };

  const getEyelidState = () => {
    if (isSleeping) return 1; // Fully closed
    if (emotion === 'happy') return 0.2; // Slightly squinted
    return 0; // Fully open
  };

  const getEyebrowTransform = (isLeft) => {
    let y = -10;
    let rotate = 0;
    let opacity = 0.8;

    if (isSleeping) {
      y = -5;
      opacity = 0; // Hide when sleeping
    } else if (emotion === 'waking' || emotion === 'surprised') {
      y = -18; // Raised
    } else if (emotion === 'sad') {
      y = -12;
      rotate = isLeft ? 15 : -15; // Inner brows up
    } else if (emotion === 'confused') {
      y = isLeft ? -18 : -10; // One raised
    } else if (emotion === 'happy' || emotion === 'excited') {
      y = -14;
    }

    return { y, rotate, opacity };
  };

  return (
    <div className="flex gap-[30px] relative z-10 mt-[-10px]">
      {/* Left Eye */}
      <div className="relative flex flex-col items-center">
        {/* Eyebrow */}
        <motion.div
          animate={getEyebrowTransform(true)}
          transition={{ type: 'spring', stiffness: 200, damping: 20 }}
          className="absolute w-6 h-[4px] bg-[#334155] rounded-full z-20"
        />
        
        {/* Eye body */}
        <motion.div
          style={{ x: lookX, y: lookY }}
          animate={getEyeTransform(true)}
          transition={{ type: 'spring', stiffness: 200, damping: 20 }}
          className="genie-eye shadow-sm"
        >
          {/* Eyelid */}
          <motion.div
            initial={{ scaleY: 1 }}
            animate={leftEyelidCtrl}
            style={{ scaleY: getEyelidState() }}
            className="genie-eyelid"
          />
        </motion.div>
      </div>

      {/* Right Eye */}
      <div className="relative flex flex-col items-center">
        {/* Eyebrow */}
        <motion.div
          animate={getEyebrowTransform(false)}
          transition={{ type: 'spring', stiffness: 200, damping: 20 }}
          className="absolute w-6 h-[4px] bg-[#334155] rounded-full z-20"
        />
        
        {/* Eye body */}
        <motion.div
          style={{ x: lookX, y: lookY }}
          animate={getEyeTransform(false)}
          transition={{ type: 'spring', stiffness: 200, damping: 20 }}
          className="genie-eye shadow-sm"
        >
          {/* Eyelid */}
          <motion.div
            initial={{ scaleY: 1 }}
            animate={rightEyelidCtrl}
            style={{ scaleY: getEyelidState() }}
            className="genie-eyelid"
          />
        </motion.div>
      </div>
    </div>
  );
}
