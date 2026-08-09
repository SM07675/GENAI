/**
 * CenterStageHeader.jsx — Floating header overlay over center 3D avatar stage
 * Displays Greeting, State Pill, System Time, and Controls.
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import MinimalControls from '../MinimalControls';

const STATUS_CONFIG = {
  sleeping:            { label: 'Say "Hey Genie"', color: '#64748b', pulse: false },
  waking:              { label: 'Waking up…',       color: '#38bdf8', pulse: true  },
  idle:                { label: 'Ready',             color: '#64748b', pulse: false },
  listening:           { label: 'Listening',         color: '#22d3ee', pulse: true  },
  transcribing:        { label: 'Processing…',       color: '#a78bfa', pulse: true  },
  thinking:            { label: 'Thinking…',         color: '#c084fc', pulse: true  },
  executing:           { label: 'Working…',          color: '#f59e0b', pulse: true  },
  speaking:            { label: 'Speaking',          color: '#34d399', pulse: true  },
  follow_up_listening: { label: 'Listening…',        color: '#22d3ee', pulse: true  },
  interrupted:         { label: 'Stopped',           color: '#fb923c', pulse: false },
  error:               { label: 'Error',             color: '#f87171', pulse: false },
};

export default function CenterStageHeader() {
  const genieState = useAppStore((s) => s.genieState);
  const statusCfg = STATUS_CONFIG[genieState] || STATUS_CONFIG.idle;

  const [timeStr, setTimeStr] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const d = new Date();
      setTimeStr(d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="absolute top-0 left-0 right-0 z-20 p-4 pointer-events-none flex items-center justify-between">
      {/* Left: Greeting & Date */}
      <div className="pointer-events-auto flex items-center gap-3 bg-black/40 backdrop-blur-xl px-4 py-2 rounded-2xl border border-white/10 shadow-lg">
        <span className="text-xl">✨</span>
        <div>
          <h2 className="text-xs font-bold text-white tracking-wide">Genie Companion</h2>
          <p className="text-[10px] text-slate-400 font-mono">{timeStr}</p>
        </div>
      </div>

      {/* Center: State Pill */}
      <div className="pointer-events-auto">
        <motion.div
          key={genieState}
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-2 px-4 py-1.5 rounded-full shadow-lg"
          style={{
            background: `${statusCfg.color}1a`,
            border: `1px solid ${statusCfg.color}40`,
            backdropFilter: 'blur(16px)',
          }}
        >
          <span className="relative flex items-center justify-center w-2 h-2">
            {statusCfg.pulse && (
              <span
                className="absolute inline-flex h-full w-full rounded-full"
                style={{ backgroundColor: statusCfg.color, opacity: 0.6, animation: 'ping 1.4s cubic-bezier(0,0,0.2,1) infinite' }}
              />
            )}
            <span className="relative inline-flex rounded-full w-1.5 h-1.5" style={{ backgroundColor: statusCfg.color }} />
          </span>
          <span className="text-xs font-semibold tracking-wide" style={{ color: statusCfg.color }}>
            {statusCfg.label}
          </span>
        </motion.div>
      </div>

      {/* Right: Controls */}
      <div className="pointer-events-auto">
        <MinimalControls embedded />
      </div>
    </header>
  );
}
