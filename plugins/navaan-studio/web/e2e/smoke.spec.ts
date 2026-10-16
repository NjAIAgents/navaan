import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const THEMES = ["midnight-cinema", "ivory-gold"];
const PAGES = [["Home", "/app/"], ["Studio", "/app/studio"], ["Songs", "/app/studio/songs"], ["Song", "/app/studio/songs/song-001"], ["Inspiration", "/app/studio/inspiration"], ["Approvals", "/app/studio/approvals"],
  ["Schedule", "/app/studio/schedule"], ["Analytics", "/app/studio/analytics"], ["Settings", "/app/studio/settings"], ["Security", "/app/account/security"], ["Cloud", "/app/studio/cloud"], ["Recommendations", "/app/studio/analytics?tab=recommendations"], ["Interactions", "/app/studio/analytics?tab=interactions"], ["Search", "/app/search?q=tere"], ["Library", "/app/library"], ["Plans", "/app/plans"], ["Albums", "/app/albums"], ["Account", "/app/account"]];

async function ready(page: Page) {
  await expect(page.getByText("Loading…")).toHaveCount(0, { timeout: 15_000 });
  await page.waitForLoadState("networkidle");
}

// The Library's New playlist form asks for a name, what it is for, and who can see it.
async function newPlaylist(page: Page, name: string) {
  await page.getByRole("button", { name: /New playlist/ }).click(); await page.getByLabel("Name", { exact: true }).fill(name); await page.getByRole("button", { name: "Create playlist" }).click();
}

test("a song goes from the list to an approved gate", async ({ page }, info) => {
  const slug = info.project.name === "mobile" ? "song-001" : "song-004";   // each project approves its own song
  await page.goto("/app/studio/songs");
  await page.getByRole("link", { name: new RegExp(slug === "song-001" ? "Draft One" : "Draft Two") }).click();
  await expect(page.getByRole("heading", { name: "Lyrics", level: 2 })).toBeVisible();
  await expect(page.locator(".art")).toContainText("Tere hone se");
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Lyrics", level: 2 })).toHaveCount(0);
  await expect(page.getByText(`gate lyrics approved via ui:`)).toBeVisible();   // the history says who
  await page.getByRole("button", { name: "Revoke approval of Lyrics" }).click(); await page.getByRole("button", { name: "Yes, revoke" }).click();   // take it back: the gate opens again
  await expect(page.getByRole("heading", { name: "Lyrics", level: 2 })).toBeVisible(); await expect(page.getByText(/gate lyrics revoked via ui:/)).toBeVisible();
});

test("a song and an inspiration can be started from the lists and open at their first step", async ({ page }, info) => {
  await page.goto("/app/studio/songs"); await page.getByRole("button", { name: "New song" }).click();
  await page.getByLabel("Idea (optional)").fill(`A song made in the ${info.project.name} check`); await page.getByRole("button", { name: "Create" }).click();
  await expect(page).toHaveURL(/\/app\/studio\/songs\/song-\d+/); await expect(page.getByRole("heading", { name: "Steps", level: 2 })).toBeVisible();
  await page.goto("/app/studio/inspiration"); await page.getByRole("button", { name: "New inspiration" }).click();
  await page.getByRole("button", { name: "Create" }).click(); await expect(page.getByText("Write the quote or the idea first.")).toBeVisible();   // an inspiration needs words
  await page.getByLabel("Quote or idea").fill("Maybe you are not behind, maybe you are on your own road"); await page.getByRole("button", { name: "Create" }).click();
  await expect(page).toHaveURL(/\/app\/studio\/inspiration\/insp-\d+/); await expect(page.getByRole("heading", { name: "Steps", level: 2 })).toBeVisible();
});

test("a song's words can be edited, saved, and are still there after a reload (and an unsaved edit is flagged)", async ({ page }, info) => {
  const slug = info.project.name === "mobile" ? "song-001" : "song-004";
  await page.goto(`/app/studio/songs/${slug}`); await ready(page);
  await page.locator("summary", { hasText: "Style" }).click();
  const box = page.getByLabel("Style", { exact: true }); await box.fill(`warm hindi pop, edited in the ${info.project.name} check`);
  await expect(page.getByText("Unsaved changes").first()).toBeVisible();
  await page.getByRole("button", { name: "Save style" }).click(); await expect(page.getByText("Saved", { exact: true })).toBeVisible();
  await page.reload(); await ready(page); await page.locator("summary", { hasText: "Style" }).click();
  await expect(page.getByLabel("Style", { exact: true })).toHaveValue(`warm hindi pop, edited in the ${info.project.name} check`);
  await expect(page.getByText(/style\.txt edited via ui:/)).toBeVisible();   // the history says who
});

test("the front door is the new app, and the classic view is still at /legacy", async ({ page }) => {
  await page.goto("/"); await expect(page).toHaveURL(/\/app\/$/);
  const r = await page.request.get("/legacy"); expect(r.status()).toBe(200); expect(await r.text()).toContain("NAVAAN");
});

test("approvals lists what is waiting, grouped by gate", async ({ page }) => {
  await page.goto("/app/studio/approvals");
  await expect(page.getByRole("heading", { name: "Quote", level: 2 })).toBeVisible();
  await expect(page.getByRole("link", { name: /Review Tired of being strong/ })).toBeVisible();
});

test("the schedule shows missed and blocked publishes", async ({ page }, info) => {
  await page.goto("/app/studio/schedule");
  await expect(page.getByText("Missed", { exact: true }).first()).toBeVisible(); await expect(page.getByText("Blocked", { exact: true }).first()).toBeVisible();
  const cal = page.getByRole("table");
  if (info.project.name === "mobile") await expect(cal).toBeHidden(); else await expect(cal).toBeVisible();   // the calendar collapses to the list on a phone
});

test("a playlist can be made, opened and deleted from the library", async ({ page }, info) => {
  const name = `E2E ${info.project.name}`;
  await page.goto("/app/library");
  await newPlaylist(page, name);
  await page.getByRole("link", { name: new RegExp(name) }).click();
  await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible(); await expect(page.getByText(/This playlist is empty/)).toBeVisible();
  await page.getByRole("button", { name: "Delete playlist" }).click(); await page.getByRole("button", { name: "Yes, delete" }).click();
  await expect(page.getByRole("heading", { name: "Library", level: 1 }).first()).toBeVisible(); await expect(page.getByRole("link", { name: new RegExp(name) })).toHaveCount(0);
});

test("an album can be made, filled, put in order, and keeps its order after a reload", async ({ page }, info) => {
  const name = `Album ${info.project.name}`;
  await page.goto("/app/albums"); await page.getByLabel("New album title").fill(name); await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("link", { name: new RegExp(name) }).click(); await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible();
  for (const title of ["Tere Hone Se", "Pata Hi Na Chala"]) { await page.getByLabel("Song to add").selectOption({ label: title }); await page.getByRole("button", { name: "Add song" }).click(); await expect(page.getByRole("link", { name: new RegExp(title) })).toBeVisible(); }
  const order = () => page.locator("ol.steps li .tx").allInnerTexts();
  expect((await order()).map((t) => t.replace(/^\d+\.\s*/, ""))).toEqual(["Tere Hone Se", "Pata Hi Na Chala"]);
  await page.getByRole("button", { name: "Move Tere Hone Se down" }).click(); await expect.poll(async () => (await order())[0]).toContain("Pata Hi Na Chala");
  await page.reload(); await expect.poll(async () => (await order())[0]).toContain("Pata Hi Na Chala");   // the order persisted
  await page.getByLabel("Status").selectOption("published"); await page.getByRole("button", { name: "Save details" }).click(); await expect(page.getByText("Saved.")).toBeVisible();
  await page.getByRole("button", { name: "Delete album" }).click(); await page.getByRole("button", { name: "Yes, delete" }).click(); await expect(page.getByRole("heading", { name: "Albums", level: 1 }).first()).toBeVisible();
});

test("plans compare Free and Premium and say Premium cannot be bought yet", async ({ page }) => {
  await page.goto("/app/plans");
  await expect(page.getByRole("columnheader", { name: /Free/ })).toBeVisible(); await expect(page.getByRole("columnheader", { name: /Premium/ })).toBeVisible();
  await expect(page.getByText(/Premium cannot be bought yet/)).toBeVisible();
});

test("search finds nothing in an empty catalog and says so", async ({ page }) => {
  await page.goto("/app/studio/songs");
  await page.getByRole("searchbox", { name: "Search songs, albums, lyrics" }).or(page.getByRole("link", { name: "Search" })).first().click();
  await page.goto("/app/search?q=zzzzqq"); await expect(page.getByText(/Nothing found/)).toBeVisible();
});

for (const theme of THEMES) {
  for (const [name, path] of PAGES) {
    test(`${name} (${theme}): no horizontal scroll, large touch targets, no serious accessibility violations`, async ({ page }, info) => {
      await page.addInitScript((t) => { try { localStorage.setItem("navaan.theme", t); } catch { /* storage blocked */ } }, theme);
      await page.goto(path); await ready(page);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      if (info.project.name === "mobile") {
        const small = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>("button, a.btn, select, .tabbar a, a.q, input")].filter((e) => e.offsetParent && !e.closest(".sr") && e.getBoundingClientRect().height < 43.5).map((e) => (e.textContent || e.id || e.tagName).trim().slice(0, 30)));
        expect(small, "controls under 44px").toEqual([]);
      }
      const r = await new AxeBuilder({ page }).analyze();   // real layout, so colour contrast is checked too
      expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id}: ${v.nodes[0]?.html.slice(0, 120)}`)).toEqual([]);
    });
  }
}
