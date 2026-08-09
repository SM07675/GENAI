/**
 * shortcuts.ts — Global keyboard shortcut manager.
 *
 * Responsibilities (§6.2, §20):
 * - Registers global desktop shortcut `Ctrl+Shift+G` for instant Quick Look.
 * - Handles unregistration on app exit.
 */
import { globalShortcut } from "electron";

export class ShortcutManager {
  private shortcut: string = "CommandOrControl+Shift+G";
  private onQuickLook: () => void;

  constructor(onQuickLook: () => void) {
    this.onQuickLook = onQuickLook;
  }

  public register(): boolean {
    try {
      const ret = globalShortcut.register(this.shortcut, () => {
        console.log("[Shortcuts] Quick Look shortcut triggered (Ctrl+Shift+G)");
        this.onQuickLook();
      });

      if (!ret) {
        console.warn(`[Shortcuts] Registration failed for shortcut: ${this.shortcut}`);
        return false;
      }
      console.log(`[Shortcuts] Registered global shortcut: ${this.shortcut}`);
      return true;
    } catch (err) {
      console.error("[Shortcuts] Error registering shortcut:", err);
      return false;
    }
  }

  public unregisterAll(): void {
    globalShortcut.unregisterAll();
    console.log("[Shortcuts] Unregistered all global shortcuts");
  }
}
