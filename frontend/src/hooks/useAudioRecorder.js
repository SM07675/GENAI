// useAudioRecorder: capture microphone audio and stream it as binary frames.
// Uses the Web Audio API to also expose a live amplitude value the orb can
// react to (for the "sound wave" visualization).
import { useCallback, useEffect, useRef, useState } from "react";
import { useAppStore } from "../store/appStore";

export function useAudioRecorder({ onChunk, sampleMs = 100 } = {}) {
  const [recording, setRecording] = useState(false);
  const setAmplitude = useAppStore((s) => s.setAmplitude);  // publish to store for the orb
  const mediaRef = useRef(null);                   // MediaRecorder
  const streamRef = useRef(null);                  // MediaStream
  const analyserRef = useRef(null);                // AnalyserNode
  const rafRef = useRef(null);                     // animation frame id
  const onChunkRef = useRef(onChunk);
  onChunkRef.current = onChunk;

  // Poll the analyser for amplitude (drives the orb's wave ring).
  const tick = useCallback(() => {
    const analyser = analyserRef.current;
    if (analyser) {
      const data = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteTimeDomainData(data);
      // RMS-ish amplitude normalized to 0..1.
      let sum = 0;
      for (let i = 0; i < data.length; i++) {
        const v = (data[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / data.length);
      setAmplitude(Math.min(1, rms * 3));
    }
    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const start = useCallback(async () => {
    if (mediaRef.current) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;

      // Wire an analyser so the orb can react to mic input in real time.
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      analyserRef.current = analyser;
      rafRef.current = requestAnimationFrame(tick);

      // MediaRecorder -> small chunks -> WS as binary frames.
      const mr = new MediaRecorder(stream, { mimeType: pickMime() });
      mr.ondataavailable = (e) => {
        if (e.data && e.data.size > 0 && onChunkRef.current) {
          e.data.arrayBuffer().then((buf) => onChunkRef.current(new Uint8Array(buf)));
        }
      };
      mr.start(sampleMs);
      mediaRef.current = mr;
      setRecording(true);
    } catch (err) {
      console.error("Mic access failed:", err);
      setRecording(false);
    }
  }, [sampleMs, tick]);

  const stop = useCallback(() => {
    const mr = mediaRef.current;
    if (mr && mr.state !== "inactive") mr.stop();
    mediaRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    analyserRef.current = null;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    setRecording(false);
    setAmplitude(0);
  }, []);

  useEffect(() => () => stop(), [stop]);

  return { recording, start, stop };
}

function pickMime() {
  // Prefer webm/opus (faster-whisper decodes it via ffmpeg). Fall back gracefully.
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  for (const c of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(c)) {
      return c;
    }
  }
  return "";
}
