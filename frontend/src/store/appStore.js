// Global UI state for Genie via Zustand. Keeps the WebSocket status, orb state,
// chat transcript, and connection metadata in one reactive store.
import { create } from "zustand";

// Orb/pipeline states mirror the backend's orb_state messages.
export const ORB_STATES = {
  IDLE: "idle",
  LISTENING: "listening",
  THINKING: "thinking",
  SPEAKING: "speaking",
};

export const GENIE_STATES = {
  INITIALIZING: "initializing",
  OFFLINE: "offline",
  SLEEPING: "sleeping",
  WAKING: "waking",
  IDLE: "idle",
  LISTENING: "listening",
  TRANSCRIBING: "transcribing",
  THINKING: "thinking",
  EXECUTING: "executing",
  SPEAKING: "speaking",
  FOLLOW_UP: "follow_up_listening",
  INTERRUPTED: "interrupted",
  SUCCESS: "success",
  ERROR: "error",
};

const GENIE_STATE_TRANSITIONS = {
  initializing: ["idle", "offline", "error"],
  offline: ["initializing", "idle", "error"],
  sleeping: ["waking", "idle", "offline", "error"],
  waking: ["listening", "idle", "error"],
  idle: ["sleeping", "waking", "listening", "thinking", "offline", "error"],
  listening: ["transcribing", "idle", "interrupted", "error"],
  transcribing: ["thinking", "idle", "interrupted", "error"],
  thinking: ["executing", "speaking", "success", "idle", "interrupted", "error"],
  executing: ["speaking", "success", "idle", "interrupted", "error"],
  speaking: ["success", "follow_up_listening", "idle", "interrupted", "error"],
  follow_up_listening: ["listening", "idle", "sleeping", "interrupted", "error"],
  interrupted: ["listening", "idle", "sleeping"],
  success: ["idle", "sleeping"],
  error: ["idle", "sleeping"],
};

function isValidGenieTransition(current, next) {
  if (current === next) return true;
  return (GENIE_STATE_TRANSITIONS[current] || []).includes(next);
}

const DEFAULT_SETTINGS = {
  wakeWordEnabled: true,
  showSubtitles: true,
  reducedMotion: false,
  animationIntensity: "normal",
};

function loadStoredSettings() {
  if (typeof localStorage === "undefined") return DEFAULT_SETTINGS;
  try {
    const raw = localStorage.getItem("genie-ui-settings");
    if (!raw) return DEFAULT_SETTINGS;
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export const useAppStore = create((set, get) => ({
  // --- Connection ------------------------------------------------------
  ws: null,                         // active WebSocket instance
  wsStatus: "disconnected",         // disconnected|connecting|connected|authed|error
  publicUrl: null,                  // ngrok public URL (for mobile pairing)

  // --- Conversation ----------------------------------------------------
  messages: [],                     // [{id, role:'user'|'assistant', text, ts, toolEvents:[]}]
  orbState: ORB_STATES.IDLE,
  currentAssistantId: null,         // id of the assistant message currently streaming
  activeToolEvents: [],             // tool_start/tool_end in flight, for inline UI
  assistantAudioElement: null,      // HTMLAudioElement for WebGL viseme analysis

  // --- Connection actions ---------------------------------------------
  setWs: (ws) => set({ ws }),
  setWsStatus: (status) => set({ wsStatus: status }),
  setPublicUrl: (url) => set({ publicUrl: url }),

  // --- Orb -------------------------------------------------------------
  setOrbState: (state) => set({ orbState: state }),
  setAssistantAudioElement: (el) => set({ assistantAudioElement: el }),
  // Live mic amplitude (0..1) published by the recorder; drives the orb's
  // sound-wave ring while listening.
  amplitude: 0,
  setAmplitude: (v) => set({ amplitude: v }),
  
  // ── Voice pipeline state machine ──────────────────────────────────────────
  // Single source of truth for the entire voice interaction lifecycle.
  // States: IDLE | WAKE_DETECTED | LISTENING | USER_SPEAKING | SILENCE_WAIT
  //         | SUBMITTING | PROCESSING | ASSISTANT_SPEAKING | ERROR
  voiceState: "wake_listening",
  setVoiceState: (s) => set({ voiceState: s }),

  // ── New Genie Central State Machine ──────────────────────────────────────
  genieState: "sleeping",
  setGenieState: (nextState, { force = false } = {}) =>
    set((state) => {
      if (!Object.values(GENIE_STATES).includes(nextState)) return {};
      if (!force && !isValidGenieTransition(state.genieState, nextState)) {
        console.debug(`[GenieState] ignored invalid transition ${state.genieState} -> ${nextState}`);
        return {};
      }
      return { genieState: nextState };
    }),
  forceGenieState: (nextState) => get().setGenieState(nextState, { force: true }),

  // True while TTS audio is playing (used for echo prevention)
  isTTSPlaying: false,
  setIsTTSPlaying: (v) => set({ isTTSPlaying: v }),

  // Transient notice from backend (e.g. "Cloud AI is busy — using offline mode")
  // Set by system_note WS messages; auto-cleared after 6 seconds.
  systemNote: null,

  // Live interim transcript shown while user is speaking
  liveTranscript: "",
  setLiveTranscript: (t) => set({ liveTranscript: t }),

  // Partial transcript from STT worker
  partialTranscript: "",
  setPartialTranscript: (t) => set({ partialTranscript: t }),

  // Interruption tracking
  isInterrupted: false,
  setIsInterrupted: (v) => set({ isInterrupted: v }),

  // Voice pipeline callbacks — set by App.jsx after hook initialization
  // Allows VoiceBar to call toggleListening without prop drilling
  toggleListening: null,
  setToggleListening: (toggleListening) => set({ toggleListening }),

  // Delivery cue gesture state — driven by [[cue]] tags from the LLM
  currentGesture: null,   // { cue: "warm", color: "#f59e0b", pulse: "gentle", intensity: 0.6 }
  // Word-level timing data from Edge TTS — keyed by sentence seq number
  wordTimings: {},        // { 0: [{word, offset_ms, duration_ms}, ...], 1: [...] }

  // --- Robot Emotion ---------------------------------------------------
  // The currently active emotional display state for the Genie robot face.
  // Updated by emotionController (priority-based) or directly by orbState changes.
  robotEmotion: { emotion: 'neutral', intensity: 1.0, source: 'idle' },
  setRobotEmotion: (emotionData) => set({ robotEmotion: emotionData }),

  // --- Background Media -----------------------------------------------
  backgroundMedia: null,  // { video_id?: string, playlist_id?: string }
  playBackgroundMedia: (media) => set({ backgroundMedia: media }),
  stopBackgroundMedia: () => set({ backgroundMedia: null }),

  // --- Transcript actions ---------------------------------------------
  pushUserMessage: (text) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { id: crypto.randomUUID(), role: "user", text, ts: Date.now() },
      ],
    })),

  pushAssistantError: (text) =>
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text,
          ts: Date.now(),
          isError: true,
        },
      ],
    })),

  // Start a new assistant bubble that we'll stream deltas into.
  beginAssistantMessage: () => {
    const id = crypto.randomUUID();
    set((s) => ({
      currentAssistantId: id,
      messages: [
        ...s.messages,
        { id, role: "assistant", text: "", ts: Date.now(), toolEvents: [] },
      ],
    }));
    return id;
  },

  // Append a text delta to the current assistant message.
  appendAssistantDelta: (delta) =>
    set((s) => {
      if (!s.currentAssistantId) return {};
      return {
        messages: s.messages.map((m) =>
          m.id === s.currentAssistantId ? { ...m, text: m.text + delta } : m
        ),
      };
    }),

  // Attach a tool event to the current assistant message.
  addToolEvent: (evt) =>
    set((s) => {
      if (!s.currentAssistantId) return {};
      return {
        messages: s.messages.map((m) =>
          m.id === s.currentAssistantId
            ? { ...m, toolEvents: [...(m.toolEvents || []), evt] }
            : m
        ),
        activeToolEvents:
          evt.type === "tool_start"
            ? [...s.activeToolEvents, evt]
            : s.activeToolEvents.filter((e) => e.name !== evt.name),
      };
    }),

  clearActiveTools: () => set({ activeToolEvents: [] }),
  endAssistantMessage: () => set({ currentAssistantId: null }),

  reset: () =>
    set({
      messages: [],
      orbState: ORB_STATES.IDLE,
      currentAssistantId: null,
      activeToolEvents: [],
      currentGesture: null,
      wordTimings: {},
    }),
}));
