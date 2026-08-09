/**
 * CompanionConfigView.tsx — Companion Configuration & Preview Page inside Main App.
 *
 * Per spec §45 & §46:
 * This is the configuration/preview mode inside the main Electron window.
 * Shows a large live preview of the Genie robot avatar, state selector,
 * appearance options, behavior (click-through, always-on-top, position presets),
 * voice settings, and permission controls.
 */
import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useCompanionStore } from '../../store/companionStore';
import GenieFace from '../GenieFace/GenieFace';

export default function CompanionConfigView() {
  const companion = useCompanionStore();

  const [previewEmotion, setPreviewEmotion] = useState<string>('idle');
  const [clickThrough, setClickThrough] = useState<boolean>(false);
  const [edgeSnapping, setEdgeSnapping] = useState<boolean>(true);
  const [positionPreset, setPositionPreset] = useState<string>('free');
  const [selectedVoice, setSelectedVoice] = useState<string>('en-US-AriaNeural');

  const isCompanionActive = companion.mode !== 'off';

  const handleToggleCompanionMode = () => {
    companion.setMode(isCompanionActive ? 'off' : 'active');
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Desktop Companion Configuration
          </h1>
          <p className="text-sm font-medium text-slate-500 mt-1">
            Customize the floating desktop overlay avatar, behaviors, and permissions.
          </p>
        </div>

        <button
          onClick={handleToggleCompanionMode}
          className={`px-5 py-2.5 rounded-xl text-xs font-bold shadow-md transition-all flex items-center gap-2 ${
            isCompanionActive
              ? 'bg-sky-500 text-white shadow-sky-500/25 hover:bg-sky-600'
              : 'bg-slate-900 text-white hover:bg-slate-800'
          }`}
        >
          <span>✨</span>
          <span>Desktop Companion: {companion.mode.toUpperCase()}</span>
        </button>
      </div>

      {/* Main Grid: Preview Card + Settings Tabs */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Large Live Robot Avatar Preview Card */}
        <div className="lg:col-span-5 sky-glass rounded-3xl p-6 flex flex-col items-center justify-between space-y-6">
          <div className="w-full flex items-center justify-between border-b border-sky-200/60 pb-3">
            <span className="text-xs font-bold text-sky-700 uppercase tracking-wide">
              Live Avatar Preview
            </span>
            <span className="text-xs font-semibold text-slate-500">
              ● Active State
            </span>
          </div>

          {/* Avatar Display */}
          <div className="py-4 flex flex-col items-center">
            <GenieFace size={220} showBody={true} minimal={false} />
          </div>

          {/* Emotion State Tester Buttons */}
          <div className="w-full space-y-2">
            <span className="text-xs font-bold text-slate-700">Test Emotional Expression</span>
            <div className="grid grid-cols-3 gap-2">
              {['idle', 'listening', 'thinking', 'speaking', 'happy', 'excited', 'confused', 'sleeping'].map((emo) => (
                <button
                  key={emo}
                  onClick={() => setPreviewEmotion(emo)}
                  className={`py-1.5 px-2 rounded-xl text-[11px] font-semibold capitalize border transition-all ${
                    previewEmotion === emo
                      ? 'bg-sky-500 text-white border-sky-500 shadow-sm'
                      : 'bg-white/80 text-slate-700 border-sky-200 hover:bg-sky-50'
                  }`}
                >
                  {emo}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Companion Settings Controls */}
        <div className="lg:col-span-7 space-y-6">
          {/* Appearance Settings */}
          <div className="sky-glass-card rounded-2xl p-6 space-y-4">
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2 border-b border-sky-200/60 pb-3">
              <span>🎨</span> Appearance & Character
            </h3>

            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-700">Display Size Mode</span>
                <select
                  value={companion.displayMode}
                  onChange={(e) => companion.setDisplayMode(e.target.value as any)}
                  className="px-3 py-1.5 rounded-xl bg-white border border-sky-200 text-slate-800 font-semibold outline-none"
                >
                  <option value="floating">Floating (Normal)</option>
                  <option value="full">Expanded Card</option>
                  <option value="mini">Mini Orb</option>
                  <option value="invisible">Voice Only (Invisible)</option>
                </select>
              </div>

              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-700">Avatar Glow Intensity</span>
                <input type="range" min="0.1" max="1.0" step="0.1" defaultValue="0.6" className="accent-sky-500 w-36" />
              </div>

              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-700">Lip-Sync Mouth Animation</span>
                <span className="text-sky-600 font-bold">Web Audio Analyser Active</span>
              </div>
            </div>
          </div>

          {/* Behavior Settings */}
          <div className="sky-glass-card rounded-2xl p-6 space-y-4">
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2 border-b border-sky-200/60 pb-3">
              <span>⚙</span> Desktop Behavior & Overlay
            </h3>

            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-700">Always on Top</div>
                  <div className="text-[11px] text-slate-500">Floats above Chrome, VS Code, and games</div>
                </div>
                <ToggleSwitch active={true} onChange={() => {}} />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-700">Passive Click-Through</div>
                  <div className="text-[11px] text-slate-500">Mouse clicks pass through transparent regions</div>
                </div>
                <ToggleSwitch active={clickThrough} onChange={() => setClickThrough(!clickThrough)} />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-700">Positioning Mode</div>
                  <div className="text-[11px] text-slate-500">Screen corner anchoring or free drag</div>
                </div>
                <select
                  value={positionPreset}
                  onChange={(e) => setPositionPreset(e.target.value)}
                  className="px-3 py-1.5 rounded-xl bg-white border border-sky-200 text-slate-800 font-semibold outline-none"
                >
                  <option value="free">Free Dragging</option>
                  <option value="top-right">Top Right Corner</option>
                  <option value="bottom-right">Bottom Right Corner</option>
                  <option value="top-left">Top Left Corner</option>
                </select>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-700">Non-Intrusive Focus</div>
                  <div className="text-[11px] text-slate-500">Never steals keyboard focus when appearing</div>
                </div>
                <ToggleSwitch active={true} onChange={() => {}} />
              </div>
            </div>
          </div>

          {/* Voice & Permissions */}
          <div className="sky-glass-card rounded-2xl p-6 space-y-4">
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2 border-b border-sky-200/60 pb-3">
              <span>🎤</span> Voice & Sensor Permissions
            </h3>

            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-700">Wake Word</span>
                <span className="text-sky-700 font-bold bg-sky-100 px-2.5 py-1 rounded-lg">"Hey Genie"</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-700">TTS Voice Model</span>
                <select
                  value={selectedVoice}
                  onChange={(e) => setSelectedVoice(e.target.value)}
                  className="px-3 py-1.5 rounded-xl bg-white border border-sky-200 text-slate-800 font-semibold outline-none"
                >
                  <option value="en-US-AriaNeural">Edge TTS — Aria Neural (US)</option>
                  <option value="en-US-GuyNeural">Edge TTS — Guy Neural (US)</option>
                  <option value="en-GB-SoniaNeural">Edge TTS — Sonia Neural (UK)</option>
                </select>
              </div>
            </div>
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
