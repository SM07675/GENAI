/**
 * CompanionWindow.tsx — Root router for Companion Mode.
 *
 * Architecture:
 * - Standalone Electron BrowserWindow: renders `DesktopCompanionOverlay` ONLY.
 *   The background is 100% transparent and stays always-on-top above Chrome, VS Code, etc.
 * - Browser/Non-Electron mode: renders `CompanionMode` in-app floating portal.
 */
import { AnimatePresence } from "framer-motion";

import CompanionOrb from "./CompanionOrb";
import CompanionMode from "./CompanionMode";
import DesktopCompanionOverlay from "./DesktopCompanionOverlay";
import { useCompanionStore } from "../../store/companionStore";

export default function CompanionWindow() {

  const mode = useCompanionStore((s) => s.mode);
  const launcherVisible = useCompanionStore((s) => s.launcherVisible);

  // Detect if running inside the dedicated Electron companion overlay window
  const genie = (typeof window !== "undefined" && (window as any).genie) || {};
  const isDedicatedElectronOverlay =
    genie.isCompanionOverlay ||
    (typeof window !== "undefined" && window.location.search.includes("companion=1"));

  // In dedicated Electron overlay window, render the standalone desktop overlay ONLY
  if (isDedicatedElectronOverlay) {
    return <DesktopCompanionOverlay />;
  }

  // The native Electron build already provides Companion Mode through the
  // dedicated desktop window (nav rail, Home pill, Ctrl+Shift+G). The
  // in-page launcher orb below exists only as a fallback for the plain
  // browser/dev target, where no separate desktop window is possible.
  if (genie.isElectron) return null;

  // Web/Browser fallback mode
  const isCompanionActive = mode !== "off";

  return (
    <>
      {/* Launcher orb — visible when companion is off in web mode */}
      <AnimatePresence>
        {!isCompanionActive && launcherVisible && <CompanionOrb />}
      </AnimatePresence>

      {/* Full companion mode — when companion is active in web mode */}
      <AnimatePresence>
        {isCompanionActive && <CompanionMode />}
      </AnimatePresence>
    </>
  );
}
