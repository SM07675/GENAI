/**
 * ipc.ts — Typed IPC message handler layer between Electron & Renderer.
 *
 * Responsibilities:
 * - Window controls (minimize, close, focus, set-click-through).
 * - Exposes backend port and status to renderer.
 * - Relays companion events & Quick Look requests.
 */
import { ipcMain, BrowserWindow } from "electron";
import { WindowManager } from "./window-manager";
import { BackendManager } from "./backend-manager";

export function registerIpcHandlers(
  windowManager: WindowManager,
  backendManager: BackendManager,
  onQuickLook: () => void,
  onCompanionToggle: () => void
): void {
  // Window controls
  ipcMain.on("window:minimize", (event) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    win?.minimize();
  });

  ipcMain.on("window:close", (event) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    win?.close();
  });

  ipcMain.on("window:focus-main", () => {
    windowManager.focusMain();
  });

  // Companion click-through
  ipcMain.on("companion:set-click-through", (_, ignore: boolean) => {
    windowManager.setCompanionClickThrough(ignore);
  });

  // Backend status
  ipcMain.handle("backend:get-status", () => {
    return backendManager.getStatus();
  });

  ipcMain.handle("backend:get-port", () => {
    return backendManager.getPort();
  });

  // Companion triggers
  ipcMain.on("companion:trigger-quick-look", () => {
    onQuickLook();
  });

  ipcMain.on("companion:toggle-mode", () => {
    onCompanionToggle();
  });
}
