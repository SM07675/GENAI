// Electron preload. Exposes a tiny, safe bridge to the renderer.
// Currently we only expose app metadata + window controls for the frameless UI.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("genie", {
  isElectron: true,
  platform: process.platform,
  // The frameless window uses these to minimize/close.
  minimize: () => ipcRenderer.send("window:minimize"),
  close: () => ipcRenderer.send("window:close"),
});
