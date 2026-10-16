// Lighthouse mobile gate (NAV-20): performance and accessibility must be 90 or more on the main screens, as the median of RUNS runs each (one run is too noisy to gate on).
// Starts the same seeded portal as the Playwright checks, so it needs the database too (NAVAAN_DATABASE_URL, or NAVAAN_PG_*).
import { spawn, spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { launch } from "chrome-launcher";
import lighthouse from "lighthouse";

const PORT = process.env.E2E_PORT ?? "8798", ROOT = process.env.E2E_ROOT ?? join(tmpdir(), "navaan-lh"), BASE = `http://127.0.0.1:${PORT}`;
const RUNS = Number(process.env.LH_RUNS ?? 3), MIN = Number(process.env.LH_MIN ?? 90);
const URLS = ["/app/", "/app/studio/songs", "/app/studio/songs/song-001", "/app/studio/schedule"];
const median = (a) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)];

const seed = spawnSync("python3", ["seed.py", ROOT], { stdio: "inherit" });
if (seed.status) process.exit(seed.status);
const server = spawn("python3", ["../../scripts/navaan.py", "serve", "--port", PORT], { stdio: "ignore",
  env: { ...process.env, NAVAAN_ROOT: ROOT, NAVAAN_AUTH: "off", NAVAAN_SCHEDULER: "off", NAVAAN_DB_SCHEMA_PER_PATH: "1", NAVAAN_LOG_DIR: join(ROOT, "logs"), NAVAAN_CACHE_DIR: join(ROOT, "cache") } });
let chrome; let failed = false;
try {
  for (let i = 0; i < 90; i++) { try { if ((await fetch(`${BASE}/auth/state`)).ok) break; } catch { /* not up yet */ } await new Promise((r) => setTimeout(r, 1000)); }
  chrome = await launch({ chromeFlags: ["--headless=new", "--no-sandbox"] });
  for (const path of URLS) {
    const perf = [], a11y = [], bp = [];
    for (let i = 0; i < RUNS; i++) {
      const r = await lighthouse(BASE + path, { port: chrome.port, output: "json", logLevel: "error", onlyCategories: ["performance", "accessibility", "best-practices"] });
      const c = r.lhr.categories; perf.push(Math.round(c.performance.score * 100)); a11y.push(Math.round(c.accessibility.score * 100)); bp.push(Math.round(c["best-practices"].score * 100));
    }
    const row = { performance: median(perf), accessibility: median(a11y), "best-practices": median(bp) };
    const bad = ["performance", "accessibility"].filter((k) => row[k] < MIN);
    console.log(`${bad.length ? "FAIL" : "ok  "} ${path}  performance ${perf.join("/")} (median ${row.performance})  accessibility ${a11y.join("/")} (median ${row.accessibility})  best-practices median ${row["best-practices"]}`);
    if (bad.length) failed = true;
  }
} finally { await chrome?.kill(); server.kill(); }
if (failed) { console.error(`Lighthouse mobile below ${MIN}`); process.exit(1); }
