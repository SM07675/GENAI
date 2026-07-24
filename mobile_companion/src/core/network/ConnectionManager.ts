import { Platform } from 'react-native';

export type ConnectionMethod = 'cloudflare' | 'local' | 'tailscale' | 'ngrok' | 'custom';

export interface ServerConnection {
  url: string;
  method: ConnectionMethod;
  latencyMs?: number;
  isOnline: boolean;
  lastChecked: number;
}

class ConnectionManager {
  private currentConnection: ServerConnection | null = null;
  private subscribers: Array<(conn: ServerConnection | null) => void> = [];

  subscribe(callback: (conn: ServerConnection | null) => void) {
    this.subscribers.push(callback);
    callback(this.currentConnection);
    return () => {
      this.subscribers = this.subscribers.filter((cb) => cb !== callback);
    };
  }

  private notify() {
    this.subscribers.forEach((cb) => cb(this.currentConnection));
  }

  async validateAndConnect(url: string, method: ConnectionMethod = 'custom'): Promise<boolean> {
    try {
      const startTime = Date.now();
      
      // Clean up URL (remove trailing slashes, add http/https if missing)
      let cleanUrl = url.trim().replace(/\/$/, '');
      if (!cleanUrl.startsWith('http')) {
        if (method === 'local' || method === 'tailscale') {
          cleanUrl = `http://${cleanUrl}`;
        } else {
          cleanUrl = `https://${cleanUrl}`;
        }
      }

      // Automatically append port for local if not specified
      if (method === 'local' && !cleanUrl.includes(':')) {
        cleanUrl = `${cleanUrl}:8000`;
      }

      console.log(`[ConnectionManager] Validating connection to ${cleanUrl}...`);
      
      // Hit the /health or /info endpoint
      const response = await fetch(`${cleanUrl}/health`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
      });

      if (response.ok) {
        const data = await response.json();
        const latencyMs = Date.now() - startTime;
        
        this.currentConnection = {
          url: cleanUrl,
          method,
          latencyMs,
          isOnline: true,
          lastChecked: Date.now(),
        };
        
        console.log(`[ConnectionManager] Successfully connected! Latency: ${latencyMs}ms`);
        this.notify();
        return true;
      }
      return false;
    } catch (error) {
      console.error(`[ConnectionManager] Connection failed:`, error);
      return false;
    }
  }

  getCurrentConnection() {
    return this.currentConnection;
  }

  disconnect() {
    this.currentConnection = null;
    this.notify();
  }

  // TODO: Implement subnet scanning (Requires native module or brute-force pinging)
  async scanLocalSubnet(): Promise<string[]> {
    console.log('[ConnectionManager] Scanning local subnet for Genie Servers...');
    // Mock implementation for now
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(['192.168.1.50:8000']);
      }, 2000);
    });
  }
}

export const connectionManager = new ConnectionManager();
