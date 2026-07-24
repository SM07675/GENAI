import { secureStorage } from '../storage/SecureStorage';

export type WebSocketStatus = 'disconnected' | 'connecting' | 'connected' | 'auth_failed' | 'error';

class WebSocketClient {
  private ws: WebSocket | null = null;
  private status: WebSocketStatus = 'disconnected';
  private pingInterval: NodeJS.Timeout | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private reconnectAttempts = 0;
  
  private onStatusChangeCallbacks: Array<(status: WebSocketStatus) => void> = [];
  private onMessageCallbacks: Array<(msg: any) => void> = [];

  subscribeToStatus(callback: (status: WebSocketStatus) => void) {
    this.onStatusChangeCallbacks.push(callback);
    callback(this.status);
    return () => {
      this.onStatusChangeCallbacks = this.onStatusChangeCallbacks.filter((cb) => cb !== callback);
    };
  }

  subscribeToMessages(callback: (msg: any) => void) {
    this.onMessageCallbacks.push(callback);
    return () => {
      this.onMessageCallbacks = this.onMessageCallbacks.filter((cb) => cb !== callback);
    };
  }

  private setStatus(newStatus: WebSocketStatus) {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.onStatusChangeCallbacks.forEach((cb) => cb(newStatus));
    }
  }

  async connect(url: string, pin: string) {
    this.disconnect(false); // Clean up existing connection

    const wsUrl = url.replace(/^http/, 'ws') + '/ws';
    console.log(`[WebSocketClient] Connecting to ${wsUrl}...`);
    this.setStatus('connecting');

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('[WebSocketClient] Connected. Sending auth hello...');
        this.reconnectAttempts = 0;
        this.send({ type: 'hello', pin });
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          
          if (msg.type === 'auth_ok') {
            console.log('[WebSocketClient] Authenticated successfully.');
            this.setStatus('connected');
            this.startHeartbeat();
          } else if (msg.type === 'auth_fail') {
            console.error('[WebSocketClient] Authentication failed.');
            this.setStatus('auth_failed');
            this.disconnect(true);
          } else if (msg.type === 'pong') {
            // Heartbeat acknowledged
          } else {
            // Pass down to listeners
            this.onMessageCallbacks.forEach((cb) => cb(msg));
          }
        } catch (e) {
          console.error('[WebSocketClient] Failed to parse message', e);
        }
      };

      this.ws.onclose = (event) => {
        console.log(`[WebSocketClient] Disconnected (Code: ${event.code})`);
        this.cleanup();
        
        if (this.status !== 'auth_failed') {
          this.setStatus('disconnected');
          this.scheduleReconnect(url, pin);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[WebSocketClient] Error:', error);
        this.setStatus('error');
      };
    } catch (e) {
      console.error('[WebSocketClient] Setup failed:', e);
      this.setStatus('error');
      this.scheduleReconnect(url, pin);
    }
  }

  private scheduleReconnect(url: string, pin: string) {
    if (this.reconnectAttempts >= 5) {
      console.log('[WebSocketClient] Max reconnect attempts reached.');
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 15000);
    this.reconnectAttempts++;
    
    console.log(`[WebSocketClient] Reconnecting in ${delay}ms (Attempt ${this.reconnectAttempts})`);
    this.reconnectTimeout = setTimeout(() => {
      this.connect(url, pin);
    }, delay);
  }

  private startHeartbeat() {
    if (this.pingInterval) clearInterval(this.pingInterval);
    this.pingInterval = setInterval(() => {
      this.send({ type: 'heartbeat' });
    }, 25000); // Server disconnects after 30s timeout, ping every 25s
  }

  send(message: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
      return true;
    }
    return false;
  }

  private cleanup() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  disconnect(permanent = true) {
    this.cleanup();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    if (permanent) {
      this.setStatus('disconnected');
    }
  }
}

export const wsClient = new WebSocketClient();
