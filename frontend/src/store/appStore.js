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

  // --- Connection actions ---------------------------------------------
  setWs: (ws) => set({ ws }),
  setWsStatus: (status) => set({ wsStatus: status }),
  setPublicUrl: (url) => set({ publicUrl: url }),

  // --- Orb -------------------------------------------------------------
  setOrbState: (state) => set({ orbState: state }),
  // Live mic amplitude (0..1) published by the recorder; drives the orb's
  // sound-wave ring while listening.
  amplitude: 0,
  setAmplitude: (v) => set({ amplitude: v }),

  // --- Transcript actions ---------------------------------------------
  pushUserMessage: (text) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { id: crypto.randomUUID(), role: "user", text, ts: Date.now() },
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
    }),
}));
