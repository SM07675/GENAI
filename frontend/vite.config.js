import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config. We use a relative base so the built assets work both when
// served by Vite (desktop dev) and when loaded over the ngrok URL (mobile).
// The FastAPI backend runs on :8765; in dev we proxy nothing because the UI
// talks to it over WebSocket directly.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
