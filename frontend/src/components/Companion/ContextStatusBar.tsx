/**
 * ContextStatusBar.tsx — Shows current app/project/time context in companion.
 */
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface ContextItem {
  icon: string;
  label: string;
  value: string;
}

export default function ContextStatusBar() {
  const [time, setTime] = useState(() => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
  const [contextItems, setContextItems] = useState<ContextItem[]>([
    { icon: '🕐', label: 'Time', value: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) },
  ]);

  // Update clock
  useEffect(() => {
    const interval = setInterval(() => {
      const t = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      setTime(t);
      setContextItems(prev => prev.map(item => item.label === 'Time' ? { ...item, value: t } : item));
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  // In production, context items would be pushed via WebSocket from the ContextEngine
  // (current app, project, open file). For now we show time + placeholder.

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '6px 16px 10px',
      overflowX: 'auto',
      scrollbarWidth: 'none',
    }}>
      {contextItems.map((item, i) => (
        <motion.div
          key={item.label}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: i * 0.05 }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '3px 8px',
            borderRadius: 99,
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 10 }}>{item.icon}</span>
          <span style={{ color: '#64748b', fontSize: 10, fontFamily: "'Inter', sans-serif" }}>
            {item.label}:
          </span>
          <span style={{ color: '#94a3b8', fontSize: 10, fontWeight: 600, fontFamily: "'Inter', sans-serif" }}>
            {item.value}
          </span>
        </motion.div>
      ))}
    </div>
  );
}
