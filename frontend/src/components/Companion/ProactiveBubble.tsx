/**
 * ProactiveBubble.tsx — Non-blocking proactive suggestion card from Genie.
 * Auto-dismisses after timeout. User can expand or dismiss early.
 */
import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useCompanionStore } from '../../store/companionStore';

const AUTO_DISMISS_MS = 12000;

export default function ProactiveBubble() {
  const bubbleText = useCompanionStore((s) => s.bubbleText);
  const bubbleVisible = useCompanionStore((s) => s.bubbleVisible);
  const setBubble = useCompanionStore((s) => s.setBubble);

  useEffect(() => {
    if (!bubbleVisible || !bubbleText) return;
    const t = setTimeout(() => setBubble(null, false), AUTO_DISMISS_MS);
    return () => clearTimeout(t);
  }, [bubbleVisible, bubbleText, setBubble]);

  return (
    <AnimatePresence>
      {bubbleVisible && bubbleText && (
        <motion.div
          initial={{ opacity: 0, x: -16, scale: 0.92 }}
          animate={{ opacity: 1, x: 0, scale: 1 }}
          exit={{ opacity: 0, x: -16, scale: 0.92 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          style={{
            position: 'absolute',
            right: 'calc(100% + 12px)',
            top: '15%',
            width: 220,
            background: 'rgba(8,12,28,0.97)',
            border: '1px solid rgba(99,102,241,0.35)',
            borderRadius: 18,
            padding: '12px 14px',
            boxShadow: '0 12px 40px rgba(0,0,0,0.6), 0 0 30px rgba(99,102,241,0.12)',
            backdropFilter: 'blur(20px)',
            pointerEvents: 'auto',
          }}
        >
          {/* Header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 8,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <motion.div
                style={{ width: 6, height: 6, borderRadius: '50%', background: '#818CF8', boxShadow: '0 0 8px #818CF8' }}
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
              <span style={{ color: '#818CF8', fontSize: 10, fontWeight: 700, fontFamily: "'Inter', sans-serif", letterSpacing: '0.05em' }}>
                GENIE SUGGESTS
              </span>
            </div>
            <button
              onClick={() => setBubble(null, false)}
              style={{
                background: 'none',
                border: 'none',
                color: '#475569',
                cursor: 'pointer',
                fontSize: 14,
                lineHeight: 1,
                padding: 0,
              }}
            >
              ×
            </button>
          </div>

          {/* Content */}
          <p style={{
            color: '#cbd5e1',
            fontSize: 12,
            fontFamily: "'Inter', sans-serif",
            lineHeight: 1.6,
            margin: 0,
          }}>
            {bubbleText}
          </p>

          {/* Auto-dismiss progress bar */}
          <motion.div
            style={{
              height: 2,
              background: '#818CF8',
              borderRadius: 99,
              marginTop: 10,
              transformOrigin: 'left',
            }}
            initial={{ scaleX: 1 }}
            animate={{ scaleX: 0 }}
            transition={{ duration: AUTO_DISMISS_MS / 1000, ease: 'linear' }}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
