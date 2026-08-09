/**
 * PrivacyPanel.tsx — Always-visible privacy status indicators.
 *
 * Per spec §24: users must know exactly what Genie can access.
 * MIC ● CAMERA ● SCREEN ● — always visible when companion is active.
 */
import React from 'react';
import { motion } from 'framer-motion';

interface PrivacyPanelProps {
  screenAware: boolean;
  micActive: boolean;
  cameraActive?: boolean;
  stateColor: string;
}

export default function PrivacyPanel({ screenAware, micActive, cameraActive = false, stateColor }: PrivacyPanelProps) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 12,
      padding: '8px 16px',
      borderTop: '1px solid rgba(255,255,255,0.06)',
      borderBottom: '1px solid rgba(255,255,255,0.06)',
      marginBottom: 8,
    }}>
      <PrivacyDot active={micActive} color="#a78bfa" label="MIC" icon="🎤" />
      <PrivacyDot active={cameraActive} color="#f472b6" label="CAM" icon="📷" />
      <PrivacyDot active={screenAware} color="#22d3ee" label="SCR" icon="🖥" />
    </div>
  );
}

function PrivacyDot({ active, color, label, icon }: { active: boolean; color: string; label: string; icon: string }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 5,
      padding: '3px 8px',
      borderRadius: 99,
      background: active ? `${color}18` : 'rgba(255,255,255,0.04)',
      border: `1px solid ${active ? color + '55' : 'rgba(255,255,255,0.08)'}`,
      transition: 'all 0.3s',
    }}>
      <motion.div
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: active ? color : '#475569',
          boxShadow: active ? `0 0 8px ${color}` : 'none',
          flexShrink: 0,
          transition: 'all 0.3s',
        }}
        animate={active ? { opacity: [1, 0.4, 1] } : { opacity: 1 }}
        transition={{ duration: 1.5, repeat: active ? Infinity : 0 }}
      />
      <span style={{
        color: active ? color : '#64748b',
        fontSize: 10,
        fontWeight: 700,
        fontFamily: "'Inter', sans-serif",
        letterSpacing: '0.06em',
        transition: 'color 0.3s',
      }}>
        {label}
      </span>
    </div>
  );
}
