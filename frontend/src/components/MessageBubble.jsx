// MessageBubble: renders a single chat message (user or assistant). Assistant
// bubbles also render any inline tool events (open_app, etc.) as little chips.
import { motion, AnimatePresence } from "framer-motion";

const FRIENDLY_TOOL_NAMES = {
  open_app: "Opened app",
  close_app: "Closed app",
  launch_steam_game: "Launched game",
  open_url: "Opened site",
  open_whatsapp_chat: "Opened WhatsApp",
  open_instagram_chat: "Opened Instagram",
  play_youtube: "Playing",
  play_youtube_playlist: "Playing playlist",
  set_volume: "Set volume",
  trigger_night_light: "Night light",
  sleep_pc: "Sleeping PC",
  ghost_type: "Typed",
  capture_screen: "Looking at screen",
};

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const isError = message.isError;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed
          ${isUser
            ? "bg-gradient-to-br from-neon-blue/30 to-neon-violet/30 border border-neon-violet/40 rounded-br-sm"
            : isError
              ? "bg-neon-pink/15 border border-neon-pink/40 rounded-bl-sm"
              : "glass rounded-bl-sm"}`}
      >
        {/* Inline tool chips for assistant messages */}
        {!isUser && message.toolEvents?.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-1.5">
            {message.toolEvents.map((evt, idx) => (
              <ToolChip key={idx} evt={evt} />
            ))}
          </div>
        )}
        <p className={isUser ? "text-white" : isError ? "text-neon-pink" : "text-gray-100"}>
          {message.text || (isUser ? "" : "…")}
        </p>
      </div>
    </motion.div>
  );
}

function ToolChip({ evt }) {
  // Show the latest state of a tool (end over start).
  const done = evt.type === "tool_end";
  const label = FRIENDLY_TOOL_NAMES[evt.name] || evt.name;
  const status = done ? (evt.result?.status || "ok") : "running";
  const color =
    status === "error" ? "border-neon-pink/60 text-neon-pink"
    : status === "not_found" ? "border-amber-400/60 text-amber-300"
    : done ? "border-neon-cyan/50 text-neon-cyan"
    : "border-white/20 text-gray-300";

  return (
    <AnimatePresence>
      <motion.span
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        className={`text-[11px] px-2 py-0.5 rounded-full border bg-space-900/60 ${color}`}
      >
        {done ? "✓" : "•"} {label}
      </motion.span>
    </AnimatePresence>
  );
}
