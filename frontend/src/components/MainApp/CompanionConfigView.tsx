/**
 * CompanionConfigView.tsx — Companion Configuration & Preview Page inside Main App.
 */
import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useCompanionStore } from '../../store/companionStore';
import { useCompanion } from '../../hooks/useCompanion';
import GenieFace from '../GenieFace/GenieFace';
import {
  SparklesIcon,
  SettingsIcon,
  MicIcon,
  EyeIcon,
  ShieldIcon,
  CheckIcon,
} from '../UI/Icons';

export default function CompanionConfigView() {
  const companion = useCompanionStore();
  const { startCompanion, stopCompanion } = useCompanion();

  const [previewEmotion, setPreviewEmotion] = useState<string>('idle');
  const [clickThrough, setClickThrough] = useState<boolean>(false);
  const [positionPreset, setPositionPreset] = useState<string>('free');
  const [selectedVoice, setSelectedVoice] = useState<string>('en-US-AriaNeural');

  const isCompanionActive = companion.mode === 'active';
  const isTransitioning = companion.mode === 'starting' || companion.mode === 'stopping';

  const handleToggleCompanionMode = () => {
    if (companion.mode === 'off') {
      startCompanion();
    } else if (companion.mode === 'active' || companion.mode === 'paused') {
      stopCompanion();
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Desktop Companion Configuration
          </h1>
          <p className="text-xs md:text-sm font-medium text-slate-400 mt-1">
            Customize the floating desktop overlay avatar, behaviors, position presets, and permissions.
          </p>
        </div>

        <button
          onClick={handleToggleCompanionMode}
          disabled={isTransitioning}
          className={`px-5 py-2.5 rounded-2xl text-xs font-bold shadow-lg transition-all flex items-center gap-2 ${
            isCompanionActive
              ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-cyan-500/25 hover:from-cyan-400 hover:to-blue-500'
              : isTransitioning
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30 cursor-wait'
              : 'bg-white/10 hover:bg-white/15 text-slate-200 border border-white/15'
          }`}
        >
          <SparklesIcon size={16} />
          <span>Companion Mode: {companion.mode.toUpperCase()}</span>
        </button>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Live Robot Avatar Preview Card */}
        <div className="lg:col-span-5 cyber-glass rounded-3xl p-6 flex flex-col items-center justify-between space-y-6">
          <div className="w-full flex items-center justify-between border-b border-white/10 pb-3">
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-2">
              <EyeIcon size={14} />
              <span>Live Avatar Preview</span>
            </span>
            <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Active</span>
            </span>
          </div>

          {/* Avatar Display */}
          <div className="py-4 flex flex-col items-center">
            <GenieFace size={220} showBody={true} minimal={false} />
          </div>

          {/* Expression Tester */}
          <div className="w-full space-y-3">
            <span className="text-xs font-bold text-slate-300">Test Avatar Emotional Expression</span>
            <div className="grid grid-cols-4 gap-2">
              {['idle', 'listening', 'thinking', 'speaking', 'happy', 'excited', 'confused', 'sleeping'].map((emo) => (
                <button
                  key={emo}
                  onClick={() => setPreviewEmotion(emo)}
                  className={`py-2 px-2 rounded-xl text-[11px] font-semibold capitalize border transition-all ${
                    previewEmotion === emo
                      ? 'bg-cyan-500 text-slate-950 font-bold border-cyan-400 shadow-md shadow-cyan-500/30'
                      : 'bg-white/5 text-slate-300 border-white/10 hover:bg-white/10'
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
          <div className="cyber-card rounded-3xl p-6 space-y-4">
            <h3 className="text-sm font-bold flex items-center gap-2 border-b border-white/10 pb-3">
              <SparklesIcon size={18} className="text-cyan-400" />
              <span>Appearance & Display Mode</span>
            </h3>

            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-200">Display Size Mode</div>
                  <div className="text-[11px] text-slate-400">Choose how Genie renders on screen</div>
                </div>
                <select
                  value={companion.displayMode}
                  onChange={(e) => companion.setDisplayMode(e.target.value as any)}
                  className="px-3 py-2 rounded-xl bg-slate-900 border border-cyan-500/30 text-cyan-300 font-bold outline-none cursor-pointer"
                >
                  <option value="floating">Floating (Normal)</option>
                  <option value="full">Expanded Card</option>
                  <option value="mini">Mini Orb</option>
                  <option value="invisible">Voice Only (Invisible)</option>
                </select>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-200">Avatar Glow Intensity</div>
                  <div className="text-[11px] text-slate-400">Aura brightness and shadow spread</div>
                </div>
                <input type="range" min="0.1" max="1.0" step="0.1" defaultValue="0.7" className="accent-cyan-400 w-36" />
              </div>
            </div>
          </div>

          {/* Behavior Settings */}
          <div className="cyber-card rounded-3xl p-6 space-y-4">
            <h3 className="text-sm font-bold flex items-center gap-2 border-b border-white/10 pb-3">
              <SettingsIcon size={18} className="text-purple-400" />
              <span>Desktop Overlay Behavior</span>
            </h3>

            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-200">Always on Top</div>
                  <div className="text-[11px] text-slate-400">Floats above Chrome, VS Code, and desktop windows</div>
                </div>
                <ToggleSwitch active={true} onChange={() => {}} />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-200">Passive Click-Through</div>
                  <div className="text-[11px] text-slate-400">Clicks pass through transparent avatar boundaries</div>
                </div>
                <ToggleSwitch active={clickThrough} onChange={() => setClickThrough(!clickThrough)} />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-200">Positioning Mode</div>
                  <div className="text-[11px] text-slate-400">Screen corner anchoring or free dragging</div>
                </div>
                <select
                  value={positionPreset}
                  onChange={(e) => setPositionPreset(e.target.value)}
                  className="px-3 py-2 rounded-xl bg-slate-900 border border-white/15 text-slate-200 font-bold outline-none cursor-pointer"
                >
                  <option value="free">Free Dragging</option>
                  <option value="top-right">Top Right Corner</option>
                  <option value="bottom-right">Bottom Right Corner</option>
                  <option value="top-left">Top Left Corner</option>
                </select>
              </div>
            </div>
          </div>

          {/* Voice & Permissions */}
          <div className="cyber-card rounded-3xl p-6 space-y-4">
            <h3 className="text-sm font-bold flex items-center gap-2 border-b border-white/10 pb-3">
              <MicIcon size={18} className="text-emerald-400" />
              <span>Voice Model & Wake Word</span>
            </h3>

            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-200">Wake Word Trigger</span>
                <span className="text-cyan-400 font-bold bg-cyan-500/10 border border-cyan-500/30 px-3 py-1 rounded-xl">"Hey Genie"</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-200">TTS Voice Engine</span>
                <select
                  value={selectedVoice}
                  onChange={(e) => setSelectedVoice(e.target.value)}
                  className="px-3 py-2 rounded-xl bg-slate-900 border border-white/15 text-slate-200 font-bold outline-none cursor-pointer"
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
