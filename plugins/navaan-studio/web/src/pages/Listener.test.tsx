import { readFileSync } from "node:fs";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { LISTENER, OWNER } from "../components/Shell.test";
import { activeIndex } from "../lib/lyrics";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json", "X-Request-Id": "req-5" } });
function route(me: unknown, routes: Record<string, (init?: RequestInit) => unknown>) {
  const f = vi.fn((u: string, init?: RequestInit) => {
    if (u.startsWith("/api/me")) return Promise.resolve(json(me));
    const k = Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => u === r || u.startsWith(r + "?") || u.startsWith(r)); const v = k ? routes[k](init) : [];
    return Promise.resolve(v instanceof Response ? v : json(v));
  });
  vi.stubGlobal("fetch", f); return f;
}
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
const posts = (f: ReturnType<typeof route>, path: string) => f.mock.calls.filter(([u]) => u === path).map(([, i]) => JSON.parse(String(i?.body)));
let paused = true, now = 0;
beforeEach(() => {
  paused = true; now = 0;
  Object.defineProperty(HTMLMediaElement.prototype, "paused", { configurable: true, get: () => paused });
  Object.defineProperty(HTMLMediaElement.prototype, "currentTime", { configurable: true, get: () => now, set: (v: number) => { now = v; } });
  Object.defineProperty(HTMLMediaElement.prototype, "duration", { configurable: true, get: () => 200 });
  HTMLMediaElement.prototype.play = vi.fn(function (this: HTMLMediaElement) { paused = false; this.dispatchEvent(new Event("play")); return Promise.resolve(); });
  HTMLMediaElement.prototype.pause = vi.fn(function (this: HTMLMediaElement) { paused = true; this.dispatchEvent(new Event("pause")); });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); document.body.classList.remove("lock"); });

const track = (o: object = {}) => ({ slug: "song-001", title: "Tere Hone Se", language: "Hindi", genre: "Romantic", albums: [{ slug: "first-light", title: "First Light" }], licence: "confirmed", art: { colour: "#336699" }, lyrics: "line one\nline two\nline three", timed: true, timed_lines: [[2, "line one"], [8, "line two"], [14, "line three"]], ...o });

describe("lyrics timing", () => {
  it("the current line is the last one that has started", () => {
    const l: [number, string][] = [[2, "a"], [8, "b"], [14, "c"]];
    expect([0, 1.9, 2, 7.99, 8, 100].map((t) => activeIndex(l, t))).toEqual([-1, -1, 0, 0, 1, 2]); expect(activeIndex([], 5)).toBe(-1);
  });
});

describe("a song for a listener", () => {
  const pageRoutes = { "/api/catalog/track/song-001": () => track(), "/api/play": () => ({ url: "https://bucket.example/a.mp3" }), "/api/library": () => ({ tracks: [], albums: [], following: false }), "/api/playlists": () => [] };
  it("plays with a round icon-only button, follows the lyrics as the song plays, and opens play mode", async () => {
    route(LISTENER, pageRoutes); at("/song/song-001");
    const play = await screen.findByRole("button", { name: "Play" }); expect(play).not.toHaveTextContent(/\w/);   // icon only, named for assistive technology
    expect(screen.getByRole("heading", { name: "Tere Hone Se", level: 1 })).toBeInTheDocument(); expect(screen.getByText("Hindi · Romantic")).toBeInTheDocument();
    fireEvent.click(play); await waitFor(() => expect(HTMLMediaElement.prototype.play).toHaveBeenCalled());
    const audio = document.querySelector("audio")!;
    now = 9; fireEvent.timeUpdate(audio);
    await waitFor(() => expect(screen.getByText("line two")).toHaveAttribute("aria-current", "true")); expect(screen.getByText("line one")).not.toHaveAttribute("aria-current");
    now = 15; fireEvent.timeUpdate(audio); await waitFor(() => expect(screen.getByText("line three")).toHaveAttribute("aria-current", "true"));
    fireEvent.click(screen.getAllByRole("button", { name: "Open play mode" })[0]);   // one in the hero, one in the Now playing bar
    const dlg = await screen.findByRole("dialog", { name: "Play mode" }); expect(document.body.classList.contains("lock")).toBe(true);
    expect(within(dlg).getByRole("button", { name: "Pause" })).toBeInTheDocument(); expect(within(dlg).getByText("line three")).toHaveAttribute("aria-current", "true");
    fireEvent.change(within(dlg).getByLabelText("Seek"), { target: { value: "50" } }); expect(now).toBe(50);
    fireEvent.click(within(dlg).getByRole("button", { name: "Pause" })); await waitFor(() => expect(within(dlg).getByRole("button", { name: "Play" })).toBeInTheDocument());
    fireEvent.keyDown(document, { key: "Escape" }); await waitFor(() => expect(screen.queryByRole("dialog", { name: "Play mode" })).toBeNull()); expect(document.body.classList.contains("lock")).toBe(false);
  });
  it("moves between songs with Back and Next, and starts the next one when a song ends", async () => {
    const rows = ["song-001", "song-002", "song-003"].map((slug, i) => ({ slug, title: `Song ${i + 1}`, language: "Hindi", genre: "", albums: [], licence: "confirmed", art: null }));
    const f = route(LISTENER, { ...pageRoutes, "/api/catalog/tracks": () => rows }); at("/song/song-001");
    fireEvent.click(await screen.findByRole("button", { name: "Play" })); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/play?slug=song-001")).toBe(true));
    const bar = await screen.findByRole("region", { name: "Now playing" }); const btn = (n: string) => within(bar).getByRole("button", { name: n });
    await waitFor(() => expect(btn("Next")).toBeEnabled()); expect(btn("Back")).toBeInTheDocument();   // the catalogue fills the queue after the first play
    fireEvent.click(btn("Next")); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/play?slug=song-002")).toBe(true)); expect(within(bar).getByText("Song 2")).toBeInTheDocument();
    now = 10; fireEvent.click(btn("Back")); expect(now).toBe(0);   // well into a song, Back restarts it
    fireEvent.click(btn("Back")); await waitFor(() => expect(f.mock.calls.filter(([u]) => u === "/api/play?slug=song-001").length).toBe(2));   // at the start it goes to the one before
    fireEvent.click(btn("Next")); await waitFor(() => expect(within(bar).getByText("Song 2")).toBeInTheDocument());
    fireEvent.ended(document.querySelector("audio")!); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/play?slug=song-003")).toBe(true)); expect(btn("Next")).toBeDisabled();   // the last song has nothing after it
  });
  it("the Play button is a circle, not an oval", async () => {
    route(LISTENER, pageRoutes); at("/song/song-001"); const play = await screen.findByRole("button", { name: "Play" });
    expect(play.className).toMatch(/\bsq\b/); expect(play.className).toMatch(/\bround\b/);   // base.css: .btn.sq.round is 56 by 56 with a 50% radius, which beats .btn.sq's 44px width
    expect(readFileSync("src/styles/base.css", "utf8")).toMatch(/\.btn\.sq\.round \{[^}]*width: 56px; height: 56px/);
  });
  it("follows the lyrics approximately when nobody measured the timing", async () => {
    route(LISTENER, { ...pageRoutes, "/api/catalog/track/song-001": () => track({ timed: false, timed_lines: null, lyrics: "[Verse 1]\nline one\nline two\nline three\nline four" }) }); at("/song/song-001");
    fireEvent.click(await screen.findByRole("button", { name: "Play" })); const audio = document.querySelector("audio")!;
    now = 1; fireEvent.timeUpdate(audio); await waitFor(() => expect(screen.getByText("Lines follow the song approximately.")).toBeInTheDocument());   // the song is 200 s long in this test
    expect(screen.queryByText("[Verse 1]")).toBeNull(); now = 190; fireEvent.timeUpdate(audio); await waitFor(() => expect(screen.getByText("line four")).toHaveAttribute("aria-current", "true"));
    now = 60; fireEvent.timeUpdate(audio); await waitFor(() => expect(screen.getByText("line two")).toHaveAttribute("aria-current", "true"));
  });
  it("shows plain lyrics when there is no timing, and says so when a song is not available", async () => {
    route(LISTENER, { ...pageRoutes, "/api/catalog/track/song-001": () => track({ timed: false, timed_lines: null }) }); at("/song/song-001");
    expect(await screen.findByLabelText("Lyrics", { selector: "p" })).toHaveTextContent("line one"); expect(document.querySelector("[aria-current]")).toBeNull();
    cleanup(); route(LISTENER, { "/api/catalog/track/ghost": () => json({ error: "no such song" }, 404) }); at("/song/ghost");
    expect(await screen.findByRole("alert")).toHaveTextContent("no such song");
  });
  it("can be saved, added to a playlist and shared by a listener", async () => {
    const f = route(LISTENER, { ...pageRoutes, "/api/library/save": () => ({ ok: true }), "/api/playlists": () => [{ id: "p1", name: "Evening", description: "", visibility: "private", tracks: 0, updated_at: "" }], "/api/share": () => ({ token: "tok", url: "https://navaan.example/s/tok" }) }); at("/song/song-001");
    fireEvent.click(await screen.findByRole("button", { name: "Save song" })); await screen.findByRole("button", { name: "Saved" }); expect(posts(f, "/api/library/save")).toEqual([{ kind: "track", slug: "song-001", on: true }]);
    fireEvent.click(await screen.findByRole("button", { name: "Share" })); expect(await screen.findByLabelText(/hears a 30 second preview/)).toHaveValue("https://navaan.example/s/tok");
    const on = screen.getByRole("list", { name: "Share on" });   // the platforms, each a link that opens that service's own share page
    for (const [name, host] of [["WhatsApp", "wa.me"], ["X", "twitter.com"], ["Facebook", "facebook.com"], ["Threads", "threads.net"], ["Telegram", "t.me"], ["LinkedIn", "linkedin.com"]]) expect(within(on).getByRole("link", { name: new RegExp(`^${name}`) }).getAttribute("href")).toContain(host);
    expect(within(on).getByRole("link", { name: /^WhatsApp/ }).getAttribute("href")).toContain(encodeURIComponent("https://navaan.example/s/tok")); expect(within(on).getByRole("button", { name: "Copy link" })).toBeInTheDocument();
  });
});

describe("albums and play buttons on lists", () => {
  const album = { id: "a1", slug: "first-light", title: "First Light", kind: "album", status: "published", release_date: "2026-10-01", description: "Songs of the dawn", tracks: [
    { slug: "song-001", title: "Tere Hone Se", position: 1, status: "published", licence: "confirmed", art: { colour: "#336699" } }, { slug: "song-002", title: "Pata Hi Na Chala", position: 2, status: "published", licence: "confirmed", art: null }] };
  it("Browse lists published albums and an album page plays from the top, then on to the next song", async () => {
    const f = route(LISTENER, { "/api/catalog/albums": () => [album], "/api/catalog/album/first-light": () => album, "/api/catalog/tracks": () => [], "/api/play": () => ({ url: "https://bucket.example/a.mp3" }) });
    at("/"); const tile = await screen.findByRole("link", { name: /First Light/ }); expect(tile).toHaveAttribute("href", "/album/first-light"); cleanup();
    at("/album/first-light"); expect(await screen.findByRole("heading", { name: "First Light", level: 1 })).toBeInTheDocument(); expect(screen.getByText("Songs of the dawn")).toBeInTheDocument();
    const before = f.mock.calls.filter(([u]) => u === "/api/catalog/tracks").length;
    fireEvent.click(screen.getByRole("button", { name: "Play First Light" })); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/play?slug=song-001")).toBe(true));
    const bar = await screen.findByRole("region", { name: "Now playing" }); await waitFor(() => expect(within(bar).getByRole("button", { name: "Next" })).toBeEnabled());   // the queue is the album
    fireEvent.click(within(bar).getByRole("button", { name: "Next" })); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/play?slug=song-002")).toBe(true));
    expect(f.mock.calls.filter(([u]) => u === "/api/catalog/tracks").length).toBe(before);   // it did not fall back to the whole catalogue
  });
  it("says so when an album is not available to this person", async () => {
    route(LISTENER, { "/api/catalog/album/ghost": () => json({ error: "no such album" }, 404) }); at("/album/ghost"); expect(await screen.findByRole("alert")).toHaveTextContent("no such album");
  });
  it("a playlist plays from its first song", async () => {
    const f = route(OWNER, { "/api/playlists/p1": () => ({ id: "p1", name: "Evening", description: "", visibility: "private", mine: true, tracks: [{ slug: "song-001", title: "Tere Hone Se", position: "a" }, { slug: "song-002", title: "Pata Hi Na Chala", position: "b" }] }), "/api/play": () => ({ url: "https://bucket.example/a.mp3" }) });
    at("/library/playlists/p1"); fireEvent.click(await screen.findByRole("button", { name: "Play Evening" })); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/play?slug=song-001")).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "Play Pata Hi Na Chala" })); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/play?slug=song-002")).toBe(true));
  });
});

describe("playlists: adding songs, and paging", () => {
  const row = (n: number) => ({ slug: `song-${String(n).padStart(3, "0")}`, title: `Song ${n}`, language: "Hindi", genre: "", albums: [], licence: "confirmed", art: null });
  it("a song list pages in 24 at a time, by itself or by the button, and says nothing more when it is done", async () => {
    const f = route(OWNER, { "/api/catalog/filters": () => ({ albums: [], languages: [], genres: [] }), "/api/catalog/tracks?limit=24&offset=0": () => Array.from({ length: 24 }, (_, i) => row(i + 1)), "/api/catalog/tracks?limit=24&offset=24": () => [row(25), row(26)], "/api/playlists": () => [], "/api/library": () => ({ tracks: [], albums: [], following: false }) });
    at("/library"); fireEvent.click(await screen.findByRole("tab", { name: "Songs" })); await screen.findByRole("link", { name: /Song 1(?!\d)/ });
    expect(screen.queryByRole("link", { name: /Song 25/ })).toBeNull(); expect(f.mock.calls.some(([u]) => String(u).includes("offset=24"))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Show more songs" })); expect(await screen.findByRole("link", { name: /Song 26/ })).toBeInTheDocument(); expect(screen.queryByRole("button", { name: /Show more/ })).toBeNull();   // a short page was the last
  });
  it("adds a song to a playlist from a song list, or to a new one made on the spot with its details", async () => {
    const f = route(OWNER, { "/api/catalog/filters": () => ({ albums: [], languages: [], genres: [] }), "/api/catalog/tracks": () => [row(1)], "/api/playlists/create": () => ({ id: "33333333-3333-3333-3333-333333333333" }), "/api/playlists/add": () => ({ ok: true }), "/api/playlists": () => [{ id: "11111111-1111-1111-1111-111111111111", name: "Evening", description: "", visibility: "private", tracks: 2, updated_at: "" }], "/api/library": () => ({ tracks: [], albums: [], following: false }) });
    at("/library"); fireEvent.click(await screen.findByRole("tab", { name: "Songs" })); fireEvent.click(await screen.findByRole("button", { name: "Add Song 1 to a playlist" }));
    const dlg = await screen.findByRole("dialog"); fireEvent.click(await within(dlg).findByRole("button", { name: "Add to Evening" }));
    await waitFor(() => expect(posts(f, "/api/playlists/add")).toEqual([{ id: "11111111-1111-1111-1111-111111111111", slug: "song-001" }])); expect(await within(dlg).findByText('Added to "Evening".')).toBeInTheDocument();
    fireEvent.click(within(dlg).getByRole("button", { name: /New playlist/ })); fireEvent.change(within(dlg).getByLabelText("Name"), { target: { value: "Rain" } }); fireEvent.change(within(dlg).getByLabelText(/What is it for/), { target: { value: "Monsoon" } }); fireEvent.click(within(dlg).getByRole("button", { name: "Create playlist" }));
    await waitFor(() => expect(posts(f, "/api/playlists/create")).toEqual([{ name: "Rain", description: "Monsoon", visibility: "private" }])); await waitFor(() => expect(posts(f, "/api/playlists/add")[1]).toEqual({ id: "33333333-3333-3333-3333-333333333333", slug: "song-001" }));   // and the song goes into it
  });
  it("the playlist page has Add songs with search, marks what is in already, and saves a description", async () => {
    const detail = { id: "p1", name: "Evening", description: "", visibility: "private", mine: true, tracks: [{ slug: "song-001", title: "Song 1", position: "a" }] };
    const f = route(OWNER, { "/api/playlists/p1": () => detail, "/api/playlists/add": () => ({ ok: true }), "/api/playlists/update": () => ({ ok: true }), "/api/catalog/tracks": () => [row(1), row(2)], "/api/search": () => ({ hits: [{ kind: "track", id: "x", slug: "song-002", title: "Song 2", title_roman: "", score: 1 }] }) });
    at("/library/playlists/p1"); fireEvent.change(await screen.findByLabelText("What it is for"), { target: { value: "Slow songs" } }); fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(posts(f, "/api/playlists/update")).toEqual([{ id: "p1", description: "Slow songs" }]));
    fireEvent.click(screen.getByRole("button", { name: /Add songs/ })); const list = await screen.findByRole("list", { name: "Songs to add" });
    expect(within(list).getByText("In the playlist")).toBeInTheDocument(); fireEvent.click(within(list).getByRole("button", { name: "Add Song 2" })); await waitFor(() => expect(posts(f, "/api/playlists/add")).toEqual([{ id: "p1", slug: "song-002" }]));
    fireEvent.change(screen.getByLabelText("Search songs"), { target: { value: "song two" } }); await waitFor(() => expect(f.mock.calls.some(([u]) => String(u).startsWith("/api/search?q=song%20two&kind=track"))).toBe(true));
  });
});

describe("shuffle", () => {
  const rows = ["song-001", "song-002", "song-003", "song-004"].map((slug, i) => ({ slug, title: `Song ${i + 1}`, language: "Hindi", genre: "", albums: [], licence: "confirmed", art: null }));
  const album = { id: "a1", slug: "first-light", title: "First Light", kind: "album", status: "published", release_date: null, description: "", tracks: rows.map((r, i) => ({ slug: r.slug, title: r.title, position: i + 1, status: "published", licence: "confirmed", art: null })) };
  const plays = (f: ReturnType<typeof route>) => f.mock.calls.map(([u]) => String(u)).filter((u) => u.startsWith("/api/play?slug=")).map((u) => u.split("=")[1]);
  it("plays every song once in a random order before any repeats, remembers it is on, and Back returns to the song before", async () => {
    try { localStorage.clear(); } catch { /* storage may be blocked */ }
    const f = route(LISTENER, { ...{ "/api/catalog/track/song-001": () => track(), "/api/play": () => ({ url: "https://bucket.example/a.mp3" }), "/api/library": () => ({ tracks: [], albums: [], following: false }), "/api/playlists": () => [] }, "/api/catalog/tracks": () => rows });
    const rnd = vi.spyOn(Math, "random").mockReturnValue(0.99);   // always the last of what is left
    at("/song/song-001"); fireEvent.click(await screen.findByRole("button", { name: "Play" })); const bar = await screen.findByRole("region", { name: "Now playing" }); await waitFor(() => expect(within(bar).getByRole("button", { name: "Next" })).toBeEnabled());
    const shuffle = within(bar).getByRole("button", { name: "Shuffle" }); fireEvent.click(shuffle); await waitFor(() => expect(within(bar).getByRole("button", { name: "Shuffle" })).toHaveAttribute("aria-pressed", "true")); expect(localStorage.getItem("navaan-shuffle")).toBe("1");
    for (let i = 0; i < 3; i++) { const n = plays(f).length; fireEvent.click(within(bar).getByRole("button", { name: "Next" })); await waitFor(() => expect(plays(f).length).toBe(n + 1)); }
    expect(new Set(plays(f)).size).toBe(4);   // song-001 and three others: no repeat yet
    const n = plays(f).length; fireEvent.click(within(bar).getByRole("button", { name: "Next" })); await waitFor(() => expect(plays(f).length).toBe(n + 1)); expect(plays(f)[n]).not.toBe(plays(f)[n - 1]);   // a new round, not the song that just played
    const before = plays(f)[n - 1]; fireEvent.click(within(bar).getByRole("button", { name: "Back" })); await waitFor(() => expect(plays(f).length).toBe(n + 2)); expect(plays(f)[n + 1]).toBe(before);   // Back goes where you were
    rnd.mockRestore();
  });
  it("Shuffle on an album turns it on and starts a random song of that album, not the one playing", async () => {
    try { localStorage.clear(); } catch { /* storage may be blocked */ }
    const f = route(LISTENER, { "/api/catalog/album/first-light": () => album, "/api/play": () => ({ url: "https://bucket.example/a.mp3" }), "/api/catalog/tracks": () => rows });
    vi.spyOn(Math, "random").mockReturnValue(0.5); at("/album/first-light"); fireEvent.click(await screen.findByRole("button", { name: "Shuffle First Light" }));
    await waitFor(() => expect(plays(f).length).toBe(1)); expect(["song-001", "song-002", "song-003", "song-004"]).toContain(plays(f)[0]); expect(localStorage.getItem("navaan-shuffle")).toBe("1");
    const bar = await screen.findByRole("region", { name: "Now playing" }); expect(within(bar).getByRole("button", { name: "Shuffle" })).toHaveAttribute("aria-pressed", "true");
    vi.restoreAllMocks();
  });
});

describe("Library filters", () => {
  it("shows the answer for the latest choice even when an earlier one answers later", async () => {
    const row = (slug: string, title: string, genre: string) => ({ slug, title, language: "Hindi", genre, albums: [], licence: "confirmed", art: null });
    let releaseSlow: (r: Response) => void = () => undefined;
    const f = vi.fn((u: string) => {
      if (u.startsWith("/api/me")) return Promise.resolve(json(OWNER));
      if (u.startsWith("/api/catalog/filters")) return Promise.resolve(json({ albums: [], languages: ["Hindi"], genres: ["Indie pop"] }));
      if (u === "/api/catalog/tracks?language=Hindi&limit=24&offset=0") return new Promise<Response>((res) => { releaseSlow = res; });   // the first choice answers last
      if (u === "/api/catalog/tracks?language=Hindi&genre=Indie+pop&limit=24&offset=0") return Promise.resolve(json([row("song-002", "Pata Hi Na Chala", "Indie pop")]));
      if (u.startsWith("/api/library")) return Promise.resolve(json({ tracks: [], albums: [], following: false }));
      if (u.startsWith("/api/catalog/tracks")) return Promise.resolve(json([row("song-001", "Tere Hone Se", "Romantic"), row("song-002", "Pata Hi Na Chala", "Indie pop")]));
      return Promise.resolve(json([]));
    });
    vi.stubGlobal("fetch", f); at("/library"); fireEvent.click(await screen.findByRole("tab", { name: "Songs" }));
    await screen.findByRole("link", { name: /Tere Hone Se/ });
    fireEvent.change(screen.getByLabelText("Language"), { target: { value: "Hindi" } }); fireEvent.change(screen.getByLabelText("Genre"), { target: { value: "Indie pop" } });
    expect(await screen.findByRole("link", { name: /Pata Hi Na Chala/ })).toBeInTheDocument();
    releaseSlow(json([row("song-001", "Tere Hone Se", "Romantic"), row("song-002", "Pata Hi Na Chala", "Indie pop")]));   // now the stale answer arrives
    await new Promise((r) => setTimeout(r, 50)); expect(screen.queryByRole("link", { name: /Tere Hone Se/ })).toBeNull(); expect(screen.getByRole("link", { name: /Pata Hi Na Chala/ })).toBeInTheDocument();
  });
});

describe("Library songs", () => {
  it("filters by album, language and genre through the server and links to the song", async () => {
    const f = route(OWNER, { "/api/catalog/filters": () => ({ albums: [{ slug: "first-light", title: "First Light" }], languages: ["English", "Hindi"], genres: ["Indie"] }), "/api/catalog/tracks": () => [{ slug: "song-001", title: "Tere Hone Se", language: "Hindi", genre: "Indie", albums: [{ slug: "first-light", title: "First Light" }], licence: "unconfirmed", art: null }], "/api/playlists": () => [], "/api/library": () => ({ tracks: [], albums: [], following: false }) });
    at("/library"); fireEvent.click(await screen.findByRole("tab", { name: "Songs" }));
    const link = await screen.findByRole("link", { name: /Tere Hone Se/ }); expect(link).toHaveAttribute("href", "/song/song-001"); expect(link).toHaveTextContent("First Light"); expect(link).toHaveTextContent("Licence unconfirmed");   // the owner sees the licence
    fireEvent.change(screen.getByLabelText("Language"), { target: { value: "Hindi" } }); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/catalog/tracks?language=Hindi&limit=24&offset=0")).toBe(true));
    fireEvent.change(screen.getByLabelText("Genre"), { target: { value: "Indie" } }); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/catalog/tracks?language=Hindi&genre=Indie&limit=24&offset=0")).toBe(true));
    fireEvent.change(screen.getByLabelText("Album"), { target: { value: "first-light" } }); await waitFor(() => expect(f.mock.calls.some(([u]) => String(u).includes("album=first-light"))).toBe(true));
  });
});

describe("Albums", () => {
  const album = (o: object = {}) => ({ id: "a1", slug: "first-light", title: "First Light", kind: "album", status: "draft", release_date: null, description: "", tracks: [{ slug: "song-001", title: "One", position: 1, status: "published", licence: "confirmed", art: { colour: "#112233" } }, { slug: "song-002", title: "Two", position: 2, status: "published", licence: "confirmed", art: null }], ...o });
  const tracks = [{ slug: "song-001", title: "One" }, { slug: "song-002", title: "Two" }, { slug: "song-003", title: "Three" }].map((t) => ({ ...t, language: "", genre: "", albums: [], licence: "confirmed", art: null }));
  it("creates an album and lists it with its kind and count", async () => {
    let rows: unknown[] = [album()];
    const f = route(OWNER, { "/api/albums/save": () => { rows = [...rows, album({ id: "a2", slug: "road", title: "Road", kind: "ep", tracks: [] })]; return { slug: "road" }; }, "/api/albums": () => rows });
    at("/albums"); expect(await screen.findByRole("link", { name: /First Light/ })).toHaveTextContent("2 songs");
    fireEvent.change(screen.getByLabelText("New album title"), { target: { value: "Road" } }); fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "ep" } }); fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("link", { name: /Road/ })).toHaveTextContent("ep"); expect(posts(f, "/api/albums/save")).toEqual([{ title: "Road", kind: "ep" }]);
  });
  it("reorders, adds and removes songs, saves details, and shows why an album cannot be published", async () => {
    const f = route(OWNER, { "/api/albums/save": () => json({ error: "every song in a published album must be published; not yet: song-002" }, 400), "/api/albums/reorder": () => ({ tracks: [] }), "/api/albums/delete": () => ({ deleted: true }), "/api/albums": () => [album()], "/api/catalog/tracks": () => tracks });
    at("/albums/first-light"); await screen.findByRole("heading", { name: "First Light", level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Move One down" })); await waitFor(() => expect(posts(f, "/api/albums/reorder")).toHaveLength(1)); expect(posts(f, "/api/albums/reorder")[0]).toEqual({ album: "first-light", tracks: ["song-002", "song-001"] });
    fireEvent.click(screen.getByRole("button", { name: "Add song" })); await waitFor(() => expect(posts(f, "/api/albums/reorder")).toHaveLength(2)); expect(posts(f, "/api/albums/reorder")[1].tracks).toEqual(["song-001", "song-002", "song-003"]);
    fireEvent.click(screen.getByRole("button", { name: "Remove Two" })); await waitFor(() => expect(posts(f, "/api/albums/reorder")).toHaveLength(3)); expect(posts(f, "/api/albums/reorder")[2].tracks).toEqual(["song-001"]);
    expect(screen.getByRole("button", { name: "Move One up" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "published" } }); fireEvent.click(screen.getByRole("button", { name: "Save details" }));
    expect(await screen.findByText(/every song in a published album must be published/)).toBeInTheDocument(); expect(posts(f, "/api/albums/save")[0]).toMatchObject({ slug: "first-light", status: "published", release_date: null });
    fireEvent.click(screen.getByRole("button", { name: "Delete album" })); expect(posts(f, "/api/albums/delete")).toHaveLength(0); fireEvent.click(screen.getByRole("button", { name: "Yes, delete" })); await waitFor(() => expect(posts(f, "/api/albums/delete")).toHaveLength(1));
  });
});

describe("a playlist that is not yours", () => {
  it("opens read only", async () => {
    route(LISTENER, { "/api/playlists/11111111-1111-1111-1111-111111111111": () => ({ id: "11111111-1111-1111-1111-111111111111", name: "Evening", description: "", visibility: "unlisted", mine: false, tracks: [{ slug: "song-001", title: "One", position: "a" }] }) });
    at("/library/playlists/11111111-1111-1111-1111-111111111111");
    expect(await screen.findByText(/Shared with you/)).toBeInTheDocument(); expect(screen.getByRole("link", { name: "One" })).toHaveAttribute("href", "/song/song-001");
    for (const n of [/Rename/, /Delete playlist/, /Move One/, /Remove One/]) expect(screen.queryByRole("button", { name: n })).toBeNull(); expect(screen.queryByLabelText("Playlist name")).toBeNull();
  });
});

describe("Account", () => {
  it("offers the export and deletes only after the phrase is typed", async () => {
    const f = route(LISTENER, { "/api/account/delete": () => json({ error: "the owner account cannot be deleted here" }, 403) }); at("/account");
    expect(await screen.findByRole("link", { name: "Download my data" })).toHaveAttribute("href", "/api/account/export"); expect(screen.getByRole("link", { name: "privacy page" })).toHaveAttribute("href", "/privacy");
    const del = screen.getByRole("button", { name: "Delete my account" }); expect(del).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Type "delete my account"/), { target: { value: "delete my account" } }); expect(del).toBeEnabled();
    fireEvent.click(del); expect(await screen.findByRole("alert")).toHaveTextContent("owner account cannot be deleted"); expect(posts(f, "/api/account/delete")).toEqual([{ confirm: "delete my account" }]);
  });
});

describe("accessibility", () => {
  it("has no serious violations on Browse, a song, play mode, Albums, an album and Account", async () => {
    const routes = { "/api/catalog/tracks": () => [{ slug: "song-001", title: "Tere Hone Se", language: "Hindi", genre: "Romantic", albums: [], licence: "confirmed", art: null }], "/api/catalog/track/song-001": () => track(), "/api/library": () => ({ tracks: [], albums: [], following: false }), "/api/playlists": () => [], "/api/play": () => ({ url: "https://bucket.example/a.mp3" }),
      "/api/albums": () => [{ id: "a1", slug: "first-light", title: "First Light", kind: "album", status: "draft", release_date: null, description: "", tracks: [{ slug: "song-001", title: "One", position: 1, status: "published", licence: "confirmed", art: null }] }] };
    for (const [me, path, play] of [[LISTENER, "/", false], [LISTENER, "/song/song-001", false], [LISTENER, "/song/song-001", true], [OWNER, "/albums", false], [OWNER, "/albums/first-light", false], [LISTENER, "/account", false]] as const) {
      cleanup(); route(me, routes); at(path); await screen.findAllByRole("heading", { level: 1 }); await waitFor(() => expect(screen.queryByText("Loading…")).toBeNull()); await new Promise((r) => setTimeout(r, 30));
      if (play) { fireEvent.click(await screen.findByRole("button", { name: "Play" })); fireEvent.click((await screen.findAllByRole("button", { name: "Open play mode" }))[0]); await screen.findByRole("dialog", { name: "Play mode" }); }
      const r = await axe.run(document.body, { rules: { "color-contrast": { enabled: false } } });
      expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${path}${play ? " (play mode)" : ""} ${v.id}: ${v.nodes[0]?.html.slice(0, 140)}`)).toEqual([]);
    }
  });
});
