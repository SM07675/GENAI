import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../store/appStore';
import { useCompanionStore } from '../store/companionStore';

const Cog6ToothIcon = ({ className }) => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 011.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.107 1.204.165.397.505.71.93.78l.893.15c.543.09.94.56.94 1.109v1.094c0 .55-.397 1.02-.94 1.11l-.893.149c-.425.07-.765.383-.93.78-.165.398-.143.854.107 1.204l.527.738c.32.447.269 1.06-.12 1.45l-.774.773a1.125 1.125 0 01-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.107-.397.165-.71.505-.781.929l-.149.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.148-.894c-.071-.424-.384-.764-.781-.93-.398-.164-.854-.142-1.204.108l-.738.527c-.447.32-1.06.269-1.45-.12l-.773-.774a1.125 1.125 0 01-.12-1.45l.527-.737c.25-.35.273-.806.108-1.204-.165-.397-.505-.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.109v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.765-.383.93-.78.165-.398.143-.854-.107-1.204l-.527-.738a1.125 1.125 0 01.12-1.45l.773-.773a1.125 1.125 0 011.45-.12l.737.527c.35.25.807.272 1.204.107.397-.165.71-.505.78-.929l.15-.894z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

const XMarkIcon = ({ className }) => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const KeyboardIcon = ({ className }) => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 7.5h10.5a2.25 2.25 0 012.25 2.25v4.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 14.25v-4.5A2.25 2.25 0 016.75 7.5zM6 10.5h.008v.008H6v-.008zm3 0h.008v.008H9v-.008zm3 0h.008v.008H12v-.008zm3 0h.008v.008H15v-.008zm-6 3h.008v.008H9v-.008zm3 0h.008v.008H12v-.008zm3 0h.008v.008H15v-.008zm-4.5 3h6v.008h-6v-.008z" />
  </svg>
);

const PaperAirplaneIcon = ({ className }) => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
  </svg>
);

const CompanionEyeIcon = ({ className }) => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

/**
 * MinimalControls — top-right controls row.
 * When `embedded` is true, renders inline (no absolute positioning).
 * When standalone (pin gate), renders absolutely positioned.
 */
export default function MinimalControls({ embedded = false }) {
  const wsStatus = useAppStore((s) => s.wsStatus);
  const isOnline = wsStatus === 'connected' || wsStatus === 'authed';
  const [showInput, setShowInput] = useState(false);
  const [text, setText] = useState("");
  const companionMode = useCompanionStore((s) => s.mode);
  const companionActive = companionMode !== 'off';

  const handleSend = () => {
    if (!text.trim()) return;
    const ws = useAppStore.getState().ws;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'text', text: text.trim() }));
    }
    setText("");
    setShowInput(false);
  };

  const handleClose = () => {
    if (window.genie && window.genie.close) {
      window.genie.close();
    } else {
      window.close();
    }
  };

  const handleCompanionToggle = () => {
    const ws = useAppStore.getState().ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    if (companionActive) {
      ws.send(JSON.stringify({ type: 'companion_stop' }));
    } else {
      ws.send(JSON.stringify({ type: 'companion_start', mode: 'general' }));
    }
  };

  const controls = (
    <div className={`flex flex-col items-end gap-2 ${embedded ? '' : 'pointer-events-auto'}`}>
      <div
        className="flex items-center gap-1 p-1 rounded-full"
        style={{
          background: 'rgba(15,20,40,0.65)',
          backdropFilter: 'blur(24px)',
          border: '1px solid rgba(255,255,255,0.08)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
        }}
      >
        {/* Online indicator */}
        <div
          className={`w-2 h-2 rounded-full mx-1.5 flex-shrink-0`}
          style={{
            background: isOnline ? '#34d399' : '#f87171',
            boxShadow: isOnline ? '0 0 6px rgba(52,211,153,0.6)' : '0 0 6px rgba(248,113,113,0.6)',
          }}
        />

        <button
          onClick={() => setShowInput((v) => !v)}
          className="p-1.5 rounded-full transition-colors"
          style={{ color: showInput ? '#6366f1' : '#94a3b8' }}
          title="Type a message"
        >
          <KeyboardIcon className="w-4 h-4" />
        </button>

        <button
          onClick={handleCompanionToggle}
          className="p-1.5 rounded-full transition-all"
          style={{
            color: companionActive ? '#a78bfa' : '#94a3b8',
            background: companionActive ? 'rgba(139,92,246,0.15)' : 'transparent',
            boxShadow: companionActive ? '0 0 8px rgba(139,92,246,0.4)' : 'none',
          }}
          title={companionActive ? 'Stop Companion Mode' : 'Start Companion Mode'}
        >
          <CompanionEyeIcon className="w-4 h-4" />
        </button>

        <button
          className="p-1.5 rounded-full transition-colors"
          style={{ color: '#94a3b8' }}
          title="Settings"
        >
          <Cog6ToothIcon className="w-4 h-4" />
        </button>

        <button
          onClick={handleClose}
          className="p-1.5 rounded-full transition-colors"
          style={{ color: '#94a3b8' }}
          onMouseEnter={(e) => e.currentTarget.style.color = '#f87171'}
          onMouseLeave={(e) => e.currentTarget.style.color = '#94a3b8'}
          title="Close"
        >
          <XMarkIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Text input drawer */}
      <AnimatePresence>
        {showInput && (
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: -8 }}
            transition={{ duration: 0.18 }}
            className="rounded-2xl p-2 flex items-center gap-2 w-56"
            style={{
              background: 'rgba(15,20,40,0.80)',
              backdropFilter: 'blur(24px)',
              border: '1px solid rgba(255,255,255,0.09)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            }}
          >
            <input
              type="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask Genie…"
              className="flex-1 bg-transparent border-none outline-none text-sm px-2"
              style={{ color: '#e2e8f0' }}
              autoFocus
            />
            <button
              onClick={handleSend}
              className="p-1.5 rounded-xl flex-shrink-0 transition-opacity hover:opacity-80"
              style={{ background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', color: '#fff' }}
            >
              <PaperAirplaneIcon className="w-3.5 h-3.5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );

  if (embedded) return controls;

  return (
    <div className="absolute top-4 right-4 z-50 pointer-events-none">
      <div className="pointer-events-auto">
        {controls}
      </div>
    </div>
  );
}
