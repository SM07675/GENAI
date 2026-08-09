/**
 * companionStore.ts — Companion Mode UI state (Zustand).
 *
 * Separate from appStore.js so companion can be stopped/started without
 * resetting the main Genie UI state. The main appStore reads
 * companionStore.isActive to show/hide the quick-toggle in MinimalControls.
 *
 * v2: Added displayMode (full/floating/mini/invisible), cameraActive,
 *     proactiveSuggestions, emotionState, contextSnapshot.
 */
import { create } from "zustand";

export type CompanionMode = "off" | "starting" | "active" | "paused" | "stopping";
export type CompanionSubMode = "general" | "gaming" | "coding" | "writing" | "quiet";
export type CompanionDisplayMode = "full" | "floating" | "mini" | "invisible";
export type CompanionOverlay =
  | "NONE"
  | "WATCHING"
  | "LISTENING"
  | "THINKING"
  | "EXCITED"
  | "WARNING"
  | "HAPPY"
  | "SAD"
  | "LAUGHING"
  | "PAUSED";

export interface CompanionPosition {
  x: number;
  y: number;
}

export interface ProactiveSuggestion {
  id: string;
  text: string;
  priority: number;
  type: string;
  createdAt: number;
}

export interface ContextSnapshot {
  currentApp: string;
  windowTitle: string;
  currentProject: string | null;
  openFile: string | null;
  activity: string;
  timestamp: number;
}

export interface CompanionState {
  // --- Mode -----------------------------------------------------------------
  mode: CompanionMode;
  subMode: CompanionSubMode;
  displayMode: CompanionDisplayMode;
  overlayState: CompanionOverlay;
  overlayIntensity: number;          // 0.0–1.0

  // --- Launcher & Bubble ---------------------------------------------------
  launcherVisible: boolean;          // Persistent launcher orb when mode === "off"
  bubbleText: string | null;         // Callout suggestion bubble text
  bubbleVisible: boolean;
  bubbleExpanded: boolean;

  // --- Privacy (always accurate, never cached) -----------------------------
  screenAware: boolean;
  micActive: boolean;
  cameraActive: boolean;             // NEW: camera feed active

  // --- Window position (persisted via localStorage) ------------------------
  position: CompanionPosition;
  isVisible: boolean;

  // --- Context & Memory -------------------------------------------------------
  contextSnapshot: ContextSnapshot | null;    // NEW: current context
  proactiveSuggestions: ProactiveSuggestion[];  // NEW: queued suggestions

  // --- Emotion state -------------------------------------------------------
  emotionState: string;              // NEW: current avatar emotion override

  // --- Last event -----------------------------------------------------------
  lastEvent: { type: string; importance: string; payload: Record<string, unknown> } | null;

  // --- Actions --------------------------------------------------------------
  setMode: (mode: CompanionMode, subMode?: CompanionSubMode) => void;
  setDisplayMode: (mode: CompanionDisplayMode) => void;
  setOverlay: (overlay: CompanionOverlay, intensity?: number) => void;
  setPrivacy: (screenAware: boolean, micActive: boolean, cameraActive?: boolean) => void;
  setPosition: (pos: CompanionPosition) => void;
  setVisible: (visible: boolean) => void;
  setLauncherVisible: (visible: boolean) => void;
  setBubble: (text: string | null, visible?: boolean) => void;
  toggleBubbleExpanded: () => void;
  setLastEvent: (event: CompanionState["lastEvent"]) => void;
  setContextSnapshot: (snapshot: ContextSnapshot | null) => void;
  addProactiveSuggestion: (suggestion: ProactiveSuggestion) => void;
  dismissProactiveSuggestion: (id: string) => void;
  setEmotionState: (emotion: string) => void;
  reset: () => void;
}

const STORED_POSITION_KEY = "genie-companion-position";
const STORED_DISPLAY_MODE_KEY = "genie-companion-display-mode";

function loadStoredPosition(): CompanionPosition {
  try {
    const raw = localStorage.getItem(STORED_POSITION_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  // Default: bottom-right quadrant
  return { x: typeof window !== "undefined" ? window.innerWidth - 180 : 1100, y: typeof window !== "undefined" ? window.innerHeight - 220 : 600 };
}

function loadStoredDisplayMode(): CompanionDisplayMode {
  try {
    const raw = localStorage.getItem(STORED_DISPLAY_MODE_KEY);
    if (raw && ["full", "floating", "mini", "invisible"].includes(raw)) return raw as CompanionDisplayMode;
  } catch {
    /* ignore */
  }
  return "floating";
}

export const useCompanionStore = create<CompanionState>((set) => ({
  // Initial state
  mode: "off",
  subMode: "general",
  displayMode: typeof window !== "undefined" ? loadStoredDisplayMode() : "floating",
  overlayState: "NONE",
  overlayIntensity: 0.5,
  launcherVisible: true,            // launcher visible by default so user can activate
  bubbleText: null,
  bubbleVisible: false,
  bubbleExpanded: false,
  screenAware: false,
  micActive: false,
  cameraActive: false,
  position: typeof window !== "undefined" ? loadStoredPosition() : { x: 80, y: 80 },
  isVisible: false,
  contextSnapshot: null,
  proactiveSuggestions: [],
  emotionState: "idle",
  lastEvent: null,

  // Actions
  setMode: (mode, subMode) =>
    set((s) => ({
      mode,
      subMode: subMode ?? s.subMode,
      isVisible: mode !== "off" || s.launcherVisible,
      overlayState: mode === "off" ? "NONE" : mode === "paused" ? "PAUSED" : s.overlayState,
    })),

  setDisplayMode: (displayMode) => {
    try {
      localStorage.setItem(STORED_DISPLAY_MODE_KEY, displayMode);
    } catch {
      /* ignore */
    }
    set({ displayMode });
  },

  setOverlay: (overlay, intensity) =>
    set({ overlayState: overlay, overlayIntensity: intensity ?? 0.5 }),

  setPrivacy: (screenAware, micActive, cameraActive) =>
    set({ screenAware, micActive, cameraActive: cameraActive ?? false }),

  setPosition: (pos) => {
    try {
      localStorage.setItem(STORED_POSITION_KEY, JSON.stringify(pos));
    } catch {
      /* ignore */
    }
    set({ position: pos });
  },

  setVisible: (visible) => set({ isVisible: visible }),

  setLauncherVisible: (visible) => set({ launcherVisible: visible }),

  setBubble: (text, visible = true) =>
    set({
      bubbleText: text,
      bubbleVisible: text !== null ? visible : false,
      bubbleExpanded: false,
    }),

  toggleBubbleExpanded: () => set((s) => ({ bubbleExpanded: !s.bubbleExpanded })),

  setLastEvent: (event) => set({ lastEvent: event }),

  setContextSnapshot: (snapshot) => set({ contextSnapshot: snapshot }),

  addProactiveSuggestion: (suggestion) =>
    set((s) => ({
      proactiveSuggestions: [
        ...s.proactiveSuggestions.filter((x) => x.id !== suggestion.id),
        suggestion,
      ].slice(-5), // keep max 5
    })),

  dismissProactiveSuggestion: (id) =>
    set((s) => ({
      proactiveSuggestions: s.proactiveSuggestions.filter((x) => x.id !== id),
    })),

  setEmotionState: (emotion) => set({ emotionState: emotion }),

  reset: () =>
    set({
      mode: "off",
      subMode: "general",
      overlayState: "NONE",
      bubbleText: null,
      bubbleVisible: false,
      bubbleExpanded: false,
      screenAware: false,
      micActive: false,
      cameraActive: false,
      isVisible: false,
      contextSnapshot: null,
      proactiveSuggestions: [],
      emotionState: "idle",
      lastEvent: null,
    }),
}));
