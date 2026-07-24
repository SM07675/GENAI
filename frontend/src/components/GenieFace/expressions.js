export const STATE_COLORS = {
  sleeping: "#a78bfa",
  waking: "#22d3ee",
  idle: "#3b82f6",
  listening: "#38bdf8",
  thinking: "#8b5cf6",
  speaking: "#06b6d4",
  happy: "#22c55e",
  excited: "#f59e0b",
  surprised: "#fbbf24",
  confused: "#f59e0b",
  sad: "#60a5fa",
  error: "#fb923c"
};

export const getEmotionForState = (genieState, textEmotion) => {
  if (genieState === 'sleeping') return 'sleeping';
  if (genieState === 'waking') return 'waking';
  if (genieState === 'listening') return 'listening';
  if (genieState === 'thinking') return 'thinking';
  if (genieState === 'error') return 'error';
  
  if (textEmotion) return textEmotion;
  
  if (genieState === 'speaking') return 'speaking';
  return 'idle';
};
