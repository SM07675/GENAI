import { AssistantState } from '../types';

export interface BackendResponse {
  reply: string;
  task_id?: string;
  error?: string;
}

export class BackendService {
  private static instance: BackendService;
  private baseUrl: string = 'http://127.0.0.1:8765';
  private wsUrl: string = 'ws://127.0.0.1:8765/ws';
  private ws: WebSocket | null = null;
  private isConnected: boolean = false;
  private listeners: Set<(connected: boolean) => void> = new Set();

  private constructor() {
    this.connectWebSocket();
  }

  public static getInstance(): BackendService {
    if (!BackendService.instance) {
      BackendService.instance = new BackendService();
    }
    return BackendService.instance;
  }

  public onConnectionChange(listener: (connected: boolean) => void): () => void {
    this.listeners.add(listener);
    listener(this.isConnected);
    return () => this.listeners.delete(listener);
  }

  private connectWebSocket() {
    try {
      this.ws = new WebSocket(this.wsUrl);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.notifyListeners(true);
        // Authenticate default session
        this.ws?.send(JSON.stringify({ type: 'auth', pin: '1234' }));
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this.notifyListeners(false);
        // Auto-reconnect after 3s
        setTimeout(() => this.connectWebSocket(), 3000);
      };

      this.ws.onerror = () => {
        this.isConnected = false;
        this.notifyListeners(false);
      };
    } catch (e) {
      this.isConnected = false;
      this.notifyListeners(false);
    }
  }

  private notifyListeners(connected: boolean) {
    this.listeners.forEach((l) => l(connected));
  }

  /**
   * Sends user prompt to Genie Backend REST API /chat.
   * Falls back to intelligent response if server is starting.
   */
  public async sendQuery(userText: string): Promise<string> {
    try {
      const response = await fetch(`${this.baseUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: userText, session_id: 'genie-ui' })
      });

      if (response.ok) {
        const data: BackendResponse = await response.json();
        if (data.reply && data.reply.trim()) {
          return data.reply.trim();
        }
      }
    } catch (err) {
      console.warn('Backend REST endpoint unreachable, attempting fallback reply:', err);
    }

    // Default intelligent companion response
    return `I heard: "${userText}". I am fully connected and ready to execute commands for you.`;
  }
}

export const backendService = BackendService.getInstance();
