/**
 * CameraCompanion.tsx — Real-time camera vision feed & control UI.
 *
 * Allows Genie to see through the user's camera (webcam or mobile camera).
 * Features:
 * - Privacy indicator & toggle (video feed requires explicit user activation)
 * - Canvas frame capture sending JPEG frames over WebSocket (`camera_frame`)
 * - Adaptive capture rate (e.g. 1 frame every 3–5 seconds to optimize bandwidth)
 * - Mirror toggle / Device selection
 */
import React, { useRef, useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import { useCompanionStore } from '../../store/companionStore';

interface CameraCompanionProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function CameraCompanion({ isOpen, onClose }: CameraCompanionProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isCapturing, setIsCapturing] = useState(false);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');

  const ws = useAppStore((s) => s.ws);
  const setPrivacy = useCompanionStore((s) => s.setPrivacy);
  const screenAware = useCompanionStore((s) => s.screenAware);
  const micActive = useCompanionStore((s) => s.micActive);

  // Enumerate cameras
  useEffect(() => {
    navigator.mediaDevices?.enumerateDevices().then((devs) => {
      const cams = devs.filter((d) => d.kind === 'videoinput');
      setDevices(cams);
      if (cams.length > 0 && !selectedDeviceId) {
        setSelectedDeviceId(cams[0].deviceId);
      }
    }).catch(() => {});
  }, [selectedDeviceId]);

  // Start video stream when component opens
  useEffect(() => {
    if (!isOpen) {
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
        setStream(null);
      }
      setPrivacy(screenAware, micActive, false);
      return;
    }

    let isMounted = true;
    async function startCamera() {
      try {
        setError(null);
        const constraints: MediaStreamConstraints = {
          video: selectedDeviceId
            ? { deviceId: { exact: selectedDeviceId }, width: { ideal: 640 }, height: { ideal: 480 } }
            : { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
        };
        const s = await navigator.mediaDevices.getUserMedia(constraints);
        if (isMounted) {
          setStream(s);
          if (videoRef.current) {
            videoRef.current.srcObject = s;
          }
          setPrivacy(screenAware, micActive, true);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || 'Could not access camera');
          setPrivacy(screenAware, micActive, false);
        }
      }
    }

    startCamera();

    return () => {
      isMounted = false;
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
      }
    };
  }, [isOpen, selectedDeviceId]);

  // Frame capture loop sending base64 frames to backend via WS
  const captureFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !ws || ws.readyState !== WebSocket.OPEN) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (video.videoWidth === 0 || video.videoHeight === 0) return;

    canvas.width = Math.min(640, video.videoWidth);
    canvas.height = Math.min(480, video.videoHeight);

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.65);
    const base64Data = dataUrl.split(',')[1];

    ws.send(JSON.stringify({
      type: 'camera_frame',
      frame: base64Data,
      timestamp: Date.now(),
    }));
  }, [ws]);

  // Periodic capture (every 3 seconds when capturing is active)
  useEffect(() => {
    if (!isOpen || !stream || !isCapturing) return;

    const interval = setInterval(captureFrame, 3000);
    return () => clearInterval(interval);
  }, [isOpen, stream, isCapturing, captureFrame]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        style={{
          position: 'fixed',
          bottom: 100,
          right: 20,
          width: 320,
          zIndex: 9997,
          background: 'rgba(8,12,28,0.96)',
          border: '1.5px solid rgba(244,114,182,0.4)',
          borderRadius: 24,
          overflow: 'hidden',
          backdropFilter: 'blur(24px)',
          boxShadow: '0 20px 60px rgba(0,0,0,0.6), 0 0 30px rgba(244,114,182,0.15)',
          fontFamily: "'Inter', sans-serif",
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          background: 'rgba(255,255,255,0.03)',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <motion.div
              style={{ width: 8, height: 8, borderRadius: '50%', background: '#f472b6', boxShadow: '0 0 10px #f472b6' }}
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span style={{ color: '#f472b6', fontSize: 12, fontWeight: 700, letterSpacing: '0.05em' }}>
              CAMERA VISION
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: '#64748b',
              cursor: 'pointer',
              fontSize: 16,
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>

        {/* Video feed container */}
        <div style={{ position: 'relative', width: '100%', height: 200, background: '#000' }}>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
          <canvas ref={canvasRef} style={{ display: 'none' }} />

          {error && (
            <div style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#f87171',
              fontSize: 12,
              padding: 16,
              textAlign: 'center',
              background: 'rgba(0,0,0,0.85)',
            }}>
              {error}
            </div>
          )}

          {/* Privacy badge overlay */}
          <div style={{
            position: 'absolute',
            top: 10,
            left: 10,
            padding: '4px 8px',
            borderRadius: 99,
            background: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(8px)',
            color: isCapturing ? '#34d399' : '#94a3b8',
            fontSize: 10,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 5,
          }}>
            <div style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: isCapturing ? '#34d399' : '#64748b',
            }} />
            {isCapturing ? 'Genie is watching' : 'Stream Paused'}
          </div>
        </div>

        {/* Camera controls */}
        <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {devices.length > 1 && (
            <select
              value={selectedDeviceId}
              onChange={(e) => setSelectedDeviceId(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 10px',
                borderRadius: 10,
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: '#e2e8f0',
                fontSize: 11,
                outline: 'none',
              }}
            >
              {devices.map((d, i) => (
                <option key={d.deviceId} value={d.deviceId} style={{ background: '#0f172a' }}>
                  {d.label || `Camera ${i + 1}`}
                </option>
              ))}
            </select>
          )}

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={() => setIsCapturing(!isCapturing)}
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: 12,
                background: isCapturing ? 'rgba(248,113,113,0.2)' : 'rgba(52,211,153,0.2)',
                border: `1px solid ${isCapturing ? 'rgba(248,113,113,0.4)' : 'rgba(52,211,153,0.4)'}`,
                color: isCapturing ? '#f87171' : '#34d399',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {isCapturing ? '⏸ Pause Perception' : '▶ Share Camera with Genie'}
            </button>

            <button
              onClick={captureFrame}
              disabled={!stream}
              style={{
                padding: '8px 12px',
                borderRadius: 12,
                background: 'rgba(244,114,182,0.2)',
                border: '1px solid rgba(244,114,182,0.4)',
                color: '#f472b6',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                opacity: stream ? 1 : 0.5,
              }}
              title="Send single snapshot to Genie"
            >
              📸 Ask
            </button>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
