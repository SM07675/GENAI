// Electron preload. Exposes a secure, typed contextBridge surface to renderer.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("genie", {
  isElectron: true,
  isCompanionOverlay: false,
  platform: process.platform,

  // Frameless window controls
  minimize: () => ipcRenderer.send("window:minimize"),
  close: () => ipcRenderer.send("window:close"),
  focusMain: () => ipcRenderer.send("window:focus-main"),

  // ── Companion overlay window controls ────────────────────────────────────
  // These drive the second always-on-top BrowserWindow from the main renderer

  // Legacy: click-through toggle
  setCompanionClickThrough: (ignore) =>
    ipcRenderer.send("companion:set-click-through", ignore),

  // Show/hide the companion overlay window.
  // These are invoke (not send) because the UI must wait for a real,
  // verified result before it's allowed to claim "ACTIVE".
  showCompanion: () => ipcRenderer.invoke("companion:show"),
  hideCompanion: () => ipcRenderer.invoke("companion:hide"),
  toggleCompanion: () => ipcRenderer.invoke("companion:toggle"),
  getCompanionMode: () => ipcRenderer.invoke("companion:get-mode"),

  // Set display mode (resizes the companion window)
  setCompanionDisplayMode: (mode) =>
    ipcRenderer.send("companion:set-display-mode", mode),

  // Reposition the companion window
  setCompanionPosition: (x, y) =>
    ipcRenderer.send("companion:set-position", { x, y }),

  // Get the companion window's current bounds
  getCompanionBounds: () => ipcRenderer.invoke("companion:get-bounds"),

  // Enable/disable mouse interaction on the companion window
  setCompanionInteractive: (interactive) =>
    ipcRenderer.send("companion:set-interactive", interactive),

  // ── Backend sidecar ────────────────────────────────────────────────────────
  getBackendStatus: () => ipcRenderer.invoke("backend:get-status"),
  getBackendPort: () => ipcRenderer.invoke("backend:get-port"),
  getDesktopPin: () => ipcRenderer.invoke("backend:get-desktop-pin"),

  // ── Companion hotkeys / triggers ──────────────────────────────────────────
  triggerQuickLook: () => ipcRenderer.send("companion:trigger-quick-look"),
  toggleCompanionMode: () => ipcRenderer.send("companion:toggle-mode"),

  // ── Subscriptions from main process ──────────────────────────────────────
  onQuickLookTriggered: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("companion:quick-look-triggered", handler);
    return () => ipcRenderer.removeListener("companion:quick-look-triggered", handler);
  },
  onToggleModeTriggered: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("companion:toggle-mode-triggered", handler);
    return () => ipcRenderer.removeListener("companion:toggle-mode-triggered", handler);
  },
  onDisplayModeChanged: (callback) => {
    const handler = (_, mode) => callback(mode);
    ipcRenderer.on("companion:display-mode-changed", handler);
    return () => ipcRenderer.removeListener("companion:display-mode-changed", handler);
  },
  onCompanionModeChanged: (callback) => {
    const handler = (_, state) => callback(state);
    ipcRenderer.on("companion:mode-changed", handler);
    return () => ipcRenderer.removeListener("companion:mode-changed", handler);
  },
  onCompanionAction: (callback) => {
    const handler = (_, action) => callback(action);
    ipcRenderer.on("companion:action", handler);
    return () => ipcRenderer.removeListener("companion:action", handler);
  },
  onCompanionBackendControl: (callback) => {
    const handler = (_, action) => callback(action);
    ipcRenderer.on("companion:backend-control", handler);
    return () => ipcRenderer.removeListener("companion:backend-control", handler);
  },
  publishCompanionState: (state) => ipcRenderer.send("companion:publish-state", state),
});

