/**
 * VoiceWaveform.tsx — Audio waveform visualizer for companion mode.
 * Shows animated bars that react to audio amplitude.
 */
import React, { useRef, useEffect, useState } from 'react';
import { motion } from 'framer-motion';

interface VoiceWaveformProps {
  isActive: boolean;       // is mic capturing or TTS playing?
  color?: string;
  bars?: number;
  height?: number;
  width?: number;
}

export default function VoiceWaveform({
  isActive,
  color = '#22D3EE',
  bars = 16,
  height = 40,
  width = 120,
}: VoiceWaveformProps) {
  const [amplitudes, setAmplitudes] = useState<number[]>(() => Array(bars).fill(0.1));
  const animRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isActive) {
      setAmplitudes(Array(bars).fill(0.08));
      return;
    }

    // Simulate organic waveform (real connection via AudioAnalyser would be wired here)
    const animate = () => {
      setAmplitudes(prev =>
        prev.map((v, i) => {
          const target = 0.1 + Math.random() * 0.9;
          return v + (target - v) * 0.25;
        })
      );
      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [isActive, bars]);

  const barW = Math.floor((width - (bars - 1) * 2) / bars);
  const maxH = height;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        width,
        height: maxH,
      }}
    >
      {amplitudes.map((amp, i) => (
        <motion.div
          key={i}
          style={{
            width: barW,
            minHeight: 3,
            borderRadius: barW,
            background: isActive
              ? `linear-gradient(180deg, ${color}ff, ${color}44)`
              : `${color}33`,
            boxShadow: isActive && amp > 0.6 ? `0 0 6px ${color}88` : 'none',
            willChange: 'height',
          }}
          animate={{ height: Math.max(3, amp * maxH) }}
          transition={{ duration: 0.08 }}
        />
      ))}
    </div>
  );
}
