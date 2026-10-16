import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig } from "@playwright/test";

// The real portal on a seeded throwaway folder (login off, scheduler off). The database comes from the environment: NAVAAN_DATABASE_URL, or NAVAAN_PG_* (docker compose -f deploy/compose.dev.yml up -d).
export const PORT = process.env.E2E_PORT ?? "8799";
export const LISTENER_PORT = process.env.E2E_LISTENER_PORT ?? "8800";
export const GUEST_PORT = process.env.E2E_GUEST_PORT ?? "8801";
export const ROOT = process.env.E2E_ROOT ?? join(tmpdir(), "navaan-e2e");
const serverEnv = { ...process.env as Record<string, string>, NAVAAN_ROOT: ROOT, NAVAAN_AUTH: "off", NAVAAN_SCHEDULER: "off", NAVAAN_DB_SCHEMA_PER_PATH: "1", NAVAAN_LOG_DIR: join(ROOT, "logs"), NAVAAN_CACHE_DIR: join(ROOT, "cache"), NAVAAN_OBJSTORE_DIR: join(ROOT, "bucket") };
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
  webServer: [
    {   // the studio side: the one local person is the owner. It seeds the folder and the stand-in bucket first.
      command: `python3 seed.py "${ROOT}" && python3 ../../scripts/navaan.py serve --port ${PORT}`,
      url: `http://127.0.0.1:${PORT}/auth/state`, timeout: 120_000, reuseExistingServer: false, stdout: "pipe", env: serverEnv,
    },
    {   // the listener side: the same data, the one local person signed in as a listener (no studio access)
      command: `sh -c 'until [ -f "${ROOT}/.seeded" ]; do sleep 1; done; python3 ../../scripts/navaan.py serve --port ${LISTENER_PORT}'`,
      url: `http://127.0.0.1:${LISTENER_PORT}/auth/state`, timeout: 120_000, reuseExistingServer: false, stdout: "pipe", env: { ...serverEnv, NAVAAN_AUTH_OFF_ROLE: "listener" },
    },
    {   // the free public site: a public host and nobody signed in, so the visitor is a guest
      command: `sh -c 'until [ -f "${ROOT}/.seeded" ]; do sleep 1; done; python3 ../../scripts/navaan.py serve --port ${GUEST_PORT}'`,
      url: `http://127.0.0.1:${GUEST_PORT}/privacy`, timeout: 120_000, reuseExistingServer: false, stdout: "pipe", env: { ...serverEnv, NAVAAN_AUTH_OFF_ROLE: "guest", NAVAAN_PUBLIC_HOST: "127.0.0.1", NAVAAN_LISTENER_HOSTS: "127.0.0.1", NAVAAN_STUDIO_HOST: "studio.example" },
    },
  ],
});
