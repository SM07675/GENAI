import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface FloatingInputProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (text: string) => void;
}

export function FloatingInput({ isOpen, onClose, onSubmit }: FloatingInputProps) {
  const [text, setText] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    } else {
      setText('');
    }
  }, [isOpen]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    onSubmit(text);
    setText('');
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="fixed bottom-28 left-1/2 -translate-x-1/2 z-40 w-full max-w-xl px-4"
        >
          <form
            onSubmit={handleSubmit}
            className="relative flex items-center w-full p-2.5 rounded-2xl bg-slate-950/80 border border-cyan-500/30 backdrop-blur-2xl shadow-2xl shadow-cyan-500/10 group"
          >
            {/* Soft Ambient Glow */}
            <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan-500/20 via-blue-500/20 to-purple-500/20 rounded-2xl blur opacity-75 group-hover:opacity-100 transition duration-500 pointer-events-none" />

            {/* Input Field */}
            <input
              ref={inputRef}
              type="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Ask Genie anything..."
              className="relative z-10 w-full px-4 py-3 bg-transparent text-slate-100 placeholder-cyan-200/40 text-base font-normal focus:outline-none"
            />

            {/* Close Button */}
            <button
              type="button"
              onClick={onClose}
              className="relative z-10 p-2 mr-1 text-slate-400 hover:text-slate-200 rounded-xl hover:bg-slate-800/50 transition-colors"
              title="Close keyboard"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {/* Send Button */}
            <motion.button
              type="submit"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              disabled={!text.trim()}
              className="relative z-10 flex items-center justify-center px-4 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-medium shadow-lg shadow-cyan-500/20 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              <svg className="w-5 h-5 transform rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </motion.button>
          </form>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
