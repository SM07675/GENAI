// StatusBar: shows connection state + the live ngrok public URL (so you can
// pair your phone). Also hosts the desktop window controls when in Electron.
import { useAppStore } from "../store/appStore";

const STATUS_META = {
  disconnected: { label: "Disconnected", color: "bg-gray-500" },
  connecting: { label: "Connecting", color: "bg-amber-400 animate-pulse" },
  connected: { label: "Connected", color: "bg-amber-400 animate-pulse" },
  authed: { label: "Ready", color: "bg-emerald-400" },
  error: { label: "Error", color: "bg-neon-pink" },
};

export default function StatusBar({ continuousMode, onToggleContinuous, onSettings }) {
  const wsStatus = useAppStore((s) => s.wsStatus);
  const publicUrl = useAppStore((s) => s.publicUrl);
  const meta = STATUS_META[wsStatus] || STATUS_META.disconnected;
  const isElectron = typeof window !== "undefined" && window.genie?.isElectron;

  return (
    <div className="flex items-center justify-between px-4 py-2 text-xs text-gray-400 border-b border-white/5">
      {/* Left: connection state */}
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${meta.color}`} />
        <span>{meta.label}</span>
        {continuousMode && (
          <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/30">
            CONTINUOUS
          </span>
        )}
      </div>

      {/* Center/right: controls and public URL */}
      <div className="flex items-center gap-3 min-w-0" style={{ WebkitAppRegion: "no-drag" }}>
        {/* Continuous mode toggle */}
        {onToggleContinuous && (
          <button
            onClick={onToggleContinuous}
            className={`transition ${
              continuousMode 
                ? 'text-neon-cyan hover:text-neon-cyan/80' 
                : 'text-gray-500 hover:text-gray-300'
            }`}
            title="Toggle continuous conversation (like Alexa)"
          >
            🔄
          </button>
        )}

        {/* Settings */}
        {onSettings && (
          <button
            onClick={onSettings}
            className="text-gray-500 hover:text-gray-300 transition"
            title="Settings"
          >
            ⚙️
          </button>
        )}

        {publicUrl && (
          <button
            onClick={() => navigator.clipboard?.writeText(publicUrl)}
            className="truncate max-w-[180px] text-neon-cyan hover:underline"
            title="Copy mobile URL"
          >
            {publicUrl.replace(/^https?:\/\//, "")}
          </button>
        )}
      </div>

      {/* Electron window controls */}
      {isElectron && (
        <div className="flex gap-2" style={{ WebkitAppRegion: "no-drag" }}>
          <button onClick={() => window.genie.minimize()} className="text-gray-500 hover:text-white px-2">—</button>
          <button onClick={() => window.genie.close()} className="text-gray-500 hover:text-neon-pink px-2">✕</button>
        </div>
      )}
    </div>
  );
}
