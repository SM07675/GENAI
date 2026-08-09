/**
 * main.ts — Genie Electron Shell Master Entry Point.
 *
 * Implements (§16.3, §16.5, §16.6):
 * - Single instance lock — second launch focuses existing instance and exits.
 * - Managed FastAPI backend sidecar process boot & health check gate.
 * - WindowManager for Main UI & Companion transparent overlay.
 * - System tray & global shortcut (Ctrl+Shift+G for Quick Look).
 * - Clean shutdown sequence (zero orphaned Python processes or ports).
 */
import { app } from "electron";
import path from "path";
import http from "http";
import { BackendManager } from "./backend-manager";
import { WindowManager } from "./window-manager";
import { TrayManager } from "./tray-manager";
import { ShortcutManager } from "./shortcuts";
import { registerIpcHandlers } from "./ipc";

const isDev = process.env.NODE_ENV === "development" || !app.isPackaged;
const projectRoot = path.join(__dirname, "..", "..", "..");

// ── Single Instance Lock (§16.5) ─────────────────────────────────────────────
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  console.log("[Main] Another instance of Genie is already running. Exiting...");
  app.quit();
  process.exit(0);
}

let backendManager: BackendManager;
let windowManager: WindowManager;
let trayManager: TrayManager;
let shortcutManager: ShortcutManager;

// ── Quick Look Trigger Callback ──────────────────────────────────────────────
function triggerQuickLook() {
  const port = backendManager.getPort();
  // Trigger Quick Look via backend HTTP/WS trigger or IPC to frontend
  const req = http.request(
    {
      hostname: "127.0.0.1",
      port,
      path: "/api/v1/companion/quicklook",
      method: "POST",
      headers: { "Content-Type": "application/json" },
    },
    (res) => {
      console.log(`[QuickLook Trigger] Backend responded with status ${res.statusCode}`);
    }
  );
  req.on("error", (err) => {
    console.warn("[QuickLook Trigger] Backend request failed (may use WS fallback):", err.message);
  });
  req.end();

  // Also notify main window via IPC
  const mainWin = windowManager.getMainWindow();
  if (mainWin && !mainWin.isDestroyed()) {
    mainWin.webContents.send("companion:quick-look-triggered");
  }
}

// ── Companion Mode Toggle Callback ───────────────────────────────────────────
function toggleCompanionMode() {
  const mainWin = windowManager.getMainWindow();
  if (mainWin && !mainWin.isDestroyed()) {
    mainWin.webContents.send("companion:toggle-mode-triggered");
  }
}

// ── Lifecycle Hook ───────────────────────────────────────────────────────────
app.on("second-instance", () => {
  if (windowManager) {
    windowManager.focusMain();
  }
});

app.whenReady().then(async () => {
  const preloadPath = path.join(__dirname, "..", "preload.cjs");

  backendManager = new BackendManager(isDev, projectRoot);
  windowManager = new WindowManager(isDev, preloadPath);

  // 1. Boot backend sidecar (§16.3)
  console.log("[Main] Starting backend sidecar...");
  const backendReady = await backendManager.start();
  const port = backendManager.getPort();

  if (!backendReady) {
    console.error("[Main] Backend sidecar failed health check gate!");
  } else {
    console.log(`[Main] Backend sidecar ready on 127.0.0.1:${port}`);
  }

  // 2. Register IPC handlers
  registerIpcHandlers(windowManager, backendManager, triggerQuickLook, toggleCompanionMode);

  // 3. Create Main Window
  windowManager.createMainWindow(port);

  // 4. Initialize Tray Icon & Context Menu
  trayManager = new TrayManager(windowManager, toggleCompanionMode, triggerQuickLook);
  trayManager.init();

  // 6. Register Global Shortcut (Ctrl+Shift+G)
  shortcutManager = new ShortcutManager(triggerQuickLook);
  shortcutManager.register();

  app.on("activate", () => {
    if (windowManager.getMainWindow() === null) {
      windowManager.createMainWindow(port);
    }
  });
});

// ── Clean Shutdown Sequence (§16.6) ──────────────────────────────────────────
let isShuttingDown = false;

app.on("before-quit", async (event) => {
  if (isShuttingDown) return;
  isShuttingDown = true;
  event.preventDefault();

  console.log("[Main] Shutdown initiated. Cleaning up...");

  if (shortcutManager) {
    shortcutManager.unregisterAll();
  }
  if (trayManager) {
    trayManager.destroy();
  }
  if (windowManager) {
    windowManager.closeAll();
  }
  if (backendManager) {
    await backendManager.stop();
  }

  console.log("[Main] Shutdown complete. Exiting.");
  app.exit(0);
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
