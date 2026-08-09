/**
 * tray-manager.ts — System Tray Icon & Context Menu Manager.
 *
 * Responsibilities (§19, §20):
 * - Renders Genie system tray icon in Windows taskbar tray.
 * - Single left-click toggles main window visibility.
 * - Right-click context menu: Show Genie, Start/Stop Companion, Quick Look, Settings, Quit.
 */
import { Tray, Menu, nativeImage, app } from "electron";
import path from "path";
import { WindowManager } from "./window-manager";

export class TrayManager {
  private tray: Tray | null = null;
  private windowManager: WindowManager;
  private onCompanionToggle: () => void;
  private onQuickLook: () => void;
  private isCompanionActive: boolean = false;

  constructor(
    windowManager: WindowManager,
    onCompanionToggle: () => void,
    onQuickLook: () => void
  ) {
    this.windowManager = windowManager;
    this.onCompanionToggle = onCompanionToggle;
    this.onQuickLook = onQuickLook;
  }

  public init(): void {
    const iconPath = path.join(__dirname, "..", "..", "public", "icon.png");
    let icon = nativeImage.createFromPath(iconPath);
    if (icon.isEmpty()) {
      // Fallback 1x1 transparent pixel if icon not yet on disk
      icon = nativeImage.createEmpty();
    }

    this.tray = new Tray(icon);
    this.tray.setToolTip("Genie AI OS — Press Ctrl+Shift+G for Quick Look");

    this.tray.on("click", () => {
      this.windowManager.focusMain();
    });

    this.updateContextMenu();
  }

  public setCompanionActive(active: boolean): void {
    this.isCompanionActive = active;
    this.updateContextMenu();
  }

  public updateContextMenu(): void {
    if (!this.tray) return;

    const contextMenu = Menu.buildFromTemplate([
      {
        label: "Open Genie",
        click: () => this.windowManager.focusMain(),
      },
      {
        label: "Quick Look (Ctrl+Shift+G)",
        click: () => this.onQuickLook(),
      },
      { type: "separator" },
      {
        label: this.isCompanionActive ? "Stop Companion Mode" : "Start Companion Mode",
        click: () => this.onCompanionToggle(),
      },
      { type: "separator" },
      {
        label: "Quit Genie",
        click: () => app.quit(),
      },
    ]);

    this.tray.setContextMenu(contextMenu);
  }

  public destroy(): void {
    if (this.tray) {
      this.tray.destroy();
      this.tray = null;
    }
  }
}
