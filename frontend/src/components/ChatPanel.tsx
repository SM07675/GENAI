import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../store/appStore';
import { ChatIcon, SendIcon, CloseIcon } from './UI/Icons';

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
          className="fixed top-16 right-6 bottom-24 z-40 w-full max-w-md p-5 rounded-3xl cyber-glass shadow-2xl flex flex-col justify-between"
        >
          {/* Panel Header */}
          <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-3">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse shadow-sm shadow-cyan-400/50" />
              <h3 className="text-sm font-bold tracking-wide text-slate-100 flex items-center gap-2">
                <ChatIcon size={16} className="text-cyan-400" />
                <span>Conversation & Activity Drawer</span>
              </h3>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-200 rounded-xl hover:bg-white/10 transition-colors"
            >
              <CloseIcon size={18} />
            </button>
          </div>

          {/* Messages Stream Area */}
          <div className="flex-1 overflow-y-auto space-y-3 pr-1 text-xs text-slate-200 custom-scrollbar">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400 space-y-3">
                <div className="p-4 rounded-3xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
                  <ChatIcon size={32} />
                </div>
                <p className="font-semibold text-slate-300">No recent messages yet.</p>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Speak aloud or type below to talk with Genie.
                </p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={msg.id || idx}
                  className={`flex flex-col ${
                    msg.role === 'user' ? 'items-end' : 'items-start'
                  }`}
                >
                  <div
                    className={`max-w-[85%] p-3.5 rounded-2xl leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-cyan-500/20 border border-cyan-500/40 text-cyan-100 rounded-br-none shadow-md'
                        : 'bg-slate-900/90 border border-white/10 text-slate-200 rounded-bl-none shadow-lg'
                    }`}
                  >
                    <div className="text-[10px] font-bold text-slate-400 uppercase mb-1 flex items-center justify-between gap-4">
                      <span>{msg.role === 'user' ? 'You' : 'Genie'}</span>
                      {msg.ts && (
                        <span className="text-[9px] text-slate-500">
                          {new Date(msg.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      )}
                    </div>
                    <div className="whitespace-pre-wrap">{msg.text || msg.content}</div>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Bottom Prompt Input */}
          <div className="pt-3 border-t border-white/10 mt-3 flex gap-2">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask Genie anything…"
              className="flex-1 px-3.5 py-2.5 rounded-2xl bg-slate-900/80 border border-white/15 text-xs text-slate-100 outline-none focus:border-cyan-400 transition-all placeholder:text-slate-500"
            />
            <button
              onClick={handleSend}
              className="px-4 py-2.5 rounded-2xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white text-xs font-bold transition-all shadow-md shadow-cyan-500/20 flex items-center gap-1.5"
            >
              <SendIcon size={14} />
              <span>Send</span>
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
