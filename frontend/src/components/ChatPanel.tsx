import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../store/appStore';

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onSendText: (text: string) => void;
}

export function ChatPanel({ isOpen, onClose, onSendText }: ChatPanelProps) {
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const messages = useAppStore((s) => s.messages);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    const text = inputText.trim();
    if (!text) return;
    onSendText(text);
    setInputText('');
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, x: 80, scale: 0.96 }}
          animate={{ opacity: 1, x: 0, scale: 1 }}
          exit={{ opacity: 0, x: 80, scale: 0.96 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          className="fixed top-16 right-6 bottom-24 z-40 w-full max-w-md p-5 rounded-3xl bg-slate-950/90 border border-cyan-500/30 backdrop-blur-2xl shadow-2xl shadow-cyan-500/20 text-slate-100 flex flex-col justify-between"
        >
          {/* Panel Header */}
          <div className="flex items-center justify-between pb-3 border-b border-cyan-500/20 mb-3">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
              <h3 className="text-sm font-semibold tracking-wide text-slate-100">
                Conversation & Activity Log
              </h3>
            </div>
            <button
              onClick={onClose}
              className="p-1 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800/60 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Messages Stream Area */}
          <div className="flex-1 overflow-y-auto space-y-3 pr-1 text-xs text-slate-200">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400 space-y-2">
                <div className="text-3xl opacity-60">💬</div>
                <p className="font-medium text-slate-300">No recent messages yet.</p>
                <p className="text-[11px] text-slate-500">
                  Speak aloud or type below to start a turn with Genie.
                </p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex flex-col ${
                    msg.role === 'user' ? 'items-end' : 'items-start'
                  }`}
                >
                  <div
                    className={`max-w-[85%] p-3 rounded-2xl leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-cyan-600/30 border border-cyan-400/40 text-cyan-100 rounded-br-none'
                        : 'bg-slate-900/80 border border-slate-800 text-slate-200 rounded-bl-none shadow-lg'
                    }`}
                  >
                    <div className="text-[10px] font-bold text-slate-400 uppercase mb-1">
                      {msg.role === 'user' ? 'You' : 'Genie'}
                    </div>
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Bottom Prompt Input */}
          <div className="pt-3 border-t border-cyan-500/20 mt-3 flex gap-2">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask Genie anything…"
              className="flex-1 px-3 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-xs text-slate-100 outline-none focus:border-cyan-400/60 transition-all placeholder:text-slate-500"
            />
            <button
              onClick={handleSend}
              className="px-4 py-2 rounded-xl bg-cyan-500/20 border border-cyan-400 text-cyan-200 text-xs font-semibold hover:bg-cyan-500/30 transition-all"
            >
              Send
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
