import { useState, useCallback } from 'react';
import { AssistantState, SettingsConfig } from '../types';
import { useVoiceInteraction } from './useVoiceInteraction';

export interface UseAssistantStateReturn {
  state: AssistantState;
  setState: (state: AssistantState) => void;
  isTypingOpen: boolean;
  setIsTypingOpen: (open: boolean) => void;
  isSettingsOpen: boolean;
  setIsSettingsOpen: (open: boolean) => void;
  settings: SettingsConfig;
  updateSettings: (newSettings: Partial<SettingsConfig>) => void;
  handleMicClick: () => void;
  handleTextSubmit: (text: string) => void;
  audioLevel: number;
  transcript: string;
}

export function useAssistantState(): UseAssistantStateReturn {
  const [state, setState] = useState<AssistantState>('idle');
  const [isTypingOpen, setIsTypingOpen] = useState<boolean>(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  const [settings, setSettings] = useState<SettingsConfig>({
    particleDensity: 1400,
    glowIntensity: 1.0,
    cameraSpeed: 0.5,
    audioSens: 1.0,
    bloomEnabled: true,
    volume: 0.8,
    autoRotate: false
  });

  const updateSettings = useCallback((newSettings: Partial<SettingsConfig>) => {
    setSettings((prev) => ({ ...prev, ...newSettings }));
  }, []);

  const handleStateChange = useCallback((newState: AssistantState) => {
    setState(newState);
  }, []);

  // Voice Interaction Hook
  const {
    audioLevel,
    transcript,
    startListening,
    stopListening,
    speakText
  } = useVoiceInteraction(state, handleStateChange);

  // Mic Click Trigger
  const handleMicClick = useCallback(() => {
    if (state === 'idle' || state === 'muted') {
      startListening();
    } else if (state === 'listening' || state === 'recording') {
      stopListening();
      setState('idle');
    } else if (state === 'speaking') {
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      setState('idle');
    } else {
      setState('idle');
    }
  }, [state, startListening, stopListening]);

  // Floating Text Submit Trigger
  const handleTextSubmit = useCallback(
    (text: string) => {
      if (!text.trim()) return;

      // Automatically close floating input
      setIsTypingOpen(false);
      setState('processing');

      setTimeout(() => {
        const response = `I received your message: "${text}". I am ready for your next request.`;
        speakText(response);
      }, 1000);
    },
    [speakText]
  );

  return {
    state,
    setState,
    isTypingOpen,
    setIsTypingOpen,
    isSettingsOpen,
    setIsSettingsOpen,
    settings,
    updateSettings,
    handleMicClick,
    handleTextSubmit,
    audioLevel,
    transcript
  };
}
