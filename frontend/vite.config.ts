/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": process.env.VITE_API_PROXY ?? "http://localhost:8000" },
  },
  build: {
    // Recharts (with its d3 dependencies) is the one large vendor chunk (~150 kB gzipped).
    chunkSizeWarningLimit: 600,
    rollupOptions: { output: { manualChunks: { vendor: ["react", "react-dom", "recharts"] } } },
  },
  test: { environment: "jsdom", globals: true },
});
