/**
 * SettingsView.tsx — Main Application Settings Page.
 *
 * Per spec §46:
 * - Appearance: Size, Glow, Theme, Accent, Opacity
 * - Behavior: Always on top, Click-through, Edge snapping, Follow active monitor, Start with Windows, Proactive assistance
 * - Voice: Voice selection, Speed, Volume, Wake word, Silence detection
 * - Privacy: Microphone, Camera, Screen, Cloud AI, Memory
 */
import React, { useState } from 'react';

export default function SettingsView() {
  const [themeMode, setThemeMode] = useState<string>('light');
  const [startWithWindows, setStartWithWindows] = useState<boolean>(false);
  const [proactiveEnabled, setProactiveEnabled] = useState<boolean>(true);
  const [edgeSnapping, setEdgeSnapping] = useState<boolean>(true);
  const [micEnabled, setMicEnabled] = useState<boolean>(true);
  const [cameraEnabled, setCameraEnabled] = useState<boolean>(true);
  const [screenEnabled, setScreenEnabled] = useState<boolean>(true);

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Genie System Settings
        </h1>
        <p className="text-sm font-medium text-slate-500 mt-1">
          Manage system preferences, sensor permissions, voice engines, and desktop behaviors.
        </p>
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Appearance & Theme */}
        <div className="sky-glass-card rounded-2xl p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2 border-b border-sky-200/60 pb-3">
            <span>🎨</span> Appearance & Theme
          </h3>

          <div className="space-y-4 text-xs">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-800">Theme Mode</div>
                <div className="text-[11px] text-slate-500">Sky Blue Light Theme is recommended</div>
              </div>
              <select
                value={themeMode}
                onChange={(e) => setThemeMode(e.target.value)}
                className="px-3 py-1.5 rounded-xl bg-white border border-sky-200 text-slate-800 font-semibold outline-none"
              >
                <option value="light">Sky Blue Light Theme (Default)</option>
                <option value="dark">Deep Sky Dark Theme</option>
                <option value="system">Follow System Theme</option>
              </select>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-800">Animation Intensity</div>
                <div className="text-[11px] text-slate-500">Adjust GPU avatar float & eye micro-movement</div>
              </div>
              <input type="range" min="0.2" max="1.0" step="0.1" defaultValue="0.8" className="accent-sky-500 w-32" />
            </div>
          </div>
        </div>

        {/* Behavior & Windows Integration */}
        <div className="sky-glass-card rounded-2xl p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2 border-b border-sky-200/60 pb-3">
            <span>⚙</span> Desktop Behavior
          </h3>

          <div className="space-y-4 text-xs">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-800">Start Genie Companion with Windows</div>
                <div className="text-[11px] text-slate-500">Launch background companion process at system boot</div>
              </div>
              <ToggleSwitch active={startWithWindows} onChange={() => setStartWithWindows(!startWithWindows)} />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-800">Edge Magnetic Snapping</div>
                <div className="text-[11px] text-slate-500">Snap companion smoothly to desktop screen edges</div>
              </div>
              <ToggleSwitch active={edgeSnapping} onChange={() => setEdgeSnapping(!edgeSnapping)} />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-800">Proactive Assistance Cards</div>
                <div className="text-[11px] text-slate-500">Allow Genie to offer non-intrusive contextual suggestions</div>
              </div>
              <ToggleSwitch active={proactiveEnabled} onChange={() => setProactiveEnabled(!proactiveEnabled)} />
            </div>
          </div>
        </div>

        {/* Privacy & Sensors */}
        <div className="sky-glass-card rounded-2xl p-6 space-y-4 lg:col-span-2">
          <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2 border-b border-sky-200/60 pb-3">
            <span>🛡</span> Privacy Center & Sensor Access
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <PermissionCard
              title="Microphone Access"
              subtitle="Voice input for wake word & conversation"
              active={micEnabled}
              onToggle={() => setMicEnabled(!micEnabled)}
              icon="🎤"
            />
            <PermissionCard
              title="Camera Vision"
              subtitle="Webcam vision for object & scene analysis"
              active={cameraEnabled}
              onToggle={() => setCameraEnabled(!cameraEnabled)}
              icon="📷"
            />
            <PermissionCard
              title="Screen Awareness"
              subtitle="Context engine app & error identification"
              active={screenEnabled}
              onToggle={() => setScreenEnabled(!screenEnabled)}
              icon="🖥"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function ToggleSwitch({ active, onChange }: { active: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors ${
        active ? 'bg-sky-500' : 'bg-slate-300'
      }`}
    >
      <div
        className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform ${
          active ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </button>
  );
}

function PermissionCard({ title, subtitle, active, onToggle, icon }: { title: string; subtitle: string; active: boolean; onToggle: () => void; icon: string }) {
  return (
    <div className="p-4 rounded-xl bg-white/70 border border-sky-100 flex flex-col justify-between space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-lg">{icon}</span>
        <ToggleSwitch active={active} onChange={onToggle} />
      </div>
      <div>
        <div className="font-bold text-slate-800">{title}</div>
        <div className="text-[11px] text-slate-500 mt-0.5">{subtitle}</div>
      </div>
    </div>
  );
}
