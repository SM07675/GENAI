// Production Electron main process for Genie AI OS.
// Supports both development (loading Vite dev server) and production packaging.
const { app, BrowserWindow, shell, ipcMain, Tray, Menu, nativeImage, globalShortcut, powerMonitor } = require("electron");
const path = require("path");
const { pathToFileURL } = require("url");
const http = require("http");
const net = require("net");
const fs = require("fs");
const crypto = require("crypto");
const { spawn } = require("child_process");

const isDev = process.env.NODE_ENV === "development" || !app.isPackaged;
const projectRoot = path.join(__dirname, "..");

// ── Companion Settings Persistence ───────────────────────────────────────────
// Position/displayMode live in the MAIN process because it's the process that
// actually owns the OS-level window. (The renderer's localStorage copy is a
// separate concern — see companionStore.ts — and is not read here.)
const companionSettingsPath = path.join(app.getPath("userData"), "companion-settings.json");

function loadCompanionSettings() {
  try {
    const raw = fs.readFileSync(companionSettingsPath, "utf-8");
    const parsed = JSON.parse(raw);
    return {
      x: typeof parsed.x === "number" ? parsed.x : null,
      y: typeof parsed.y === "number" ? parsed.y : null,
      displayId: typeof parsed.displayId === "number" ? parsed.displayId : null,
      displayMode: ["full", "floating", "mini", "invisible"].includes(parsed.displayMode)
        ? parsed.displayMode
        : "floating",
    };
  } catch {
    return { x: null, y: null, displayId: null, displayMode: "floating" };
  }
}

let saveSettingsTimer = null;
function saveCompanionSettings(partial) {
  // Debounced — drag emits many position updates per second.
  if (saveSettingsTimer) clearTimeout(saveSettingsTimer);
  saveSettingsTimer = setTimeout(() => {
    try {
      const current = loadCompanionSettings();
      const next = { ...current, ...partial };
      fs.mkdirSync(path.dirname(companionSettingsPath), { recursive: true });
      fs.writeFileSync(companionSettingsPath, JSON.stringify(next, null, 2));
    } catch (err) {
      console.error("[Companion] Failed to persist settings:", err);
    }
  }, 250);
}

// ── Single Instance Lock (§16.5) ─────────────────────────────────────────────
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  console.log("[Main] Another instance of Genie is running. Exiting...");
  app.quit();
  process.exit(0);
}

let mainWindow = null;
let companionWindow = null;
let tray = null;
let backendProcess = null;
let backendPort = 8765;
const backendPin = process.env.GENIE_PIN || "1234";
let backendStatus = { running: false, ready: false, port: 8765, error: null };
let restartCount = 0;
const maxRestarts = 3;

// Companion overlay window state — restored from disk (§ Position Persistence)
const persistedCompanionSettings = loadCompanionSettings();
let companionVisible = false;
let companionModeActive = false;
let companionRequestedActive = false;
let companionTransition = null;
let latestCompanionState = null;
let companionRendererReady = false;
let companionReadyWaiters = [];
let companionPosition = { x: persistedCompanionSettings.x, y: persistedCompanionSettings.y };
let companionDisplayMode = persistedCompanionSettings.displayMode;   // full | floating | mini | invisible

// ── Port Discovery (§16.7) ───────────────────────────────────────────────────
function findAvailablePort(startPort = 8765) {
  return new Promise((resolve) => {
    const checkPort = (portToCheck) => {
      const server = net.createServer();
      server.once("error", () => checkPort(portToCheck + 1));
      server.once("listening", () => {
        server.close(() => resolve(portToCheck));
      });
      server.listen(portToCheck, "127.0.0.1");
    };
    checkPort(startPort);
  });
}

// ── Health Gate Polling (§16.3) ─────────────────────────────────────────────
function checkHealth(port) {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/health`, (res) => {
      if (res.statusCode !== 200) return resolve(false);
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
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

async function waitForHealth(port, timeoutMs = 15000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeoutMs) {
    const isReady = await checkHealth(port);
    if (isReady) return true;
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

// ── Spawn Backend Sidecar (§16.3, §16.8) ────────────────────────────────────
async function startBackend(preferredPort = 8765) {
  backendStatus.error = null;
  backendPort = await findAvailablePort(preferredPort);
  backendStatus.port = backendPort;

  let command;
  let args;
  let cwd;

  if (isDev) {
    const venvPython = process.platform === "win32"
      ? path.join(projectRoot, "..", "backend", ".venv", "Scripts", "python.exe")
      : path.join(projectRoot, "..", "backend", ".venv", "bin", "python");

    command = venvPython;
    args = ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", backendPort.toString()];
    cwd = path.join(projectRoot, "..", "backend");
  } else {
    const exeName = process.platform === "win32" ? "backend.exe" : "backend";
    command = path.join(process.resourcesPath, "backend", exeName);
    args = ["--port", backendPort.toString()];
    cwd = path.join(process.resourcesPath, "backend");
  }

  console.log(`[Main] Spawning backend sidecar: ${command} ${args.join(" ")}`);

  try {
    backendProcess = spawn(command, args, {
      cwd,
      env: {
        ...process.env,
        PORT: backendPort.toString(),
        GENIE_PIN: backendPin,
        NGROK_ENABLED: process.env.NGROK_ENABLED || "false",
      },
      windowsHide: true,
    });

    backendStatus.running = true;

    backendProcess.stdout?.on("data", (data) => {
      console.log(`[Backend] ${data.toString().trim()}`);
    });

    backendProcess.stderr?.on("data", (data) => {
      console.error(`[Backend ERR] ${data.toString().trim()}`);
    });

    backendProcess.on("exit", (code) => {
      console.warn(`[Main] Backend process exited with code ${code}`);
      backendStatus.running = false;
      backendStatus.ready = false;

      if (code !== 0 && restartCount < maxRestarts) {
        restartCount++;
        console.log(`[Main] Attempting backend restart ${restartCount}/${maxRestarts}...`);
        setTimeout(() => startBackend(backendPort), 2000 * restartCount);
      } else if (code !== 0) {
        backendStatus.error = `Backend crashed with exit code ${code}`;
      }
    });

    // First packaged launch may spend 15–30s loading Silero VAD/ONNX assets.
    // Keep the health gate longer than that cold-start path so a healthy
    // sidecar is not falsely reported as failed.
    const ready = await waitForHealth(backendPort, 60000);
    backendStatus.ready = ready;
    if (ready) restartCount = 0;
    return ready;
  } catch (err) {
    backendStatus.error = err.message;
    console.error("[Main] Failed to spawn backend:", err);
    return false;
  }
}

// ── Window Management (§6.6, §18.4) ──────────────────────────────────────────────
function createWindows() {
  // 1. Main Window
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    transparent: false,
    resizable: true,
    backgroundColor: "#020617",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow?.show();
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  const mainUrl = isDev
    ? `http://localhost:5173?backendPort=${backendPort}`
    : `${pathToFileURL(path.join(__dirname, "..", "dist", "index.html")).toString()}?backendPort=${backendPort}`;

  mainWindow.loadURL(mainUrl);

  if (isDev) {
    mainWindow.webContents.openDevTools({ mode: "undocked" });
  }

  // The companion is created lazily when mode is entered. This keeps startup
  // lightweight and guarantees that only the main renderer owns backend/audio.
}

// ── Multi-Monitor Bounds Validation ──────────────────────────────────────────
function validateCompanionPosition(x, y, winW = 280, winH = 340) {
  const { screen } = require('electron');
  const displays = screen.getAllDisplays();

  // Check if position lies within any display's workArea
  const isWithinDisplay = displays.some(display => {
    const { x: dx, y: dy, width: dw, height: dh } = display.workArea;
    return x >= dx && x + winW <= dx + dw && y >= dy && y + winH <= dy + dh;
  });

  if (isWithinDisplay) {
    return { x: Math.round(x), y: Math.round(y) };
  }

  // Fallback to primary display bottom-right
  const primary = screen.getPrimaryDisplay().workArea;
  return {
    x: Math.round(primary.x + primary.width - winW - 30),
    y: Math.round(primary.y + primary.height - winH - 30),
  };
}

// ── Companion Overlay Window ──────────────────────────────────────────────────
function createCompanionWindow() {
  if (companionWindow && !companionWindow.isDestroyed()) return companionWindow;

  companionRendererReady = false;
  const initialSize = COMPANION_SIZES[companionDisplayMode] || COMPANION_SIZES.floating;

  const initialPos = validateCompanionPosition(
    companionPosition.x ?? 9999,
    companionPosition.y ?? 9999,
    initialSize.width,
    initialSize.height
  );

  companionWindow = new BrowserWindow({
    x: initialPos.x,
    y: initialPos.y,
    width: initialSize.width,
    height: initialSize.height,
    frame: false,
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable: true,
    show: false,
    hasShadow: false,
    type: 'toolbar',         // Standard window type for desktop overlays on Windows
    webPreferences: {
      preload: path.join(__dirname, "companion-preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });

  // Interactive by default. Click-through is an explicit opt-in because a
  // permanently click-through companion cannot expose usable controls.
  companionWindow.setIgnoreMouseEvents(false);

  // Always on top — screen-saver level on Windows
  companionWindow.setAlwaysOnTop(true, 'screen-saver');

  const companionUrl = isDev
    ? `http://localhost:5173?companion=1&backendPort=${backendPort}`
    : `${pathToFileURL(path.join(__dirname, "..", "dist", "index.html")).toString()}?companion=1&backendPort=${backendPort}`;

  companionWindow.loadURL(companionUrl);
  companionWindow.webContents.on('did-start-loading', () => {
    companionRendererReady = false;
  });

  companionWindow.once('ready-to-show', () => {
    if (companionVisible) {
      companionWindow?.showInactive(); // Show without taking focus
    }
  });

  companionWindow.on('moved', () => {
    if (!companionWindow || companionWindow.isDestroyed()) return;
    const bounds = companionWindow.getBounds();
    companionPosition = { x: bounds.x, y: bounds.y };
    const { screen } = require('electron');
    const display = screen.getDisplayMatching(bounds);
    saveCompanionSettings({ x: bounds.x, y: bounds.y, displayId: display?.id ?? null });
  });

  companionWindow.on('closed', () => {
    companionWindow = null;
    if (companionModeActive && !isShuttingDown) {
      companionModeActive = false;
      companionRequestedActive = false;
      companionVisible = false;
      showMainWindow();
      updateTrayMenu();
    }
  });

  return companionWindow;
}

// ── Companion window size configs ─────────────────────────────────────────
const COMPANION_SIZES = {
  full:      { width: 420, height: 620 },
  floating:  { width: 300, height: 360 },
  mini:      { width: 150, height: 170 },
  invisible: { width: 1,   height: 1   },
};

function showMainWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

function sendToMain(channel, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, payload);
  }
}

function broadcastCompanionMode() {
  const state = { active: companionModeActive, visible: companionVisible };
  sendToMain("companion:mode-changed", state);
  if (companionWindow && !companionWindow.isDestroyed()) {
    companionWindow.webContents.send("companion:mode-changed", state);
  }
}

function waitForCompanionRenderer(timeoutMs = 12000) {
  if (companionRendererReady) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const waiter = {
      resolve: () => { clearTimeout(waiter.timer); resolve(); },
      timer: null,
    };
    waiter.timer = setTimeout(() => {
      companionReadyWaiters = companionReadyWaiters.filter((item) => item !== waiter);
      reject(new Error("Companion renderer did not initialize in time."));
    }, timeoutMs);
    companionReadyWaiters.push(waiter);
  });
}

function waitForCompanionReady(win, timeoutMs = 12000) {
  if (!win || win.isDestroyed()) return Promise.reject(new Error("Companion window was destroyed."));
  if (!win.webContents.isLoadingMainFrame()) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error("Companion window did not become ready in time."));
    }, timeoutMs);
    const cleanup = () => {
      clearTimeout(timer);
      win.webContents.removeListener("did-finish-load", onReady);
      win.webContents.removeListener("did-fail-load", onFail);
    };
    const onReady = () => { cleanup(); resolve(); };
    const onFail = (_event, code, description) => {
      cleanup();
      reject(new Error(`Companion failed to load (${code}): ${description}`));
    };
    win.webContents.once("did-finish-load", onReady);
    win.webContents.once("did-fail-load", onFail);
  });
}

async function enterCompanionMode() {
  companionRequestedActive = true;
  if (companionModeActive && companionWindow?.isVisible()) {
    return { success: true, active: true, visible: true };
  }
  if (companionTransition) return companionTransition;

  companionTransition = (async () => {
    try {
      const win = createCompanionWindow();
      await waitForCompanionReady(win);
      await waitForCompanionRenderer();
      companionVisible = true;
      win.show();
      win.moveTop();
      if (!win.isVisible()) throw new Error("Companion window could not be shown.");

      // Only hide the main UI after the replacement surface is verified visible.
      mainWindow?.hide();
      companionModeActive = true;
      sendToMain("companion:backend-control", { type: "companion_start" });
      if (latestCompanionState) win.webContents.send("companion:state", latestCompanionState);
      broadcastCompanionMode();
      updateTrayMenu();
      return { success: true, active: true, visible: true };
    } catch (err) {
      companionVisible = false;
      companionModeActive = false;
      companionRequestedActive = false;
      companionWindow?.hide();
      showMainWindow();
      updateTrayMenu();
      return { success: false, active: false, visible: false, error: err?.message || "Companion unavailable." };
    } finally {
      companionTransition = null;
    }
  })();
  return companionTransition;
}

async function exitCompanionMode() {
  companionRequestedActive = false;
  if (companionTransition) await companionTransition;
  companionVisible = false;
  companionModeActive = false;
  if (companionWindow && !companionWindow.isDestroyed()) companionWindow.hide();
  sendToMain("companion:backend-control", { type: "companion_stop" });
  showMainWindow();
  broadcastCompanionMode();
  updateTrayMenu();
  return { success: true, active: false, visible: false };
}

function toggleCompanionMode() {
  return companionRequestedActive ? exitCompanionMode() : enterCompanionMode();
}


// ── IPC Handlers ────────────────────────────────────────────────────────────────────
function setupIpc() {
  ipcMain.on("window:minimize", (event) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    win?.minimize();
  });

  ipcMain.on("window:close", (event) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    win?.close();
  });

  ipcMain.on("window:focus-main", () => {
    if (companionModeActive) void exitCompanionMode();
    else showMainWindow();
  });

  ipcMain.on("companion:set-click-through", (_, ignore) => {
    if (companionWindow) {
      if (ignore) {
        companionWindow.setIgnoreMouseEvents(true, { forward: true });
      } else {
        companionWindow.setIgnoreMouseEvents(false);
      }
    }
  });

  // ── Companion overlay window management ─────────────────────────────

  // Show companion overlay — returns real, verified state instead of trusting
  // the renderer to assume success. The UI should not say "ACTIVE" until this
  // resolves truthfully.
  ipcMain.handle("companion:show", () => enterCompanionMode());
  ipcMain.handle("companion:hide", () => exitCompanionMode());
  ipcMain.handle("companion:toggle", () => toggleCompanionMode());
  ipcMain.handle("companion:get-mode", () => ({ active: companionModeActive, visible: companionVisible }));

  // Set display mode — resizes the companion window
  ipcMain.on("companion:set-display-mode", (_, mode) => {
    const safeMode = Object.prototype.hasOwnProperty.call(COMPANION_SIZES, mode) ? mode : "floating";
    const size = COMPANION_SIZES[safeMode];
    companionDisplayMode = safeMode;
    if (companionWindow && !companionWindow.isDestroyed()) {
      companionWindow.setSize(size.width, size.height, true);
      if (safeMode === 'invisible') {
        companionWindow.setIgnoreMouseEvents(true, { forward: true });
      } else {
        // Let renderer decide click-through per-mode via companion:set-click-through
      }
    }
    saveCompanionSettings({ displayMode: safeMode });
    sendToMain("companion:display-mode-changed", safeMode);
  });

  // Reposition companion window from renderer with multi-monitor safety
  // (used both for drag-to-move and the corner presets)
  ipcMain.on("companion:set-position", (_, { x, y } = {}) => {
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    if (companionWindow && !companionWindow.isDestroyed()) {
      const bounds = companionWindow.getBounds();
      const safePos = validateCompanionPosition(x, y, bounds.width, bounds.height);
      companionPosition = safePos;
      companionWindow.setPosition(safePos.x, safePos.y, false);
      const { screen } = require('electron');
      const display = screen.getDisplayNearestPoint(safePos);
      saveCompanionSettings({ x: safePos.x, y: safePos.y, displayId: display?.id ?? null });
    }
  });

  // Get current companion window bounds (so renderer can sync)
  ipcMain.handle("companion:get-bounds", () => {
    if (companionWindow && !companionWindow.isDestroyed()) {
      return companionWindow.getBounds();
    }
    return null;
  });

  // Enable interactive mode (mouse events pass through when false)
  ipcMain.on("companion:set-interactive", (_, interactive) => {
    if (companionWindow && !companionWindow.isDestroyed()) {
      if (interactive) {
        companionWindow.setIgnoreMouseEvents(false);
        companionWindow.setFocusable(true);
      } else {
        companionWindow.setIgnoreMouseEvents(true, { forward: true });
        companionWindow.setFocusable(false);
      }
    }
  });

  ipcMain.on("companion:set-expanded", (_, expanded) => {
    if (!companionWindow || companionWindow.isDestroyed()) return;
    const size = expanded ? COMPANION_SIZES.full : COMPANION_SIZES.floating;
    const bounds = companionWindow.getBounds();
    const safePos = validateCompanionPosition(bounds.x, bounds.y, size.width, size.height);
    companionWindow.setBounds({ ...safePos, ...size }, true);
  });

  ipcMain.on("companion:set-always-on-top", (_, enabled) => {
    if (!companionWindow || companionWindow.isDestroyed()) return;
    companionWindow.setAlwaysOnTop(Boolean(enabled), "screen-saver");
  });

  ipcMain.on("companion:publish-state", (event, state) => {
    if (!mainWindow || event.sender !== mainWindow.webContents || !state || typeof state !== "object") return;
    latestCompanionState = state;
    if (companionWindow && !companionWindow.isDestroyed()) {
      companionWindow.webContents.send("companion:state", state);
    }
  });

  ipcMain.on("companion:action", (event, action) => {
    if (!companionWindow || event.sender !== companionWindow.webContents || !action || typeof action !== "object") return;
    const allowed = new Set(["text", "image", "manual_wake", "cancel", "quick_look", "pause", "resume"]);
    if (!allowed.has(action.type)) return;
    sendToMain("companion:action", action);
  });

  ipcMain.on("companion:renderer-ready", (event) => {
    if (!companionWindow || event.sender !== companionWindow.webContents) return;
    companionRendererReady = true;
    companionReadyWaiters.splice(0).forEach((waiter) => waiter.resolve());
    if (latestCompanionState) event.sender.send("companion:state", latestCompanionState);
    event.sender.send("companion:mode-changed", { active: companionModeActive, visible: companionVisible });
  });

  ipcMain.handle("backend:get-status", () => backendStatus);
  ipcMain.handle("backend:get-port", () => backendPort);
  ipcMain.handle("backend:get-desktop-pin", (event) => {
    if (!mainWindow || event.sender !== mainWindow.webContents) return null;
    return backendPin;
  });

  ipcMain.on("companion:trigger-quick-look", () => triggerQuickLook());
  ipcMain.on("companion:toggle-mode", () => void toggleCompanionMode());
}

// ── Triggers ─────────────────────────────────────────────────────────────────
function triggerQuickLook() {
  const req = http.request(
    {
      hostname: "127.0.0.1",
      port: backendPort,
      path: "/api/v1/companion/quicklook",
      method: "POST",
      headers: { "Content-Type": "application/json" },
    },
    (res) => console.log(`[QuickLook] Status: ${res.statusCode}`)
  );
  req.on("error", () => {});
  req.end();

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("companion:quick-look-triggered");
  }
}

async function restartBackend() {
  const previousPort = backendPort;
  if (backendProcess && !backendProcess.killed) {
    await new Promise((resolve) => {
      const timer = setTimeout(resolve, 3000);
      backendProcess.once("exit", () => { clearTimeout(timer); resolve(); });
      backendProcess.kill("SIGTERM");
    });
  }
  backendProcess = null;
  restartCount = 0;
  backendStatus = { running: false, ready: false, port: backendPort, error: null };
  const ready = await startBackend(previousPort);
  sendToMain("companion:action", {
    type: "system_note",
    message: ready ? "Backend restarted." : "Backend restart failed. Open Genie for details.",
  });
}

// ── Tray Icon (§19) ──────────────────────────────────────────────────────────
function setupTray() {
  const iconPath = path.join(__dirname, "..", "public", "icon.png");
  let icon = nativeImage.createFromPath(iconPath);
  if (icon.isEmpty()) icon = nativeImage.createEmpty();

  tray = new Tray(icon);
  tray.setToolTip("Genie AI — Press Ctrl+Shift+G to toggle Companion Mode");

  tray.on("click", () => {
    if (companionModeActive) void exitCompanionMode();
    else showMainWindow();
  });

  updateTrayMenu();
}

function updateTrayMenu() {
  if (!tray) return;
  const menu = Menu.buildFromTemplate([
    {
      label: "Open Genie",
      click: () => {
        if (companionModeActive) void exitCompanionMode();
        else showMainWindow();
      },
    },
    {
      label: companionModeActive ? "Exit Companion Mode" : "Enter Companion Mode",
      click: () => void toggleCompanionMode(),
    },
    { type: "separator" },
    {
      label: "Start Listening",
      click: () => sendToMain("companion:action", { type: "manual_wake" }),
    },
    {
      label: "Pause Listening",
      click: () => sendToMain("companion:action", { type: "cancel" }),
    },
    {
      label: "Quick Look",
      click: () => triggerQuickLook(),
    },
    { type: "separator" },
    {
      label: "Settings",
      click: () => {
        if (companionModeActive) void exitCompanionMode();
        else showMainWindow();
        sendToMain("companion:action", { type: "open_settings" });
      },
    },
    {
      label: "Restart Backend",
      click: () => void restartBackend(),
    },
    { type: "separator" },
    {
      label: "Quit Genie",
      click: () => app.quit(),
    },
  ]);

  tray.setContextMenu(menu);
}

// ── Global Shortcut (§6.2, §20) ──────────────────────────────────────────────
function setupShortcuts() {
  try {
    globalShortcut.register("CommandOrControl+Shift+G", () => {
      console.log("[Hotkey] Companion mode toggle triggered");
      void toggleCompanionMode();
    });
  } catch (err) {
    console.error("[Hotkey] Failed to register companion toggle:", err);
  }
}

// ── Power State Monitor (§7.6) ───────────────────────────────────────────────
function setupPowerMonitor() {
  powerMonitor.on("suspend", () => {
    console.log("[Power] OS is suspending/sleeping — pausing Companion Mode");
    const req = http.request({
      hostname: "127.0.0.1",
      port: backendPort,
      path: "/api/v1/companion/pause",
      method: "POST",
    });
    req.on("error", () => {});
    req.end();
  });

  powerMonitor.on("resume", () => {
    console.log("[Power] OS resumed — resetting observation timers");
    const req = http.request({
      hostname: "127.0.0.1",
      port: backendPort,
      path: "/api/v1/companion/resume",
      method: "POST",
    });
    req.on("error", () => {});
    req.end();
  });
}

// ── App Lifecycle ────────────────────────────────────────────────────────────
app.on("second-instance", () => {
  if (companionModeActive && companionWindow && !companionWindow.isDestroyed()) {
    companionWindow.show();
    companionWindow.focus();
  } else {
    showMainWindow();
  }
});

app.whenReady().then(async () => {
  setupIpc();
  console.log("[Main] Booting backend sidecar...");
  const backendReady = await startBackend();
  if (!backendReady) {
    console.error("[Main] Backend health check failed! Proceeding with fallback UI.");
  } else {
    console.log(`[Main] Backend ready on 127.0.0.1:${backendPort}`);
  }

  createWindows();
  setupTray();
  setupShortcuts();
  setupPowerMonitor();

  const { screen } = require('electron');
  screen.on('display-removed', () => {
    if (!companionWindow || companionWindow.isDestroyed()) return;
    const bounds = companionWindow.getBounds();
    const safe = validateCompanionPosition(bounds.x, bounds.y, bounds.width, bounds.height);
    companionWindow.setPosition(safe.x, safe.y, false);
  });
  screen.on('display-metrics-changed', () => {
    if (!companionWindow || companionWindow.isDestroyed()) return;
    const bounds = companionWindow.getBounds();
    const safe = validateCompanionPosition(bounds.x, bounds.y, bounds.width, bounds.height);
    companionWindow.setPosition(safe.x, safe.y, false);
  });

  app.on("activate", () => {
    if (mainWindow === null) createWindows();
  });
});

// ── Clean Shutdown (§16.6) ──────────────────────────────────────────────────
let isShuttingDown = false;

app.on("before-quit", async (event) => {
  if (isShuttingDown) return;
  isShuttingDown = true;
  event.preventDefault();

  console.log("[Main] Stopping Genie...");
  globalShortcut.unregisterAll();
  if (tray) tray.destroy();

  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill("SIGTERM");
    setTimeout(() => {
      if (backendProcess && !backendProcess.killed) backendProcess.kill("SIGKILL");
      app.exit(0);
    }, 2000);
  } else {
    app.exit(0);
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
