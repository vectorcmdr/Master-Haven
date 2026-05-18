import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config for the Travelers Archive frontend.
// - dev server proxies /api/* to the local backend (port 8020)
// - build emits to ../app_static/ so the Dockerfile can copy it
//   into the Python image
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": "http://localhost:8020",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
  },
});
