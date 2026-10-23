import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Django API runs on :8000 in development; proxying keeps the browser on a
// single origin so no CORS preflight is needed while iterating.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The editor/agent writes files atomically, which leaves short-lived
    // ".name.tmpdir" siblings behind; watching them makes chokidar throw EBUSY.
    watch: { ignored: ["**/.*.tmpdir/**", "**/node_modules/**", "**/dist/**"] },
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 900 },
});
