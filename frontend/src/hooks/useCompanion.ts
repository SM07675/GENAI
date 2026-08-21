/**
 * useCompanion.ts — React hook wiring the companion window/overlay to the WS store & Electron IPC.
 *
 * Listens to Electron window.genie IPC and WS backend events.
 * Controls mode, display mode, positions, and IPC window triggers.
 */
import { useEffect, useCallback } from "react";
import { useAppStore } from "../store/appStore";
import {
  useCompanionStore,
  type CompanionMode,
  type CompanionSubMode,
  type CompanionOverlay,
  type CompanionDisplayMode,
} from "../store/companionStore";

export function useCompanion() {
  const { setMode, setDisplayMode, setOverlay, setPrivacy, setLastEvent, position } = useCompanionStore();
  const mode = useCompanionStore((s) => s.mode);
  const displayMode = useCompanionStore((s) => s.displayMode);
  const ws = useAppStore((s) => s.ws);

  // ── Send companion control commands via WS connection ─────────────────────
  const sendCompanionCommand = useCallback(
    (type: string, payload: Record<string, unknown> = {}) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      ws.send(JSON.stringify({ type, ...payload }));
    },
    [ws]
  );

  // ── Truthful start/stop ─────────────────────────────────────────────────
  // Do NOT flip the store to "active" optimistically. Go through "starting"
  // and only land on "active" once the main process confirms the companion
  // BrowserWindow actually exists and is visible. On failure, fall back to
  // "off" rather than silently lying to the UI.
  const startCompanion = useCallback(
    async (subMode?: CompanionSubMode) => {
      setMode("starting", subMode);

      const genie = (window as any).genie;
      if (!genie || !genie.isElectron) {
        sendCompanionCommand("companion_start", subMode ? { mode: subMode } : {});
        setMode("active", subMode);
        return;
      }

      try {
        const result = await genie.showCompanion?.();
        if (result?.success) {
          setMode("active", subMode);
        } else {
          console.error("[Companion] Failed to start:", result?.error);
          setMode("off");
        }
      } catch (err) {
        console.error("[Companion] Failed to start:", err);
        setMode("off");
      }
    },
    [sendCompanionCommand, setMode]
  );

  const stopCompanion = useCallback(async () => {
    setMode("stopping");

    const genie = (window as any).genie;
    if (genie && genie.isElectron) {
      try {
        await genie.hideCompanion?.();
      } catch (err) {
        console.error("[Companion] Failed to hide window cleanly:", err);
      }
    } else {
      sendCompanionCommand("companion_stop");
    }
    setMode("off");
  }, [sendCompanionCommand, setMode]);

  const pauseCompanion = useCallback(() => {
    sendCompanionCommand("companion_pause");
    setMode("paused");
  }, [sendCompanionCommand, setMode]);

  const resumeCompanion = useCallback(() => {
    sendCompanionCommand("companion_resume");
    setMode("active");
  }, [sendCompanionCommand, setMode]);

  const setCompanionSubMode = useCallback(
    (subMode: CompanionSubMode) => {
      sendCompanionCommand("companion_set_mode", { mode: subMode });
    },
    [sendCompanionCommand]
  );

  const requestAnalysis = useCallback(() => {
    sendCompanionCommand("companion_hotkey_analyze");
  }, [sendCompanionCommand]);

  const requestQuickLook = useCallback(
    (text?: string) => {
      sendCompanionCommand("companion_quick_look", text ? { text } : {});
    },
    [sendCompanionCommand]
  );

  // ── Electron Sync for Overlay Window ──────────────────────────────────────
  // Note: show/hide is intentionally NOT driven from here — it's called
  // explicitly (and awaited) from startCompanion()/stopCompanion() above, so
  // the store only reaches "active" after main.cjs confirms the window is
  // real and visible. This effect just keeps display mode in sync while
  // already active; it never claims a status it hasn't verified.
  useEffect(() => {
    const genie = (window as any).genie;
    if (!genie || !genie.isElectron) return;
    if (mode !== "active") return;

    genie.setCompanionDisplayMode?.(displayMode);
  }, [mode, displayMode]);

  // Handle hotkeys & IPC events from Electron main process
  useEffect(() => {
    const genie = (window as any).genie;
    if (!genie || !genie.isElectron) return;

    const unSubQuickLook = genie.onQuickLookTriggered?.(() => {
      requestQuickLook();
    });

    const unSubToggleMode = genie.onToggleModeTriggered?.(() => {
      if (mode === "off") {
        startCompanion();
      } else {
        stopCompanion();
      }
    });

    const unSubDisplayMode = genie.onDisplayModeChanged?.((newMode: CompanionDisplayMode) => {
      setDisplayMode(newMode);
    });

    const unSubMode = genie.onCompanionModeChanged?.((state: { active: boolean }) => {
      setMode(state.active ? "active" : "off");
    });

    const unSubBackendControl = genie.onCompanionBackendControl?.((action: { type: string }) => {
      if (action?.type === "companion_start" || action?.type === "companion_stop") {
        sendCompanionCommand(action.type);
      }
    });

    return () => {
      unSubQuickLook?.();
      unSubToggleMode?.();
      unSubDisplayMode?.();
      unSubMode?.();
      unSubBackendControl?.();
    };
  }, [mode, startCompanion, stopCompanion, requestQuickLook, setDisplayMode, setMode, sendCompanionCommand]);

  return {
    startCompanion,
    stopCompanion,
    pauseCompanion,
    resumeCompanion,
    setCompanionSubMode,
    requestAnalysis,
    requestQuickLook,
  };
}
