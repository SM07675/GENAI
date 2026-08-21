/**
 * SettingsView.tsx — Main Application Settings Page.
 */
import React, { useState } from 'react';
import {
  SettingsIcon,
  MicIcon,
  CameraIcon,
  EyeIcon,
  ShieldIcon,
  SunIcon,
  MoonIcon,
  SparklesIcon,
} from '../UI/Icons';

export default function SettingsView() {
  const [themeMode, setThemeMode] = useState<string>('dark');
  const [startWithWindows, setStartWithWindows] = useState<boolean>(false);
  const [proactiveEnabled, setProactiveEnabled] = useState<boolean>(true);
  const [edgeSnapping, setEdgeSnapping] = useState<boolean>(true);
  const [micEnabled, setMicEnabled] = useState<boolean>(true);
  const [cameraEnabled, setCameraEnabled] = useState<boolean>(true);
  const [screenEnabled, setScreenEnabled] = useState<boolean>(true);

  const handleThemeChange = (newTheme: string) => {
    setThemeMode(newTheme);
    if (newTheme === 'sky') {
      document.documentElement.classList.add('theme-sky');
    } else {
      document.documentElement.classList.remove('theme-sky');
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Genie System Settings
        </h1>
        <p className="text-xs md:text-sm font-medium text-slate-400 mt-1">
          Manage system preferences, sensor permissions, voice engines, theme aesthetics, and desktop behaviors.
        </p>
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Appearance & Theme */}
        <div className="cyber-card rounded-3xl p-6 space-y-4">
          <h3 className="text-sm font-bold flex items-center gap-2 border-b border-white/10 pb-3">
            <SparklesIcon size={18} className="text-cyan-400" />
            <span>Appearance & Theme System</span>
          </h3>

          <div className="space-y-4 text-xs">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-200">Theme Aesthetic</div>
                <div className="text-[11px] text-slate-400">Cyber Luxe Dark or Sky Glass Aurora</div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleThemeChange('dark')}
                  className={`px-3 py-1.5 rounded-xl font-bold flex items-center gap-1.5 transition-all ${
                    themeMode === 'dark'
                      ? 'bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/30'
                      : 'bg-white/5 text-slate-300 hover:bg-white/10'
                  }`}
                >
                  <MoonIcon size={14} />
                  <span>Cyber Dark</span>
                </button>
                <button
                  onClick={() => handleThemeChange('sky')}
                  className={`px-3 py-1.5 rounded-xl font-bold flex items-center gap-1.5 transition-all ${
                    themeMode === 'sky'
                      ? 'bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/30'
                      : 'bg-white/5 text-slate-300 hover:bg-white/10'
                  }`}
                >
                  <SunIcon size={14} />
                  <span>Sky Light</span>
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-200">Animation Intensity</div>
                <div className="text-[11px] text-slate-400">Adjust floating avatar GPU framerate & aura pulse</div>
              </div>
              <input type="range" min="0.2" max="1.0" step="0.1" defaultValue="0.8" className="accent-cyan-400 w-32" />
            </div>
          </div>
        </div>

        {/* Behavior & Windows Integration */}
        <div className="cyber-card rounded-3xl p-6 space-y-4">
          <h3 className="text-sm font-bold flex items-center gap-2 border-b border-white/10 pb-3">
            <SettingsIcon size={18} className="text-purple-400" />
            <span>Desktop Behavior & Overlay</span>
          </h3>

          <div className="space-y-4 text-xs">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-200">Start Genie Companion with Windows</div>
                <div className="text-[11px] text-slate-400">Launch background desktop companion at boot</div>
              </div>
              <ToggleSwitch active={startWithWindows} onChange={() => setStartWithWindows(!startWithWindows)} />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-200">Edge Magnetic Snapping</div>
                <div className="text-[11px] text-slate-400">Snap companion smoothly to desktop screen boundaries</div>
              </div>
              <ToggleSwitch active={edgeSnapping} onChange={() => setEdgeSnapping(!edgeSnapping)} />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-200">Proactive Assistance Cards</div>
                <div className="text-[11px] text-slate-400">Offer non-intrusive AI suggestions during tasks</div>
              </div>
              <ToggleSwitch active={proactiveEnabled} onChange={() => setProactiveEnabled(!proactiveEnabled)} />
            </div>
          </div>
        </div>

        {/* Privacy & Sensors */}
        <div className="cyber-card rounded-3xl p-6 space-y-4 lg:col-span-2">
          <h3 className="text-sm font-bold flex items-center gap-2 border-b border-white/10 pb-3">
            <ShieldIcon size={18} className="text-emerald-400" />
            <span>Privacy Center & Sensor Access</span>
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <PermissionCard
              title="Microphone Access"
              subtitle="Voice input for wake word & conversation"
              active={micEnabled}
              onToggle={() => setMicEnabled(!micEnabled)}
              icon={<MicIcon size={20} className="text-cyan-400" />}
            />
            <PermissionCard
              title="Camera Vision"
              subtitle="Webcam vision for object & scene analysis"
              active={cameraEnabled}
              onToggle={() => setCameraEnabled(!cameraEnabled)}
              icon={<CameraIcon size={20} className="text-purple-400" />}
            />
            <PermissionCard
              title="Screen Awareness"
              subtitle="Context engine app & error identification"
              active={screenEnabled}
              onToggle={() => setScreenEnabled(!screenEnabled)}
              icon={<EyeIcon size={20} className="text-emerald-400" />}
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
        active ? 'bg-cyan-500' : 'bg-slate-700'
      }`}
    >
      <div
        className={`bg-slate-950 w-4 h-4 rounded-full shadow-md transform transition-transform ${
          active ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </button>
  );
}

function PermissionCard({ title, subtitle, active, onToggle, icon }: { title: string; subtitle: string; active: boolean; onToggle: () => void; icon: React.ReactNode }) {
  return (
    <div className="p-4 rounded-2xl bg-white/5 border border-white/10 flex flex-col justify-between space-y-3">
      <div className="flex items-center justify-between">
        <div>{icon}</div>
        <ToggleSwitch active={active} onChange={onToggle} />
      </div>
      <div>
        <div className="font-bold text-slate-200">{title}</div>
        <div className="text-[11px] text-slate-400 mt-0.5">{subtitle}</div>
      </div>
    </div>
  );
}
