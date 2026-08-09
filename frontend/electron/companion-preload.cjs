// companion-preload.cjs — Secure preload for the companion overlay BrowserWindow.
//
// Exposes a restricted surface for the companion overlay renderer.
// This window has NO access to main window controls (minimize/close),
// only companion-specific IPC channels.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('genie', {
  isElectron: true,
  isCompanionOverlay: true,   // lets React know it's in overlay mode
  platform: process.platform,

  // Companion window controls
  setClickThrough: (ignore) =>
    ipcRenderer.send('companion:set-click-through', ignore),

  setInteractive: (interactive) =>
    ipcRenderer.send('companion:set-interactive', interactive),

  setDisplayMode: (mode) =>
    ipcRenderer.send('companion:set-display-mode', mode),

  setPosition: (x, y) =>
    ipcRenderer.send('companion:set-position', { x, y }),

  getBounds: () =>
    ipcRenderer.invoke('companion:get-bounds'),

  // Focus the main Genie window
  focusMain: () =>
    ipcRenderer.send('window:focus-main'),

  // Quick Look shortcut
  triggerQuickLook: () =>
    ipcRenderer.send('companion:trigger-quick-look'),

  // Backend sidecar
  getBackendPort: () =>
    ipcRenderer.invoke('backend:get-port'),

  getBackendStatus: () =>
    ipcRenderer.invoke('backend:get-status'),

  // Subscriptions (receive events from main process)
  onQuickLookTriggered: (callback) => {
    const handler = () => callback();
    ipcRenderer.on('companion:quick-look-triggered', handler);
    return () => ipcRenderer.removeListener('companion:quick-look-triggered', handler);
  },

  onToggleModeTriggered: (callback) => {
    const handler = () => callback();
    ipcRenderer.on('companion:toggle-mode-triggered', handler);
    return () => ipcRenderer.removeListener('companion:toggle-mode-triggered', handler);
  },

  onDisplayModeChanged: (callback) => {
    const handler = (_, mode) => callback(mode);
    ipcRenderer.on('companion:display-mode-changed', handler);
    return () => ipcRenderer.removeListener('companion:display-mode-changed', handler);
  },
});
