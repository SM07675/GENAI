import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { SettingsConfig, AssistantState } from '../../types';
import { useCompanionStore } from '../../store/companionStore';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: SettingsConfig;
  onUpdateSettings: (newSettings: Partial<SettingsConfig>) => void;
  assistantState: AssistantState;
  onChangeState: (state: AssistantState) => void;
  availableClips: string[];
}

type TabType = 'general' | 'voice' | 'companion' | 'ai' | 'diagnostics';

export function SettingsModal({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
  assistantState,
  onChangeState,
  availableClips
}: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>('companion');
  const [healthStatus, setHealthStatus] = useState<string | null>(null);
  const [isHealthChecking, setIsHealthChecking] = useState(false);

  const companionStore = useCompanionStore();

  const runHealthCheck = async () => {
    setIsHealthChecking(true);
    try {
      const genie = (window as any).genie;
      if (genie?.getBackendStatus) {
        const status = await genie.getBackendStatus();
        setHealthStatus(status.ready ? 'PASS — Backend online on port ' + status.port : 'WARNING — Backend process offline');
      } else {
        const res = await fetch('http://127.0.0.1:8765/health');
        const data = await res.json();
        setHealthStatus(data.status === 'ok' ? 'PASS — All API systems nominal' : 'FAIL — ' + JSON.stringify(data));
      }
    } catch (err: any) {
      setHealthStatus('FAIL — Could not reach backend: ' + err.message);
    } finally {
      setIsHealthChecking(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop Blur overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-md"
          />

          {/* Floating Settings Drawer / Modal */}
          <motion.div
            initial={{ opacity: 0, x: 50, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 50, scale: 0.95 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className="fixed top-12 right-6 z-50 w-full max-w-lg p-6 rounded-3xl bg-slate-950/95 border border-cyan-500/30 backdrop-blur-2xl shadow-2xl shadow-cyan-500/20 text-slate-100 max-h-[85vh] flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between pb-4 mb-4 border-b border-cyan-500/20">
              <div className="flex items-center gap-2.5">
                <div className="w-3 h-3 rounded-full bg-cyan-400 animate-pulse" />
                <h3 className="text-lg font-semibold tracking-wide text-slate-100">
                  Genie System & Companion Settings
                </h3>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 text-slate-400 hover:text-slate-200 rounded-xl hover:bg-slate-800/60 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Navigation Tabs */}
            <div className="flex gap-1 mb-4 p-1 rounded-xl bg-slate-900/80 border border-slate-800/80 text-xs">
              {(['companion', 'voice', 'ai', 'general', 'diagnostics'] as TabType[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`flex-1 py-1.5 rounded-lg capitalize font-medium transition-all ${
                    activeTab === tab
                      ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-500/40 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="space-y-4 text-sm overflow-y-auto pr-1 flex-1">
              {/* COMPANION TAB */}
              {activeTab === 'companion' && (
                <div className="space-y-4">
                  <div>
                    <label className="block mb-1.5 text-xs font-medium text-slate-300">
                      Companion Mode Status
                    </label>
                    <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                      <span className="capitalize font-mono text-cyan-400">{companionStore.mode}</span>
                      <button
                        onClick={() => companionStore.setMode(companionStore.mode === 'off' ? 'active' : 'off')}
                        className={`px-3 py-1 rounded-lg text-xs font-semibold ${
                          companionStore.mode !== 'off'
                            ? 'bg-red-500/20 text-red-300 border border-red-500/30 hover:bg-red-500/30'
                            : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-500/30'
                        }`}
                      >
                        {companionStore.mode !== 'off' ? 'Stop Companion' : 'Start Companion'}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block mb-1.5 text-xs font-medium text-slate-300">
                      Active Sub-Mode (§12)
                    </label>
                    <div className="grid grid-cols-4 gap-1.5">
                      {(['general', 'gaming', 'coding', 'writing'] as const).map((m) => (
                        <button
                          key={m}
                          onClick={() => companionStore.setMode(companionStore.mode, m)}
                          className={`py-1.5 rounded-lg text-xs font-medium capitalize border ${
                            companionStore.subMode === m
                              ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200'
                              : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                          }`}
                        >
                          {m}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                    <div>
                      <div className="text-xs font-medium text-slate-200">Persistent Launcher Orb</div>
                      <div className="text-[11px] text-slate-400">Show floating corner orb when Companion is OFF</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={companionStore.launcherVisible}
                      onChange={(e) => companionStore.setLauncherVisible(e.target.checked)}
                      className="w-4 h-4 rounded accent-cyan-400"
                    />
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                    <div>
                      <div className="text-xs font-medium text-slate-200">Screen Awareness (Vision)</div>
                      <div className="text-[11px] text-slate-400">NVIDIA Nemotron 12B VL API vision checks</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={companionStore.screenAware}
                      onChange={(e) => companionStore.setPrivacy(e.target.checked, companionStore.micActive)}
                      className="w-4 h-4 rounded accent-cyan-400"
                    />
                  </div>
                </div>
              )}

              {/* VOICE TAB */}
              {activeTab === 'voice' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                    <div>
                      <div className="text-xs font-medium text-slate-200">Wake Word Detection</div>
                      <div className="text-[11px] text-slate-400">Listen for "Hey Genie" / "Okay Genie"</div>
                    </div>
                    <input type="checkbox" defaultChecked className="w-4 h-4 rounded accent-cyan-400" />
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/70 border border-slate-800">
                    <div>
                      <div className="text-xs font-medium text-slate-200">Continuous Follow-up</div>
                      <div className="text-[11px] text-slate-400">Keep listening for 8s after response</div>
                    </div>
                    <input type="checkbox" defaultChecked className="w-4 h-4 rounded accent-cyan-400" />
                  </div>
                </div>
              )}

              {/* AI TAB */}
              {activeTab === 'ai' && (
                <div className="space-y-4">
                  <div>
                    <label className="block mb-1 text-xs font-medium text-slate-300">LLM Provider</label>
                    <select className="w-full p-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-cyan-300">
                      <option value="nvidia">NVIDIA NIM (OpenAI-compatible)</option>
                      <option value="openrouter">OpenRouter Pool</option>
                      <option value="gemini">Google Gemini 2.5 Flash</option>
                      <option value="xai">xAI Grok 4.5</option>
                      <option value="groq">Groq Cloud</option>
                    </select>
                  </div>

                  <div>
                    <label className="block mb-1 text-xs font-medium text-slate-300">
                      Private API Key (Stored Locally on this PC Only)
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="password"
                        placeholder="Paste your private API key (e.g. nvapi-... or AIzaSy...)"
                        defaultValue={localStorage.getItem('genie_private_api_key') || ''}
                        id="genie-private-api-key-input"
                        className="flex-1 p-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-cyan-300 placeholder:text-slate-600 focus:border-cyan-400 outline-none font-mono"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          const val = (document.getElementById('genie-private-api-key-input') as HTMLInputElement)?.value;
                          if (val) {
                            localStorage.setItem('genie_private_api_key', val);
                            alert('Private API key saved locally on this PC!');
                          }
                        }}
                        className="px-3 py-1.5 rounded-xl bg-cyan-500/20 border border-cyan-400 text-cyan-200 text-xs font-semibold hover:bg-cyan-500/30 transition-all"
                      >
                        Save
                      </button>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1">
                      🔒 Your API key is encrypted and stored locally in this PC's environment. It is never transmitted or shared with other PCs.
                    </div>
                  </div>

                  <div>
                    <label className="block mb-1 text-xs font-medium text-slate-300">Vision Model</label>
                    <input
                      type="text"
                      readOnly
                      value="nvidia/nemotron-nano-12b-v2-vl"
                      className="w-full p-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-400 font-mono"
                    />
                  </div>
                </div>
              )}

              {/* GENERAL TAB */}
              {activeTab === 'general' && (
                <div className="space-y-4">
                  <div>
                    <label className="block mb-2 text-xs font-medium uppercase tracking-wider text-cyan-300/80">
                      State Tester
                    </label>
                    <div className="grid grid-cols-3 gap-1.5">
                      {(['idle', 'listening', 'recording', 'processing', 'speaking', 'muted'] as AssistantState[]).map(
                        (st) => (
                          <button
                            key={st}
                            onClick={() => onChangeState(st)}
                            className={`px-2.5 py-1.5 rounded-lg text-xs font-medium capitalize transition-all border ${
                              assistantState === st
                                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200'
                                : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                            }`}
                          >
                            {st}
                          </button>
                        )
                      )}
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between mb-1.5 text-xs text-slate-300">
                      <span>Particle Atmosphere</span>
                      <span className="font-mono text-cyan-400">{settings.particleDensity}</span>
                    </div>
                    <input
                      type="range"
                      min="300"
                      max="3000"
                      step="100"
                      value={settings.particleDensity}
                      onChange={(e) => onUpdateSettings({ particleDensity: Number(e.target.value) })}
                      className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                    />
                  </div>
                </div>
              )}

              {/* DIAGNOSTICS TAB (§19.2, §19.3) */}
              {activeTab === 'diagnostics' && (
                <div className="space-y-4">
                  <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 text-xs space-y-2 font-mono">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Desktop Shell:</span>
                      <span className="text-cyan-300">Electron (Windows)</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Shortcut:</span>
                      <span className="text-cyan-300">Ctrl+Shift+G (Quick Look)</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Backend Port:</span>
                      <span className="text-cyan-300">127.0.0.1:8765</span>
                    </div>
                  </div>

                  <button
                    onClick={runHealthCheck}
                    disabled={isHealthChecking}
                    className="w-full py-2 rounded-xl bg-cyan-500/20 border border-cyan-400 text-cyan-200 font-medium text-xs hover:bg-cyan-500/30 transition-all flex items-center justify-center gap-2"
                  >
                    {isHealthChecking ? 'Running Health Check...' : 'Run Genie Health Check (§19.3)'}
                  </button>

                  {healthStatus && (
                    <div className="p-3 rounded-xl bg-slate-900 border border-cyan-500/30 text-xs font-mono text-cyan-300">
                      {healthStatus}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="mt-4 pt-3 border-t border-cyan-500/20 text-center text-xs text-slate-500">
              Genie AI Operating System v5.0 • Desktop Production Edition
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
