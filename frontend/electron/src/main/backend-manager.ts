/**
 * backend-manager.ts — FastAPI sidecar process manager for Electron.
 *
 * Responsibilities (§16.3, §16.7, §16.8):
 * - Spawns Python FastAPI backend (dev python script or packaged backend.exe).
 * - Performs dynamic port discovery if base port is occupied.
 * - Polls GET /health until ready: true (with 15s timeout).
 * - Tracks child process; performs bounded retries (max 3) on unexpected crash.
 * - Ensures clean process termination on app exit (no zombie Python processes).
 */
import { spawn, ChildProcess } from "child_process";
import http from "http";
import net from "net";
import path from "path";

export interface BackendStatus {
  running: boolean;
  ready: boolean;
  port: number;
  pid: number | null;
  error: string | null;
}

export class BackendManager {
  private child: ChildProcess | null = null;
  private port: number = 8765;
  private isDev: boolean;
  private projectRoot: string;
  private restartCount: number = 0;
  private maxRestarts: number = 3;
  private status: BackendStatus = {
    running: false,
    ready: false,
    port: 8765,
    pid: null,
    error: null,
  };

  constructor(isDev: boolean, projectRoot: string) {
    this.isDev = isDev;
    this.projectRoot = projectRoot;
  }

  public getPort(): number {
    return this.port;
  }

  public getStatus(): BackendStatus {
    return { ...this.status };
  }

  /**
   * Find an available local port starting from startPort.
   */
  public async findAvailablePort(startPort: number = 8765): Promise<number> {
    return new Promise((resolve) => {
      const checkPort = (portToCheck: number) => {
        const server = net.createServer();
        server.once("error", () => {
          checkPort(portToCheck + 1);
        });
        server.once("listening", () => {
          server.close(() => resolve(portToCheck));
        });
        server.listen(portToCheck, "127.0.0.1");
      };
      checkPort(startPort);
    });
  }

  /**
   * Start the backend process and wait for /health to return ready: true.
   */
  public async start(): Promise<boolean> {
    this.port = await this.findAvailablePort(8765);
    this.status.port = this.port;

    const env = { ...process.env, PORT: this.port.toString() };

    let command: string;
    let args: string[];
    let cwd: string;

    if (this.isDev) {
      const venvPython = process.platform === "win32"
        ? path.join(this.projectRoot, "backend", ".venv", "Scripts", "python.exe")
        : path.join(this.projectRoot, "backend", ".venv", "bin", "python");

      command = venvPython;
      args = ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", this.port.toString()];
      cwd = path.join(this.projectRoot, "backend");
    } else {
      // Production packaged executable path
      const exeName = process.platform === "win32" ? "backend.exe" : "backend";
      command = path.join(process.resourcesPath, "backend", exeName);
      args = ["--port", this.port.toString()];
      cwd = path.join(process.resourcesPath, "backend");
    }

    console.log(`[BackendManager] Spawning backend: ${command} ${args.join(" ")}`);

    try {
      this.child = spawn(command, args, {
        cwd,
        env,
        stdio: ["pipe", "pipe", "pipe"],
        windowsHide: true,
      });

      this.status.running = true;
      this.status.pid = this.child.pid ?? null;

      this.child.stdout?.on("data", (chunk: Buffer) => {
        console.log(`[Backend] ${chunk.toString().trim()}`);
      });

      this.child.stderr?.on("data", (chunk: Buffer) => {
        console.error(`[Backend ERR] ${chunk.toString().trim()}`);
      });

      this.child.on("exit", (code, signal) => {
        console.warn(`[BackendManager] Process exited with code ${code}, signal ${signal}`);
        this.status.running = false;
        this.status.ready = false;
        this.status.pid = null;

        if (code !== 0 && this.restartCount < this.maxRestarts) {
          this.restartCount++;
          console.log(`[BackendManager] Attempting restart ${this.restartCount}/${this.maxRestarts}...`);
          setTimeout(() => this.start(), 2000 * this.restartCount);
        } else if (code !== 0) {
          this.status.error = `Backend crashed unexpectedly (exit code ${code})`;
        }
      });

      // Wait for health check
      const ready = await this.waitForHealth(15000);
      this.status.ready = ready;
      if (ready) {
        this.restartCount = 0; // reset on successful boot
      }
      return ready;
    } catch (err: any) {
      this.status.error = err.message || "Failed to spawn backend process";
      console.error("[BackendManager] Spawn error:", err);
      return false;
    }
  }

  /**
   * Poll GET http://127.0.0.1:port/health until ready: true or timeout.
   */
  private async waitForHealth(timeoutMs: number = 15000): Promise<boolean> {
    const startTime = Date.now();
    while (Date.now() - startTime < timeoutMs) {
      const isReady = await this.checkHealth();
      if (isReady) return true;
      await new Promise((r) => setTimeout(r, 500));
    }
    console.error(`[BackendManager] Health check timed out after ${timeoutMs}ms`);
    return false;
  }

  private checkHealth(): Promise<boolean> {
    return new Promise((resolve) => {
      const req = http.get(`http://127.0.0.1:${this.port}/health`, (res) => {
        if (res.statusCode !== 200) {
          resolve(false);
          return;
        }
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          try: {
            const parsed = JSON.parse(data);
            resolve(parsed.status === "ok" || parsed.ready === true);
          } catch {
            resolve(false);
          }
        });
      });
      req.on("error", () => resolve(false));
      req.setTimeout(1000, () => {
        req.destroy();
        resolve(false);
      });
    });
  }

  /**
   * Stop the backend process cleanly on app shutdown (§16.6).
   */
  public async stop(): Promise<void> {
    if (!this.child) return;
    console.log("[BackendManager] Terminating backend process...");
    
    return new Promise((resolve) => {
      if (!this.child || this.child.killed) {
        resolve();
        return;
      }
      this.child.once("exit", () => resolve());
      this.child.kill("SIGTERM");

      // Force kill if not exited after 3 seconds
      setTimeout(() => {
        if (this.child && !this.child.killed) {
          this.child.kill("SIGKILL");
        }
        resolve();
      }, 3000);
    });
  }
}
