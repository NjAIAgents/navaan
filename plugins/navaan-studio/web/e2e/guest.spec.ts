import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { GUEST_PORT } from "./playwright.config";

// The free public site, seen by someone who is not signed in. Songs seeded: song-010 and song-011 confirmed, song-012 published but not confirmed.
test.use({ baseURL: `http://127.0.0.1:${GUEST_PORT}` });

test("the front door is the app, with no sign in, and only licensed songs", async ({ page }) => {
  await page.goto("/"); await expect(page).toHaveURL(/\/app\/$/);
  await expect(page.getByRole("heading", { name: "Browse", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: /Tere Hone Se/ }).first()).toBeVisible(); await expect(page.getByRole("link", { name: /Pata Hi Na Chala/ }).first()).toBeVisible();
  await expect(page.getByText(/passkey|Sign in with/i)).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Library" }).first()).toBeVisible(); await expect(page.getByRole("link", { name: "Studio" })).toHaveCount(0);   // the Library is open to visitors; nothing for the owner here
  await page.goto("/app/song/song-012"); await expect(page.getByRole("heading", { name: "This song is not available" })).toBeVisible();   // published but its licence is not confirmed: not offered
});

test("a visitor plays a whole song with its lyrics, shares it, and is told what an account will give", async ({ page }) => {
  await page.goto("/app/song/song-011"); await expect(page.getByRole("heading", { name: "Pata Hi Na Chala", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Lyrics" }).click();   // the lyrics are folded until asked for
  await page.getByRole("button", { name: "Play" }).first().click();
  await expect(page.getByRole("region", { name: "Now playing", exact: true })).toBeVisible(); await expect(page.getByRole("button", { name: "Mute" })).toBeVisible();   // the slider too on a wide screen; a phone keeps the mute button
  await expect.poll(async () => page.evaluate(() => (document.querySelector("audio") as HTMLAudioElement).currentTime)).toBeGreaterThan(0);   // it really plays
  await expect(page.locator("[aria-current=true]")).toBeVisible();   // and the lyrics follow
  expect(await page.evaluate(() => document.querySelectorAll("audio[controls]").length)).toBe(0);   // no browser player with a download item
  await page.getByRole("button", { name: "Share", exact: true }).click(); await expect(page.getByLabel(/Anyone with this link can listen/)).toHaveValue(/\/app\/song\/song-011$/);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Add to a playlist" }).click(); await expect(page.getByRole("link", { name: "Create account" })).toHaveAttribute("href", "/app/join");
});

test("a visitor makes a clip of a song, plays it, and the page for it leads back to the whole song", async ({ page, request }) => {
  await page.goto("/app/song/song-011");
  await page.getByRole("button", { name: "Share a clip" }).click();   // the clip is made in a sheet the icon at the top opens
  await page.getByLabel("Start at (seconds)").fill("1"); await page.getByLabel("End at (seconds)").fill("16"); await page.getByRole("button", { name: "Make the clip" }).click();
  const video = page.getByLabel(/^Clip of /); await expect(video).toBeVisible({ timeout: 60_000 });
  const src = (await video.getAttribute("src"))!; expect(src).toMatch(/^\/c\/song-011-1-15\.mp4$/);
  const r = await request.get(src, { headers: { Range: "bytes=0-99" } }); expect(r.status()).toBe(206); expect(r.headers()["content-type"]).toBe("video/mp4");   // Safari plays video only with ranges
  await page.goto(src.replace(".mp4", "")); await expect(page.getByRole("link", { name: "Hear the full song" })).toHaveAttribute("href", "/app/song/song-011");
});

test("a visitor reacts to a song and sends feedback, and the owner sees both", async ({ page, request }, info) => {
  const note = `Feedback from the ${info.project.name} check ${Date.now()}`;
  await page.goto("/app/song/song-011"); await expect(page.getByRole("heading", { name: "Pata Hi Na Chala", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "What did you think?" }).click();   // the reactions are in the sheet the icon at the top opens
  await page.getByRole("button", { name: /Love it/ }).click(); await expect(page.getByRole("button", { name: /Love it/ })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Thumbs up", exact: true }).click(); await expect(page.getByRole("button", { name: "Thumbs up", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: /Send feedback/ }).click(); await page.getByLabel("Your message").fill(note); await page.getByRole("button", { name: "Send", exact: true }).click(); await expect(page.getByText(/Thank you/)).toBeVisible();
  const owner = `http://127.0.0.1:${process.env.E2E_PORT ?? "8799"}`;   // the studio side of the same data
  const messages = await (await request.get(`${owner}/api/site/feedback?limit=50`)).json(); expect(messages.map((m: { message: string }) => m.message)).toContain(note);
  const rx = await (await request.get(`${owner}/api/site/reactions`)).json(); const row = rx.find((r: { slug: string }) => r.slug === "song-011"); expect(row.up + row.love).toBeGreaterThan(0);
});

test.describe("the public site opens dark", () => {
  test.use({ colorScheme: "light" });   // even on a device that prefers light
  test("until the visitor chooses, and the choice is kept", async ({ page }) => {
    await page.goto("/app/"); await expect(page.locator("html")).toHaveAttribute("data-theme", "midnight-cinema");
    await page.getByRole("button", { name: /Account menu/ }).first().click(); await page.getByRole("button", { name: /Ivory/ }).click(); await expect(page.locator("html")).toHaveAttribute("data-theme", "ivory-gold");
    await page.reload(); await expect(page.locator("html")).toHaveAttribute("data-theme", "ivory-gold");
  });
});

test("a visitor opens the Library, and Create playlist leads to Create account, which keeps what they like", async ({ page }) => {
  await page.goto("/app/library");
  await expect(page.getByText("Create your first playlist")).toBeVisible();
  await page.getByRole("link", { name: /Create playlist/ }).click();
  await expect(page.getByRole("heading", { name: "Create your account", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Calm" }).click(); await page.getByRole("button", { name: "Create my account" }).click();
  await expect(page.getByText(/Accounts open soon/)).toBeVisible();
});

test("a visitor cannot reach the studio or anything that needs an account", async ({ page }) => {
  for (const path of ["/api/songs", "/api/settings", "/api/playlists", "/api/library", "/api/account"]) expect((await page.request.get(path)).status(), path).toBe(403);
  expect((await page.request.get("/api/catalog/tracks")).status()).toBe(200); expect((await page.request.get("/legacy")).status()).toBe(403);
  await page.goto("/app/studio/settings"); await expect(page.getByText("This page is not available here")).toBeVisible();
});

for (const theme of ["midnight-cinema", "ivory-gold"]) {
  for (const [name, path] of [["Browse", "/app/"], ["Song", "/app/song/song-010"]]) {
    test(`public ${name} (${theme}): no horizontal scroll, large touch targets, no serious accessibility violations`, async ({ page }, info) => {
      await page.addInitScript((t) => { try { localStorage.setItem("navaan-theme", t); } catch { /* storage may be blocked */ } }, theme);
      await page.goto(path); await expect(page.getByText("Loading…")).toHaveCount(0, { timeout: 15_000 }); await page.waitForLoadState("networkidle");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      if (info.project.name === "mobile") {
        const small = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>("button, a.btn, select, .tabbar a, a.q, input")].filter((e) => e.offsetParent !== null && e.getBoundingClientRect().height > 0 && e.getBoundingClientRect().height < 43.5 && !e.classList.contains("sr")).map((e) => e.id || e.textContent?.trim().slice(0, 20) || e.tagName));
        expect(small, "controls under 44px").toEqual([]);
      }
      const r = await new AxeBuilder({ page }).analyze();
      expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id}: ${v.nodes[0]?.html.slice(0, 120)}`)).toEqual([]);
    });
  }
}
