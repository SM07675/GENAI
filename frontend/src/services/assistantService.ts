import { AssistantState, AssistantServiceListener } from '../types';

/**
 * Service singleton ready for future integrations with:
 * - Real-time Voice Recognition (STT)
 * - LLM / AI Response APIs
 * - Emotion & Sentiment Detection
 * - TTS Audio Wave Synchronization
 */
export class AssistantService {
  private static instance: AssistantService;
  private listeners: Set<AssistantServiceListener> = new Set();
  private currentState: AssistantState = 'idle';

  private constructor() {}

  public static getInstance(): AssistantService {
    if (!AssistantService.instance) {
      AssistantService.instance = new AssistantService();
    }
    return AssistantService.instance;
  }

  public subscribe(listener: AssistantServiceListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  public setState(newState: AssistantState): void {
    this.currentState = newState;
    this.listeners.forEach((l) => l.onStateChange?.(newState));
  }

  public getState(): AssistantState {
    return this.currentState;
  }

  public emitAudioLevel(level: number): void {
    this.listeners.forEach((l) => l.onAudioLevel?.(level));
  }

  public emitTranscript(text: string): void {
    this.listeners.forEach((l) => l.onTranscript?.(text));
  }
}

export const assistantService = AssistantService.getInstance();
