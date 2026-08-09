// Production Electron main process for Genie AI OS.
// Supports both development (loading Vite dev server) and production packaging.
const { app, BrowserWindow, shell, ipcMain, Tray, Menu, nativeImage, globalShortcut, powerMonitor } = require("electron");
const path = require("path");
const http = require("http");
const net = require("net");
const { spawn } = require("child_process");

const isDev = process.env.NODE_ENV === "development" || !app.isPackaged;
const projectRoot = path.join(__dirname, "..");

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
let backendStatus = { running: false, ready: false, port: 8765, error: null };
let restartCount = 0;
const maxRestarts = 3;

// Companion overlay window state
let companionVisible = false;
let companionPosition = { x: null, y: null };  // null = use default (bottom-right)
let companionDisplayMode = 'floating';   // full | floating | mini | invisible

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
async function startBackend() {
  backendPort = await findAvailablePort(8765);
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
      env: { ...process.env, PORT: backendPort.toString() },
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
        setTimeout(() => startBackend(), 2000 * restartCount);
      } else if (code !== 0) {
        backendStatus.error = `Backend crashed with exit code ${code}`;
      }
    });

    const ready = await waitForHealth(backendPort, 15000);
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
    ? "http://localhost:5173"
    : `file://${path.join(__dirname, "..", "dist", "index.html")}`;

  mainWindow.loadURL(mainUrl);

  if (isDev) {
    mainWindow.webContents.openDevTools({ mode: "undocked" });
  }

  // 2. Companion Overlay Window
  createCompanionWindow();
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
  const initialPos = validateCompanionPosition(
    companionPosition.x ?? 9999,
    companionPosition.y ?? 9999,
    280,
    340
  );

  companionWindow = new BrowserWindow({
    x: initialPos.x,
    y: initialPos.y,
    width: 280,
    height: 340,
    frame: false,
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable: false,        // Non-intrusive — never steals keyboard focus from Chrome/VS Code
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

  // Default to click-through mouse pass-through
  companionWindow.setIgnoreMouseEvents(true, { forward: true });

  // Always on top — screen-saver level on Windows
  companionWindow.setAlwaysOnTop(true, 'screen-saver');

  const companionUrl = isDev
    ? "http://localhost:5173?companion=1"
    : `file://${path.join(__dirname, "..", "dist", "index.html?companion=1")}`;

  companionWindow.loadURL(companionUrl);

  companionWindow.once('ready-to-show', () => {
    if (companionVisible) {
      companionWindow?.showInactive(); // Show without taking focus
    }
  });

  companionWindow.on('closed', () => {
    companionWindow = null;
  });
}

// ── Companion window size configs ─────────────────────────────────────────
const COMPANION_SIZES = {
  full:      { width: 380, height: 560 },
  floating:  { width: 280, height: 340 },
  mini:      { width: 120, height: 140 },
  invisible: { width: 1,   height: 1   },  // Hidden but keeps process active
};


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
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
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

  // Show/hide companion overlay
  ipcMain.on("companion:show", () => {
    if (companionWindow && !companionWindow.isDestroyed()) {
      companionVisible = true;
      companionWindow.show();
    }
  });

  ipcMain.on("companion:hide", () => {
    if (companionWindow && !companionWindow.isDestroyed()) {
      companionVisible = false;
      companionWindow.hide();
    }
  });

  // Set display mode — resizes the companion window
  ipcMain.on("companion:set-display-mode", (_, mode) => {
    const size = COMPANION_SIZES[mode] || COMPANION_SIZES.floating;
    companionDisplayMode = mode;
    if (companionWindow && !companionWindow.isDestroyed()) {
      companionWindow.setSize(size.width, size.height, true);
      if (mode === 'invisible') {
        companionWindow.setIgnoreMouseEvents(true, { forward: true });
      } else {
        // Let renderer decide click-through per-mode via companion:set-click-through
      }
    }
    // Notify main window of mode change
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("companion:display-mode-changed", mode);
    }
  });

  // Reposition companion window from renderer with multi-monitor safety
  ipcMain.on("companion:set-position", (_, { x, y }) => {
    if (companionWindow && !companionWindow.isDestroyed()) {
      const bounds = companionWindow.getBounds();
      const safePos = validateCompanionPosition(x, y, bounds.width, bounds.height);
      companionPosition = safePos;
      companionWindow.setPosition(safePos.x, safePos.y, false);
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

  ipcMain.handle("backend:get-status", () => backendStatus);
  ipcMain.handle("backend:get-port", () => backendPort);

  ipcMain.on("companion:trigger-quick-look", () => triggerQuickLook());
  ipcMain.on("companion:toggle-mode", () => toggleCompanionMode());
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

function toggleCompanionMode() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("companion:toggle-mode-triggered");
  }
}

// ── Tray Icon (§19) ──────────────────────────────────────────────────────────
function setupTray() {
  const iconPath = path.join(__dirname, "..", "public", "icon.png");
  let icon = nativeImage.createFromPath(iconPath);
  if (icon.isEmpty()) icon = nativeImage.createEmpty();

  tray = new Tray(icon);
  tray.setToolTip("Genie AI OS — Press Ctrl+Shift+G for Quick Look");

  tray.on("click", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  const menu = Menu.buildFromTemplate([
    {
      label: "Open Genie",
      click: () => {
        if (mainWindow) {
          if (mainWindow.isMinimized()) mainWindow.restore();
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    {
      label: "Quick Look (Ctrl+Shift+G)",
      click: () => triggerQuickLook(),
    },
    { type: "separator" },
    {
      label: "Toggle Companion Mode",
      click: () => toggleCompanionMode(),
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
      console.log("[Hotkey] Quick Look (Ctrl+Shift+G) triggered");
      triggerQuickLook();
    });
  } catch (err) {
    console.error("[Hotkey] Failed to register Ctrl+Shift+G:", err);
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
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
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
