import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig } from "@playwright/test";

// The real portal on a seeded throwaway folder (login off, scheduler off). The database comes from the environment: NAVAAN_DATABASE_URL, or NAVAAN_PG_* (docker compose -f deploy/compose.dev.yml up -d).
export const PORT = process.env.E2E_PORT ?? "8799";
export const ROOT = process.env.E2E_ROOT ?? join(tmpdir(), "navaan-e2e");
export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, channel: "chrome", trace: "retain-on-failure" },
  projects: [
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, hasTouch: true } },
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
  ],
  webServer: {
    command: `python3 seed.py "${ROOT}" && python3 ../../scripts/navaan.py serve --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/auth/state`,
    timeout: 90_000,
    reuseExistingServer: false,
    stdout: "pipe",
    env: { ...process.env as Record<string, string>, NAVAAN_ROOT: ROOT, NAVAAN_AUTH: "off", NAVAAN_SCHEDULER: "off", NAVAAN_DB_SCHEMA_PER_PATH: "1", NAVAAN_LOG_DIR: join(ROOT, "logs"), NAVAAN_CACHE_DIR: join(ROOT, "cache") },
  },
});
