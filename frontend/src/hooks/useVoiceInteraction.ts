import { useEffect, useRef, useState, useCallback } from 'react';
import { AssistantState } from '../types';
import { backendService } from '../services/backendService';

export interface UseVoiceInteractionReturn {
  audioLevel: number;
  transcript: string;
  startListening: () => void;
  stopListening: () => void;
  speakText: (text: string, onEnd?: () => void) => void;
  isSupported: boolean;
  isBackendConnected: boolean;
}

export function useVoiceInteraction(
  assistantState: AssistantState,
  onStateChange: (newState: AssistantState) => void
): UseVoiceInteractionReturn {
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [transcript, setTranscript] = useState<string>('');
  const [isSupported, setIsSupported] = useState<boolean>(true);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);

  // Audio Context & Analyser for physical mic input volume
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const animFrameRef = useRef<number | null>(null);

  // Speech Recognition & Synthesis references
  const recognitionRef = useRef<any>(null);
  const wakeWordRecognitionRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);
  const isListeningRef = useRef<boolean>(false);

  // Monitor Backend Connection
  useEffect(() => {
    const unsubscribe = backendService.onConnectionChange((connected) => {
      setIsBackendConnected(connected);
    });
    return unsubscribe;
  }, []);

  // Play subtle activation chime when wake word is detected
  const playWakeChime = useCallback(() => {
    try {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15); // A5
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.3);
    } catch (e) {}
  }, []);

  // Start reading physical mic volume using Web Audio API
  const startMicAudio = useCallback(async () => {
    try {
      if (micStreamRef.current) return; // Already active

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;

      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioCtxRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const updateVolume = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);

        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const average = sum / dataArray.length;
        const normalized = Math.min(1.0, average / 120);

        setAudioLevel(normalized);
        animFrameRef.current = requestAnimationFrame(updateVolume);
      };

      updateVolume();
    } catch (err) {
      console.warn('Microphone access not granted or unavailable:', err);
    }
  }, []);

  // Stop physical mic audio reading
  const stopMicAudio = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close();
      audioCtxRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  // Speech Synthesis - Genie speaks AI response out loud
  const speakText = useCallback(
    (text: string, onEnd?: () => void) => {
      if (!synthRef.current) return;

      synthRef.current.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.05;

      const voices = synthRef.current.getVoices();
      const preferredVoice =
        voices.find(
          (v) =>
            v.lang.startsWith('en') &&
            (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Samantha') || v.name.includes('Zira'))
        ) || voices.find((v) => v.lang.startsWith('en'));

      if (preferredVoice) {
        utterance.voice = preferredVoice;
      }

      utterance.onstart = () => {
        onStateChange('speaking');
      };

      utterance.onend = () => {
        onStateChange('idle');
        if (onEnd) onEnd();
      };

      utterance.onerror = () => {
        onStateChange('idle');
      };

      // Pulsing audio visualizer during speech
      let speakInterval: any = setInterval(() => {
        if (synthRef.current?.speaking) {
          setAudioLevel(0.4 + Math.random() * 0.55);
        } else {
          clearInterval(speakInterval);
          setAudioLevel(0);
        }
      }, 100);

      synthRef.current.speak(utterance);
    },
    [onStateChange]
  );

  // Initialize Primary Speech Recognition
  useEffect(() => {
    if (typeof window !== 'undefined') {
      synthRef.current = window.speechSynthesis;

      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
          isListeningRef.current = true;
          onStateChange('listening');
        };

        recognition.onresult = (event: any) => {
          let currentTranscript = '';
          for (let i = event.resultIndex; i < event.results.length; i++) {
            currentTranscript += event.results[i][0].transcript;
          }
          setTranscript(currentTranscript);
          onStateChange('recording');
        };

        recognition.onerror = (event: any) => {
          console.warn('Speech recognition error:', event.error);
          isListeningRef.current = false;
          stopMicAudio();
        };

        recognition.onend = () => {
          isListeningRef.current = false;
          stopMicAudio();
          onStateChange('processing');

          // Query Backend API for real AI response
          const capturedText = transcript.trim();
          if (capturedText) {
            backendService.sendQuery(capturedText).then((reply) => {
              speakText(reply);
            });
          } else {
            speakText("I am online. How can I help you today?");
          }
        };

        recognitionRef.current = recognition;

        // ── Wake Word Recognition Engine ("Hey Genie" / "Genie") ──
        const wakeRecognition = new SpeechRecognition();
        wakeRecognition.continuous = true;
        wakeRecognition.interimResults = true;
        wakeRecognition.lang = 'en-US';

        wakeRecognition.onresult = (event: any) => {
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const heard = event.results[i][0].transcript.toLowerCase();
            if (
              heard.includes('genie') ||
              heard.includes('hey genie') ||
              heard.includes('hello genie') ||
              heard.includes('ok genie') ||
              heard.includes('wake up')
            ) {
              wakeRecognition.stop();
              playWakeChime();
              startListening();
              break;
            }
          }
        };

        wakeRecognition.onend = () => {
          // Restart background wake-word listener if idle
          if (!isListeningRef.current && assistantState === 'idle') {
            try {
              wakeRecognition.start();
            } catch (e) {}
          }
        };

        wakeWordRecognitionRef.current = wakeRecognition;
        try {
          wakeRecognition.start();
        } catch (e) {}
      } else {
        setIsSupported(false);
      }
    }

    return () => {
      stopMicAudio();
    };
  }, [assistantState, onStateChange, playWakeChime, speakText, transcript]);

  // Trigger voice prompt capture
  const startListening = useCallback(() => {
    setTranscript('');
    startMicAudio();

    if (recognitionRef.current) {
      try {
        recognitionRef.current.start();
      } catch (err) {
        onStateChange('listening');
      }
    } else {
      // Fallback
      onStateChange('listening');
      setTimeout(() => onStateChange('recording'), 1000);
      setTimeout(() => {
        stopMicAudio();
        onStateChange('processing');
        backendService.sendQuery("Hello Genie").then((reply) => {
          speakText(reply);
        });
      }, 3000);
    }
  }, [startMicAudio, stopMicAudio, onStateChange, speakText]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (err) {}
    }
    stopMicAudio();
  }, [stopMicAudio]);

  return {
    audioLevel,
    transcript,
    startListening,
    stopListening,
    speakText,
    isSupported,
    isBackendConnected
  };
}
