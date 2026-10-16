/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The portal serves the build at /app/ (navaan_ui.py). /api and /auth belong to the same server, so a dev server proxies them to a running portal.
export default defineConfig({
  base: "/app/",
  plugins: [react()],
  build: { outDir: "dist", sourcemap: false, target: "es2022" },
  server: { proxy: { "/api": "http://127.0.0.1:8765", "/auth": "http://127.0.0.1:8765" } },
  test: { globals: true, environment: "jsdom", setupFiles: ["./src/test-setup.ts"], css: false, include: ["src/**/*.test.{ts,tsx}"] },
});
