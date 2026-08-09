/**
 * GenieOSLayout.jsx — Responsive Desktop 3-Column Layout around the 3D Avatar Stage
 * Proportions:
 *   - Left Sidebar: 18%
 *   - Center Assistant Stage: 55% (3D Avatar primary centerpiece)
 *   - Right Context Panel: 27%
 */

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import LeftSidebar from './LeftSidebar';
import RightContextPanel from './RightContextPanel';
import CenterStageHeader from './CenterStageHeader';
import CenterStageFooter from './CenterStageFooter';
import GenieAvatarStage from '../avatar/GenieAvatarStage';
import { useAppStore } from '../../store/appStore';

function stripCueTags(text) {
  return (text || "").replace(/\[\[[a-z]+\]\]/gi, "").trim();
}

function ChatBubble({ role, text, isStreaming }) {
  const isUser = role === 'user';
  const displayText = isUser ? text : stripCueTags(text);

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} w-full items-end gap-2 my-1`}>
      {!isUser && (
        <div
          className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center font-bold text-[10px] text-white"
          style={{ background: 'linear-gradient(135deg,#22d3ee,#6366f1,#a855f7)' }}
        >
          G
        </div>
      )}
      <div
        className={`max-w-[80%] px-3.5 py-2.5 text-xs leading-relaxed ${
          isUser ? 'rounded-2xl rounded-br-xs bubble-user' : 'rounded-2xl rounded-bl-xs bubble-assistant'
        }`}
      >
        {displayText}
        {isStreaming && (
          <span className="inline-block ml-1 animate-pulse text-emerald-400">▋</span>
        )}
      </div>
    </div>
  );
}

export default function GenieOSLayout() {
  const genieState = useAppStore((s) => s.genieState);
  const messages = useAppStore((s) => s.messages);
  const currentAssistantId = useAppStore((s) => s.currentAssistantId);

  const [activeTab, setActiveTab] = useState('assistant');

  const scrollRef = useRef(null);
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const recentMessages = messages.slice(-10);

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 font-sans select-none">
      {/* ── 1. LEFT SIDEBAR (18%) ───────────────────────────────────────── */}
      <LeftSidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* ── 2. CENTER ASSISTANT AREA (55%) ─────────────────────────────── */}
      <main className="relative flex-1 flex flex-col h-full overflow-hidden bg-gradient-to-b from-slate-950 via-slate-900/60 to-slate-950">
        {/* Floating Header */}
        <CenterStageHeader />

        {/* Dedicated 3D Avatar Stage (Central Primary Focus) */}
        <div className="relative flex-1 w-full h-full flex items-center justify-center">
          <GenieAvatarStage genieState={genieState} />

          {/* Conversation History Modal Overlay (When user selects 'history' tab) */}
          <AnimatePresence>
            {activeTab === 'history' && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="absolute inset-6 z-30 flex flex-col rounded-3xl p-4 border bg-black/80 backdrop-blur-2xl shadow-2xl"
                style={{ borderColor: 'rgba(255, 255, 255, 0.1)' }}
              >
                <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-3">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>💬</span> Conversation History
                  </h3>
                  <button
                    onClick={() => setActiveTab('assistant')}
                    className="px-3 py-1 rounded-xl text-xs bg-white/10 hover:bg-white/20 text-slate-300 transition-colors"
                  >
                    Close Overlay
                  </button>
                </div>

                <div ref={scrollRef} className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
                  {recentMessages.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-xs text-slate-400">
                      No active messages yet. Say "Hey Genie" or send a prompt below.
                    </div>
                  ) : (
                    recentMessages.map((msg) => (
                      <ChatBubble
                        key={msg.id}
                        role={msg.role}
                        text={msg.text}
                        isStreaming={msg.id === currentAssistantId && genieState === 'speaking'}
                      />
                    ))
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Floating Bottom Input & Waveform Overlay */}
        <CenterStageFooter />
      </main>

      {/* ── 3. RIGHT CONTEXT PANEL (27%) ────────────────────────────────── */}
      <RightContextPanel />
    </div>
  );
}
