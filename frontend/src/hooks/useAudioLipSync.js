/**
 * useAudioLipSync — connects to the assistant's audio element via Web Audio API
 * and extracts speech-frequency amplitude in real time.
 *
 * Returns a ref (NOT state) containing `mouthOpenness` (0–1) so that the
 * mouth component can read it via rAF without causing React re-renders.
 *
 * The AudioContext is created lazily on first 'play' event to satisfy
 * browser autoplay policies. Cleans up rAF on unmount without closing
 * the shared AudioContext (which would break subsequent playback).
 */
import { useRef, useEffect } from 'react';
import { getOrCreateAnalyser } from '../services/audioAnalyser.js';

export function useAudioLipSync(audioElement) {
  const mouthOpennessRef = useRef(0);
  const analyserRef      = useRef(null);
  const rafRef           = useRef(null);
  const dataArrayRef     = useRef(new Uint8Array(128));

  useEffect(() => {
    if (!audioElement) return;

    const initAnalyser = () => {
      if (analyserRef.current) return; // already initialised
      try {
        const analyser = getOrCreateAnalyser(audioElement);
        if (!analyser) return;
        analyserRef.current = analyser;
        dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount);
      } catch (e) {
        console.warn('[AudioLipSync] AudioContext init failed:', e);
      }
    };

    const tick = () => {
      if (analyserRef.current) {
        analyserRef.current.getByteFrequencyData(dataArrayRef.current);
        // Focus on fundamental speech frequencies (roughly 100–3000 Hz in first 30 bins)
        let sum = 0;
        const bins = Math.min(30, dataArrayRef.current.length);
        for (let i = 2; i < bins; i++) sum += dataArrayRef.current[i];
        const raw = sum / (bins - 2) / 255;
        // Smooth with light lerp
        mouthOpennessRef.current += (raw - mouthOpennessRef.current) * 0.22;
      } else {
        // Decay when no analyser (not yet playing)
        mouthOpennessRef.current *= 0.88;
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    audioElement.addEventListener('play', initAnalyser);
    tick(); // start rAF loop immediately

    return () => {
      audioElement.removeEventListener('play', initAnalyser);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      // Don't close audioCtx — it's reused across playback sessions
    };
  }, [audioElement]);

  return mouthOpennessRef;
}
