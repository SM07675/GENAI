// ChatPanel: the scrolling transcript. Auto-scrolls to the latest message and
// shows a subtle "Genie is thinking" indicator when tools are in flight.
import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import MessageBubble from "./MessageBubble";
import { useAppStore } from "../store/appStore";

export default function ChatPanel() {
  const messages = useAppStore((s) => s.messages);
  const activeTools = useAppStore((s) => s.activeToolEvents);
  const orbState = useAppStore((s) => s.orbState);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, activeTools]);

  const showThinking = orbState === "thinking" && activeTools.length > 0;

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
      {messages.length === 0 && (
        <div className="h-full flex flex-col items-center justify-center text-center px-6 text-gray-500">
          <p className="text-sm">
            Say something or type a command.
          </p>
          <p className="text-xs mt-2 text-gray-600">
            Try: “open chrome”, “launch palworld”, “play sad songs”, “set volume to 50”, “what's on my screen”
          </p>
        </div>
      )}

      <AnimatePresence initial={false}>
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
      </AnimatePresence>

      <AnimatePresence>
        {showThinking && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2 px-2 text-xs text-gray-400"
          >
            <span className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-neon-cyan"
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
                />
              ))}
            </span>
            working on it…
          </motion.div>
        )}
      </AnimatePresence>

      <div ref={endRef} />
    </div>
  );
}
