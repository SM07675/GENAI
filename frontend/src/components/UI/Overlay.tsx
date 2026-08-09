import { motion } from 'framer-motion';
import { AssistantState, SettingsConfig } from '../../types';
import { MicrophoneButton } from '../Microphone/MicrophoneButton';
import { FloatingInput } from '../Typing/FloatingInput';
import { SettingsModal } from '../Settings/SettingsModal';

interface OverlayProps {
  assistantState: AssistantState;
  onMicClick: () => void;
  isTypingOpen: boolean;
  onToggleTyping: () => void;
  onCloseTyping: () => void;
  onSendText: (text: string) => void;
  isSettingsOpen: boolean;
  onToggleSettings: () => void;
  onCloseSettings: () => void;
  settings: SettingsConfig;
  onUpdateSettings: (newSettings: Partial<SettingsConfig>) => void;
  onChangeState: (state: AssistantState) => void;
  availableClips: string[];
  audioLevel?: number;
  isBackendConnected?: boolean;
}

export function Overlay({
  assistantState,
  onMicClick,
  isTypingOpen,
  onToggleTyping,
  onCloseTyping,
  onSendText,
  isSettingsOpen,
  onToggleSettings,
  onCloseSettings,
  settings,
  onUpdateSettings,
  onChangeState,
  availableClips,
  audioLevel,
  isBackendConnected = true
}: OverlayProps) {
  return (
    <div className="fixed inset-0 z-30 pointer-events-none flex flex-col justify-between p-6 select-none">
      {/* Top Bar - Left Wake-Word Badge & Right Settings Icon */}
      <div className="flex items-center justify-between w-full">
        {/* Top Left Subtle Hands-Free Status */}
        <div className="pointer-events-auto flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-950/60 border border-cyan-500/20 backdrop-blur-md text-xs font-medium text-cyan-200/80 shadow-lg shadow-cyan-500/10">
          <div className={`w-2 h-2 rounded-full ${isBackendConnected ? 'bg-cyan-400 animate-pulse' : 'bg-amber-400'}`} />
          <span>Say <strong className="text-cyan-300 font-semibold">"Hey Genie"</strong></span>
        </div>

        {/* Top Right Settings Icon Only */}
        <motion.button
          onClick={onToggleSettings}
          whileHover={{ scale: 1.1, rotate: 45 }}
          whileTap={{ scale: 0.9 }}
          className="pointer-events-auto flex items-center justify-center w-11 h-11 rounded-2xl bg-slate-950/60 border border-cyan-500/20 backdrop-blur-xl text-cyan-300/80 hover:text-cyan-200 hover:border-cyan-400/50 shadow-lg shadow-cyan-500/10 transition-all duration-300"
          title="System Settings"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.8}
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </motion.button>
      </div>

      {/* Floating Input Component when Typing button is clicked */}
      <div className="pointer-events-auto">
        <FloatingInput
          isOpen={isTypingOpen}
          onClose={onCloseTyping}
          onSubmit={onSendText}
        />
      </div>

      {/* Settings Modal Component when Settings button is clicked */}
      <div className="pointer-events-auto">
        <SettingsModal
          isOpen={isSettingsOpen}
          onClose={onCloseSettings}
          settings={settings}
          onUpdateSettings={onUpdateSettings}
          assistantState={assistantState}
          onChangeState={onChangeState}
          availableClips={availableClips}
        />
      </div>

      {/* Bottom Bar Controls: Bottom Center Microphone & Bottom Right Typing Button */}
      <div className="relative flex items-center justify-between w-full">
        {/* Left Spacer for symmetry */}
        <div className="w-12 h-12" />

        {/* Bottom Center: Large Animated Circular Microphone */}
        <div className="pointer-events-auto">
          <MicrophoneButton
            state={assistantState}
            onClick={onMicClick}
            audioLevel={audioLevel}
          />
        </div>

        {/* Bottom Right: Single Typing Toggle Button */}
        <div className="pointer-events-auto">
          <motion.button
            onClick={onToggleTyping}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            className={`flex items-center justify-center w-12 h-12 rounded-2xl border backdrop-blur-xl transition-all duration-300 shadow-lg ${
              isTypingOpen
                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200 shadow-cyan-500/20'
                : 'bg-slate-950/60 border-cyan-500/20 text-cyan-300/80 hover:text-cyan-200 hover:border-cyan-400/50 shadow-cyan-500/10'
            }`}
            title="Type a message"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.8}
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
              />
            </svg>
          </motion.button>
        </div>
      </div>
    </div>
  );
}
