/**
 * AudioWaveform — compact bar-based audio waveform shown below the robot
 * while Genie is speaking. Uses the same assistantAudioElement analyser
 * data, sampled via rAF and displayed as 12 Framer Motion bars.
 *
 * Only rendered when orbState === 'speaking'.
 */
import React, { useRef, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../store/appStore.js';
import { getOrCreateAnalyser } from '../services/audioAnalyser.js';

const BAR_COUNT  = 12;
const BAR_WIDTH  = 3;
const BAR_GAP    = 4;
const MAX_HEIGHT = 28;
const MIN_HEIGHT = 3;

function WaveformBars() {
  const assistantAudioElement = useAppStore((s) => s.assistantAudioElement);
  const [heights, setHeights] = useState(Array(BAR_COUNT).fill(MIN_HEIGHT));
  const analyserRef   = useRef(null);
  const rafRef        = useRef(null);
  const dataRef       = useRef(new Uint8Array(256));

  useEffect(() => {
    if (!assistantAudioElement) return;

    const init = () => {
      if (analyserRef.current) return;
      try {
        const analyser = getOrCreateAnalyser(assistantAudioElement);
        if (!analyser) return;
        analyserRef.current = analyser;
        dataRef.current = new Uint8Array(analyser.frequencyBinCount);
      } catch (e) {
        console.warn('[AudioWaveform] AudioContext init failed:', e);
      }
    };

    assistantAudioElement.addEventListener('play', init);

    const tick = () => {
      if (analyserRef.current) {
        analyserRef.current.getByteFrequencyData(dataRef.current);
        const bucketSize = Math.floor(dataRef.current.length / BAR_COUNT);
        const newHeights = Array.from({ length: BAR_COUNT }, (_, i) => {
          let sum = 0;
          for (let j = 0; j < bucketSize; j++) {
            sum += dataRef.current[i * bucketSize + j];
          }
          const avg = sum / bucketSize / 255;
          return MIN_HEIGHT + avg * (MAX_HEIGHT - MIN_HEIGHT);
        });
        setHeights(newHeights);
      } else {
        setHeights(Array(BAR_COUNT).fill(MIN_HEIGHT));
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    tick();

    return () => {
      assistantAudioElement.removeEventListener('play', init);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [assistantAudioElement]);

  const totalWidth = BAR_COUNT * BAR_WIDTH + (BAR_COUNT - 1) * BAR_GAP;

  return (
    <svg
      width={totalWidth}
      height={MAX_HEIGHT + 4}
      viewBox={`0 0 ${totalWidth} ${MAX_HEIGHT + 4}`}
      style={{ display: 'block' }}
    >
      {heights.map((h, i) => (
        <rect
          key={i}
          x={i * (BAR_WIDTH + BAR_GAP)}
          y={(MAX_HEIGHT - h) / 2}
          width={BAR_WIDTH}
          height={h}
          rx={1.5}
          fill="#ec4899"
          opacity={0.75}
          style={{
            filter: `drop-shadow(0 0 2px #ec4899)`,
            transition: 'height 90ms ease-out, y 90ms ease-out',
          }}
        />
      ))}
    </svg>
  );
}

export default function AudioWaveform() {
  const orbState = useAppStore((s) => s.orbState);

  return (
    <AnimatePresence>
      {orbState === 'speaking' && (
        <motion.div
          key="waveform"
          className="flex justify-center mt-1"
          initial={{ opacity: 0, scaleY: 0.3 }}
          animate={{ opacity: 1, scaleY: 1 }}
          exit={{ opacity: 0, scaleY: 0.3 }}
          transition={{ type: 'spring', stiffness: 300, damping: 22 }}
          style={{ transformOrigin: 'bottom' }}
        >
          <WaveformBars />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
