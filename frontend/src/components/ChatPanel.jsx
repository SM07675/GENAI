import { motion, AnimatePresence } from "framer-motion";
import { useAppStore } from "../store/appStore";

// The Minimalist Interaction Display. Replaces the scrolling chat history 
// with a single, highly readable active interaction text block.
export default function ChatPanel() {
  const messages = useAppStore((s) => s.messages);
  const activeTools = useAppStore((s) => s.activeToolEvents);
  const orbState = useAppStore((s) => s.orbState);

  // We only care about the very last message in this minimalist mode
  const activeMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  const showThinking = orbState === "thinking" && activeTools.length > 0;

  // Determine the current tool being executed
  let activeToolName = "";
  if (showThinking) {
    const latestTool = activeTools[activeTools.length - 1];
    activeToolName = FRIENDLY_TOOL_NAMES[latestTool?.name] || latestTool?.name || "Processing data...";
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 py-4 overflow-hidden relative">
      <AnimatePresence mode="wait">
        {!activeMessage ? (
          // Welcome State
          <motion.div 
            key="welcome"
            className="text-center"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.1, filter: "blur(10px)" }}
            transition={{ duration: 0.5 }}
          >
            <motion.div
              className="text-5xl mb-4 text-white font-bold"
              style={{ textShadow: "0 0 20px #22d3ee, 0 0 40px #a855f7" }}
              animate={{ opacity: [0.8, 1, 0.8] }}
              transition={{ duration: 3, repeat: Infinity }}
            >
              SYS_READY
            </motion.div>
            <p className="text-xs text-gray-400 font-mono tracking-widest">
              AWAITING COMMAND INPUT
            </p>
          </motion.div>
        ) : (
          // Active Interaction State
          <motion.div
            key={activeMessage.id}
            className="w-full max-w-sm text-center"
            initial={{ opacity: 0, y: 20, filter: "blur(5px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -20, filter: "blur(5px)" }}
            transition={{ duration: 0.4 }}
          >
            {/* The actual text content */}
            <p className="text-xl md:text-2xl font-bold tracking-wide text-white break-words whitespace-pre-wrap"
               style={{ 
                 textShadow: activeMessage.role === "user" 
                   ? "0 2px 10px rgba(0,0,0,0.8), 0 0 20px #22d3ee" 
                   : "0 2px 10px rgba(0,0,0,0.8), 0 0 20px #ec4899" 
               }}
            >
              {activeMessage.text || (activeMessage.role === "user" ? "" : "...")}
            </p>

            {/* Sub-label showing who is speaking */}
            <p className="text-[10px] font-mono tracking-widest mt-4 opacity-50 uppercase" style={{ color: activeMessage.role === "user" ? "#22d3ee" : "#ec4899" }}>
              {activeMessage.role === "user" ? "> USER INPUT" : "> SYSTEM RESPONSE"}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Futuristic Thinking / Tool Execution Indicator */}
      <AnimatePresence>
        {showThinking && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="absolute bottom-4 left-0 right-0 flex justify-center"
          >
            <div className="flex items-center gap-3 px-6 py-2 cyber-pill bg-[#0a0b1e]/80 border border-neon-purple shadow-[0_0_15px_rgba(168,85,247,0.3)]">
              <span className="flex gap-1.5">
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-neon-purple"
                    animate={{ 
                      scale: [1, 1.5, 1],
                      opacity: [0.3, 1, 0.3] 
                    }}
                    transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15 }}
                  />
                ))}
              </span>
              <span className="text-xs font-mono text-neon-purple tracking-wider uppercase">
                {activeToolName}
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const FRIENDLY_TOOL_NAMES = {
  open_app: "Opening app",
  close_app: "Closing app",
  launch_steam_game: "Launching game",
  open_url: "Opening site",
  open_whatsapp_chat: "Opening WhatsApp",
  open_instagram_chat: "Opening Instagram",
  play_youtube: "Playing video",
  play_youtube_playlist: "Playing playlist",
  search_youtube_music: "Searching music",
  play_youtube_music: "Playing music",
  set_volume: "Adjusting volume",
  trigger_night_light: "Toggling night light",
  sleep_pc: "Sleeping PC",
  ghost_type: "Typing",
  capture_screen: "Scanning screen",
  manage_note: "Accessing memory",
  set_reminder: "Setting reminder",
  search_web: "Searching web",
  get_news: "Fetching news",
  get_news_briefing: "Generating briefing",
  get_api_status: "Checking APIs",
  get_weather: "Fetching weather",
  get_time: "Checking time",
  calculate: "Calculating",
  clipboard_read: "Reading clipboard",
  clipboard_write: "Writing clipboard",
};
