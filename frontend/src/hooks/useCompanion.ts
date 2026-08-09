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

  const startCompanion = useCallback(
    (subMode?: CompanionSubMode) => {
      sendCompanionCommand("companion_start", subMode ? { mode: subMode } : {});
      setMode("active", subMode);
    },
    [sendCompanionCommand, setMode]
  );

  const stopCompanion = useCallback(() => {
    sendCompanionCommand("companion_stop");
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
  useEffect(() => {
    const genie = (window as any).genie;
    if (!genie || !genie.isElectron) return;

    if (mode !== "off") {
      genie.showCompanion?.();
      genie.setCompanionDisplayMode?.(displayMode);
      genie.setCompanionPosition?.(position.x, position.y);
    } else {
      genie.hideCompanion?.();
    }
  }, [mode, displayMode, position.x, position.y]);

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

    return () => {
      unSubQuickLook?.();
      unSubToggleMode?.();
      unSubDisplayMode?.();
    };
  }, [mode, startCompanion, stopCompanion, requestQuickLook, setDisplayMode]);

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
