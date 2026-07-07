// useAudioPlayer: play back base64-encoded MP3 chunks sent from the backend
// (Edge TTS / ElevenLabs output). Maintains a single HTMLAudioElement so
// successive replies queue cleanly without overlap.
import { useCallback, useEffect, useRef } from "react";
import { useAppStore } from "../store/appStore";

export function useAudioPlayer() {
  const audioRef = useRef(null);
  const queueRef = useRef([]);
  const isPlayingRef = useRef(false);
  const setOrbState = useAppStore((s) => s.setOrbState);

  useEffect(() => {
    const el = new Audio();
    el.autoplay = false;
    audioRef.current = el;

    el.onended = () => {
      if (queueRef.current.length > 0) {
        // Pop and play the next chunk
        const nextB64 = queueRef.current.shift();
        el.src = `data:audio/mpeg;base64,${nextB64}`;
        el.play().catch(console.error);
      } else {
        isPlayingRef.current = false;
        setOrbState("idle");
      }
    };

    el.onerror = () => {
      console.error("Audio playback error");
      el.onended(); // skip to next chunk if one fails
    };

    return () => {
      el.pause();
      audioRef.current = null;
    };
  }, [setOrbState]);

  const queueAudioChunk = useCallback((b64) => {
    const el = audioRef.current;
    if (!el) return;
    
    if (!isPlayingRef.current) {
      isPlayingRef.current = true;
      setOrbState("speaking");
      el.src = `data:audio/mpeg;base64,${b64}`;
      el.play().catch((e) => {
        console.error(e);
        el.onended();
      });
    } else {
      queueRef.current.push(b64);
    }
  }, [setOrbState]);
  
  const stopAudio = useCallback(() => {
    queueRef.current = [];
    isPlayingRef.current = false;
    if (audioRef.current) {
      audioRef.current.pause();
    }
    setOrbState("idle");
  }, [setOrbState]);

  return { queueAudioChunk, stopAudio };
}
