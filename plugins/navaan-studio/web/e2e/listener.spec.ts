import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { LISTENER_PORT } from "./playwright.config";

// The listener side: the same data, signed in as a listener (no studio access). Songs seeded: song-010 and song-011 confirmed, song-012 published but not confirmed.
const L = `http://127.0.0.1:${LISTENER_PORT}`;
test.use({ baseURL: L });

const token = (page: Page) => page.locator('meta[name="navaan-token"]').getAttribute("content");
async function post(page: Page, path: string, body: unknown) {
  const t = await token(page);
  return page.evaluate(async ([p, b, tok]) => (await fetch(p as string, { method: "POST", headers: { "Content-Type": "application/json", "X-Navaan-Token": tok as string }, body: JSON.stringify(b) })).status, [path, body, t]);
}

// The Library's New playlist form asks for a name, what it is for, and who can see it.
async function newPlaylist(page: Page, name: string) {
  await page.getByRole("button", { name: /New playlist/ }).click(); await page.getByLabel("Name", { exact: true }).fill(name); await page.getByRole("button", { name: "Create playlist" }).click();
}

test("browse shows only confirmed songs, with no studio in sight", async ({ page }) => {
  await page.goto("/app/");
  await expect(page.getByRole("heading", { name: "Browse", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: /Tere Hone Se/ }).first()).toBeVisible();
  await expect(page.getByText("From Then to Forever")).toHaveCount(0);     // published, licence not confirmed: a listener does not see it
  await expect(page.getByRole("link", { name: "Studio" })).toHaveCount(0);
  const r = await page.request.get(`${L}/api/songs`); expect(r.status()).toBe(403);   // and the studio is closed to this person
});

test("a song plays, its lyrics follow it, and play mode opens and closes", async ({ page }) => {
  await page.goto("/app/song/song-010");
  await expect(page.getByRole("heading", { name: "Tere Hone Se", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Play", exact: true }).first().click();
  await expect.poll(() => page.evaluate(() => document.querySelector("audio")!.currentTime), { timeout: 15_000 }).toBeGreaterThan(1.5);
  await expect(page.locator('.lyrics li[aria-current="true"]').first()).toBeVisible();   // the current line is marked
  await page.getByRole("button", { name: "Open play mode" }).first().click();
  const pm = page.getByRole("dialog", { name: "Play mode" }); await expect(pm).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press("Escape"); await expect(pm).toHaveCount(0);
  await page.getByRole("button", { name: "Pause", exact: true }).first().click();
});

test("a shared link opens for someone who is not signed in", async ({ page, browser }) => {
  await page.goto("/app/song/song-011");
  await page.getByRole("button", { name: "Share", exact: true }).click();   // the Share button opens the sheet and makes the link
  const url = await page.getByLabel(/can listen, free/).inputValue(); expect(url).toContain("/s/");
  for (const n of ["WhatsApp", "X", "Facebook", "Threads", "Telegram"]) await expect(page.getByRole("link", { name: new RegExp(`^${n}`) })).toBeVisible();   // where to send it
  const anon = await browser.newContext(); const ap = await anon.newPage();
  const res = await ap.goto(url.replace(/^https?:\/\/[^/]+/, L)); expect(res!.status()).toBe(200);
  await expect(ap.getByRole("heading", { name: "Pata Hi Na Chala", level: 1 })).toBeVisible();
  expect(await ap.locator('meta[property="og:title"]').getAttribute("content")).toBe("Pata Hi Na Chala");
  const prev = await ap.request.get(L + new URL(url).pathname + "/preview.mp3"); expect(prev.status()).toBe(200); expect(prev.headers()["content-type"]).toContain("audio");
  await page.getByRole("button", { name: "Stop sharing" }).click(); await expect(page.getByText("That link no longer works.")).toBeVisible();
  expect((await ap.request.get(url.replace(/^https?:\/\/[^/]+/, L))).status()).toBe(404);   // stopped: it no longer opens
  await anon.close();
  const unconfirmed = await page.request.post(`${L}/api/share`, { headers: { "X-Navaan-Token": (await token(page)) ?? "" }, data: { slug: "song-012" } }); expect(unconfirmed.status()).toBe(404);   // not visible to a listener at all
});

test("the free plan stops at three playlists with a clear way on, and a person can tidy up", async ({ page }, info) => {
  await page.goto("/app/library");
  const names = [1, 2, 3, 4].map((i) => `Limit ${info.project.name} ${i}`);
  for (const n of names.slice(0, 3)) { await newPlaylist(page, n); await expect(page.getByRole("link", { name: new RegExp(n) })).toBeVisible(); }
  await newPlaylist(page, names[3]);
  const alert = page.getByRole("alert").filter({ hasText: /plan includes 3/ }); await expect(alert).toBeVisible();
  await alert.getByRole("link", { name: /See the plans/ }).click(); await expect(page.getByRole("heading", { name: "Plans", level: 1 })).toBeVisible(); await expect(page.getByText(/3 of 3 playlists used/)).toBeVisible();
  await page.goto("/app/library");
  for (const n of names.slice(0, 3)) { await page.getByRole("link", { name: new RegExp(n) }).click(); await page.getByRole("button", { name: "Delete playlist" }).click(); await page.getByRole("button", { name: "Yes, delete" }).click(); await expect(page.getByRole("heading", { name: "Library", level: 1 }).first()).toBeVisible(); }
  await expect(page.getByRole("link", { name: /Limit / })).toHaveCount(0);
});

test("a playlist can be filled from a song page and the library songs can be filtered", async ({ page }, info) => {
  const name = `Fill ${info.project.name}`;
  await page.goto("/app/library"); await newPlaylist(page, name); await expect(page.getByRole("link", { name: new RegExp(name) })).toBeVisible();
  await page.goto("/app/song/song-010"); await page.getByLabel("Playlist").selectOption({ label: name }); await page.getByRole("button", { name: "Add to playlist" }).click(); await expect(page.getByText(`Added to "${name}".`)).toBeVisible();
  await page.goto("/app/library"); await page.getByRole("link", { name: new RegExp(name) }).click(); await expect(page.getByRole("link", { name: "Tere Hone Se" })).toBeVisible();
  await page.getByRole("button", { name: "Delete playlist" }).click(); await page.getByRole("button", { name: "Yes, delete" }).click();
  await page.goto("/app/library"); await page.getByRole("tab", { name: "Songs" }).click();
  await expect(page.getByRole("link", { name: /Tere Hone Se/ })).toBeVisible(); await expect(page.getByLabel("Language").locator("option", { hasText: "English" })).toHaveCount(0);   // the only English song is unconfirmed: a listener is not offered its language
  await page.getByLabel("Language").selectOption("Hindi"); await page.getByLabel("Genre").selectOption("Indie pop"); await expect(page.getByRole("link", { name: /Pata Hi Na Chala/ })).toBeVisible(); await expect(page.getByRole("link", { name: /Tere Hone Se/ })).toHaveCount(0);
});

for (const theme of ["midnight-cinema", "ivory-gold"]) {
  for (const [name, path] of [["Browse", "/app/"], ["Song", "/app/song/song-010"], ["Library", "/app/library"], ["Songs tab", "/app/library"], ["Plans", "/app/plans"], ["Account", "/app/account"]]) {
    test(`listener ${name} (${theme}): no horizontal scroll, large touch targets, no serious accessibility violations`, async ({ page }, info) => {
      await page.addInitScript((t) => { try { localStorage.setItem("navaan.theme", t); } catch { /* storage blocked */ } }, theme);
      await page.goto(path); if (name === "Songs tab") await page.getByRole("tab", { name: "Songs" }).click();
      await expect(page.getByText("Loading…")).toHaveCount(0, { timeout: 15_000 }); await page.waitForLoadState("networkidle");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      if (info.project.name === "mobile") {
        const small = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>("button, a.btn, select, .tabbar a, a.q, input")].filter((e) => e.offsetParent && !e.closest(".sr") && e.getBoundingClientRect().height < 43.5).map((e) => (e.getAttribute("aria-label") || e.textContent || e.id || e.tagName).trim().slice(0, 30)));
        expect(small, "controls under 44px").toEqual([]);
      }
      const r = await new AxeBuilder({ page }).analyze();
      expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id}: ${v.nodes[0]?.html.slice(0, 120)}`)).toEqual([]);
    });
  }
}
