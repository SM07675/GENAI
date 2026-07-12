// useAudioPlayer: play back base64-encoded audio chunks sent from the backend
// (Edge/ElevenLabs MP3 or Gemini Live WAV).
//
// Architecture:
// - Uses a ref for isPlaying (not state) to avoid stale-closure bugs
// - Exposes isPlayingRef.current for external checks
// - Validates base64 audio has minimum viable size before attempting play
// - Uses Blob URLs instead of data: URIs to avoid Chrome/Electron CORS issues
import { useCallback, useEffect, useRef } from "react";
import { useAppStore } from "../store/appStore";

// Minimum base64 length for a valid MP3 frame (~100 bytes encoded)
const MIN_AUDIO_B64_LENGTH = 100;

export function useAudioPlayer() {
  const audioRef = useRef(null);
  const queueRef = useRef([]);          // [{blobUrl, seq}]
  const isPlayingRef = useRef(false);
  const setOrbState = useAppStore((s) => s.setOrbState);

  // Convert base64 audio to a Blob URL — avoids the data: URI CORS issue
  // that causes "[AudioPlayer] Audio error" in Chrome/Electron.
  const createBlobUrl = useCallback((base64, mime) => {
    try {
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: mime });
      return URL.createObjectURL(blob);
    } catch (e) {
      console.error("[AudioPlayer] Failed to create blob URL:", e);
      return null;
    }
  }, []);

  useEffect(() => {
    const el = new Audio();
    el.autoplay = false;
    audioRef.current = el;
    useAppStore.getState().setAssistantAudioElement(el);

    const playNext = () => {
      if (queueRef.current.length > 0) {
        const next = queueRef.current.shift();
        el.src = next.blobUrl;
        el.play().catch((e) => {
          console.warn("[AudioPlayer] play() rejected:", e);
          URL.revokeObjectURL(next.blobUrl);
          playNext(); // skip to next chunk
        });
      } else {
        isPlayingRef.current = false;
        setOrbState("idle");
      }
    };

    el.onended = () => {
      // Revoke the old blob URL to free memory
      if (el.src && el.src.startsWith("blob:")) {
        URL.revokeObjectURL(el.src);
      }
      playNext();
    };

    el.onerror = () => {
      console.warn("[AudioPlayer] Audio element error — skipping chunk");
      if (el.src && el.src.startsWith("blob:")) {
        URL.revokeObjectURL(el.src);
      }
      playNext();
    };

    return () => {
      el.pause();
      el.src = "";
      // Clean up any remaining queued blob URLs
      queueRef.current.forEach((item) => URL.revokeObjectURL(item.blobUrl));
      queueRef.current = [];
      audioRef.current = null;
    };
  }, [setOrbState]);

  const queueAudioChunk = useCallback((audio, mime = "audio/mpeg", seq = 0) => {
    const el = audioRef.current;
    if (!el || !audio || audio.length < MIN_AUDIO_B64_LENGTH) return;

    const blobUrl = createBlobUrl(audio, mime);
    if (!blobUrl) return;

    if (!isPlayingRef.current) {
      // First chunk — start playing immediately
      isPlayingRef.current = true;
      setOrbState("speaking");
      el.src = blobUrl;
      el.play().catch((e) => {
        console.warn("[AudioPlayer] Initial play() rejected:", e);
        URL.revokeObjectURL(blobUrl);
        isPlayingRef.current = false;
        setOrbState("idle");
      });
    } else {
      // Already playing — queue for gapless sequential playback
      queueRef.current.push({ blobUrl, seq });
    }
  }, [setOrbState, createBlobUrl]);

  const stopAudio = useCallback(() => {
    // Clean up all queued blob URLs
    queueRef.current.forEach((item) => URL.revokeObjectURL(item.blobUrl));
    queueRef.current = [];
    isPlayingRef.current = false;
    if (audioRef.current) {
      if (audioRef.current.src && audioRef.current.src.startsWith("blob:")) {
        URL.revokeObjectURL(audioRef.current.src);
      }
      audioRef.current.pause();
      audioRef.current.src = "";
    }
    setOrbState("idle");
  }, [setOrbState]);

  // Expose isPlayingRef so callers can check .current (boolean)
  return { queueAudioChunk, stopAudio, isPlaying: isPlayingRef };
}
