/**
 * window-manager.ts — Electron window lifecycle manager.
 *
 * Responsibilities (§6.6, §16.5, §18.4):
 * - Owns Main BrowserWindow (Genie primary UI).
 * - Owns Companion BrowserWindow (transparent, always-on-top, frameless, skipTaskbar floating orb).
 * - Implements click-through toggle for the Companion overlay window.
 * - Handles window positioning, multi-monitor safety, and clean shutdown.
 */
import { BrowserWindow, shell, screen } from "electron";
import path from "path";

export class WindowManager {
  private mainWindow: BrowserWindow | null = null;
  private companionWindow: BrowserWindow | null = null;
  private isDev: boolean;
  private preloadPath: string;

  constructor(isDev: boolean, preloadPath: string) {
    this.isDev = isDev;
    this.preloadPath = preloadPath;
  }

  public getMainWindow(): BrowserWindow | null {
    return this.mainWindow;
  }

  public getCompanionWindow(): BrowserWindow | null {
    return this.companionWindow;
  }

  /**
   * Create the primary Genie main window.
   */
  public createMainWindow(serverPort: number): BrowserWindow {
    if (this.mainWindow) {
      if (this.mainWindow.isMinimized()) this.mainWindow.restore();
      this.mainWindow.focus();
      return this.mainWindow;
    }

    this.mainWindow = new BrowserWindow({
      width: 1280,
      height: 820,
      minWidth: 900,
      minHeight: 600,
      frame: false,
      transparent: false,
      resizable: true,
      backgroundColor: "#020617",
      show: false, // Hide until ready-to-show to prevent visual flash
      webPreferences: {
        preload: this.preloadPath,
        contextIsolation: true,
        nodeIntegration: false,
        backgroundThrottling: false,
      },
    });

    this.mainWindow.once("ready-to-show", () => {
      this.mainWindow?.show();
    });

    // Open external links in default OS browser
    this.mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      shell.openExternal(url);
      return { action: "deny" };
    });

    this.mainWindow.on("closed", () => {
      this.mainWindow = null;
    });

    const targetUrl = this.isDev
      ? "http://localhost:5173"
      : `file://${path.join(__dirname, "..", "..", "dist", "index.html")}`;

    this.mainWindow.loadURL(targetUrl);

    if (this.isDev) {
      this.mainWindow.webContents.openDevTools({ mode: "undocked" });
    }

    return this.mainWindow;
  }

  /**
   * Create the transparent, always-on-top floating Companion Orb window (§6.6).
   */
  public createCompanionWindow(serverPort: number): BrowserWindow {
    if (this.companionWindow) {
      this.companionWindow.show();
      return this.companionWindow;
    }

    const primaryDisplay = screen.getPrimaryDisplay();
    const { width: workWidth, height: workHeight } = primaryDisplay.workAreaSize;

    // Default position: bottom-right quadrant
    const defaultX = Math.max(0, workWidth - 180);
    const defaultY = Math.max(0, workHeight - 220);

    this.companionWindow = new BrowserWindow({
      width: 180,
      height: 220,
      x: defaultX,
      y: defaultY,
      transparent: true,
      frame: false,
      alwaysOnTop: true,
      skipTaskbar: true,
      hasShadow: false,
      resizable: true,
      movable: true,
      show: true,
      webPreferences: {
        preload: this.preloadPath,
        contextIsolation: true,
        nodeIntegration: false,
        backgroundThrottling: false,
      },
    });

    this.companionWindow.setAlwaysOnTop(true, "screen-saver");

    this.companionWindow.on("closed", () => {
      this.companionWindow = null;
    });

    const targetUrl = this.isDev
      ? "http://localhost:5173/#companion"
      : `file://${path.join(__dirname, "..", "..", "dist", "index.html")}#companion`;

    this.companionWindow.loadURL(targetUrl);

    return this.companionWindow;
  }

  /**
   * Toggle mouse click-through for the Companion window.
   */
  public setCompanionClickThrough(ignore: boolean): void {
    if (!this.companionWindow) return;
    if (ignore) {
      this.companionWindow.setIgnoreMouseEvents(true, { forward: true });
    } else {
      this.companionWindow.setIgnoreMouseEvents(false);
    }
  }

  /**
   * Focus main window or restore if minimized (§16.5).
   */
  public focusMain(): void {
    if (!this.mainWindow) return;
    if (this.mainWindow.isMinimized()) this.mainWindow.restore();
    this.mainWindow.show();
    this.mainWindow.focus();
  }

  /**
   * Close all windows cleanly.
   */
  public closeAll(): void {
    if (this.companionWindow) {
      this.companionWindow.close();
      this.companionWindow = null;
    }
    if (this.mainWindow) {
      this.mainWindow.close();
      this.mainWindow = null;
    }
  }
}
