import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
const GUEST = { user: "", roles: ["guest"], permissions: [], guest: true, studio_url: "https://studio.navaan.online" };
const OWNER_PUBLIC = { user: "navjyot", roles: ["listener"], permissions: ["library.view", "playlists.write"], studio_url: "https://studio.navaan.online" };
const OWNER_STUDIO = { user: "navjyot", roles: ["owner"], permissions: ["studio.access", "library.view", "studio.settings"], public_url: "https://navaan.online" };
const TRACK = { slug: "song-001", title: "Tere Hone Se", language: "Hindi", genre: "Indie pop", albums: [], licence: "confirmed", art: null, lyrics: "line one\nline two", timed: false, timed_lines: null };
function stub(me: unknown) {
  const f = vi.fn((u: string, _i?: RequestInit) => Promise.resolve(
    u.startsWith("/api/me") ? json(me) : u.startsWith("/api/catalog/tracks") ? json([TRACK]) : u.startsWith("/api/catalog/track/") ? json(TRACK) : u.startsWith("/api/catalog/albums") ? json([]) : u.startsWith("/api/play") ? json({ url: "https://bucket.example/a.mp3" }) : json([])));
  vi.stubGlobal("fetch", f); return f;
}
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
let paused = true;
beforeEach(() => {
  paused = true; try { localStorage.clear(); localStorage.setItem("navaan.song-lyrics", "1"); } catch { /* storage may be blocked */ }   // these checks read the lyrics: open them as a returning listener would have
  Object.defineProperty(HTMLMediaElement.prototype, "paused", { configurable: true, get: () => paused });
  HTMLMediaElement.prototype.play = vi.fn(function (this: HTMLMediaElement) { paused = false; this.dispatchEvent(new Event("play")); return Promise.resolve(); });
  HTMLMediaElement.prototype.pause = vi.fn(function (this: HTMLMediaElement) { paused = true; this.dispatchEvent(new Event("pause")); });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const hits = (f: ReturnType<typeof stub>) => f.mock.calls.filter(([u]) => u === "/api/site/hit").map(([, i]) => JSON.parse(String(i?.body)));

describe("visit counts (NAV-33)", () => {
  it("counts a guest's page view of a song, the seconds they listened, and opening the account page", async () => {
    const f = stub(GUEST); at("/song/song-001");
    await waitFor(() => expect(hits(f)).toContainEqual({ kind: "view", slug: "song-001" }));
    fireEvent.click(await screen.findByRole("button", { name: "Play" }));
    const a = document.querySelector("audio")!; let t = 0; Object.defineProperty(a, "currentTime", { configurable: true, get: () => t, set: (v) => { t = v; } });
    await waitFor(() => expect(paused).toBe(false));
    for (const x of [0, 1, 2, 3]) { t = x; fireEvent.timeUpdate(a); }
    t = 120; fireEvent.timeUpdate(a);   // a seek forward is not listening
    window.dispatchEvent(new Event("pagehide"));
    expect(hits(f)).toContainEqual({ kind: "play", slug: "song-001", seconds: 3 });
    cleanup(); const g = stub(GUEST); at("/join"); await waitFor(() => expect(hits(g)).toContainEqual({ kind: "pitch" }));
  });
  it("never counts the owner", async () => {
    for (const me of [OWNER_PUBLIC, OWNER_STUDIO]) { const f = stub(me); at("/song/song-001"); await screen.findByRole("heading", { name: "Tere Hone Se" }); expect(hits(f)).toEqual([]); cleanup(); }
  });
});

describe("the free public site (not signed in)", () => {
  it("opens on Browse with Home and Library in the navigation, and the menu offers Create account, not Studio, Account or Sign out", async () => {
    stub(GUEST); at("/"); expect(await screen.findByRole("heading", { name: "Browse", level: 1 })).toBeInTheDocument();
    const nav = screen.getAllByRole("navigation", { name: "Main" })[0]; expect(within(nav).getAllByRole("link").map((a) => a.textContent?.trim())).toEqual(["Home", "Library"]);
    fireEvent.click(screen.getAllByRole("button", { name: /Account menu, Visitor/ })[0]); const menu = await screen.findByRole("dialog", { name: "Account menu" });
    expect(within(menu).getByRole("link", { name: /Create account/ })).toHaveAttribute("href", "/join"); expect(within(menu).queryByRole("link", { name: /Studio/ })).toBeNull();   // no studio sign in on the public site
    expect(within(menu).queryByRole("link", { name: /Plan|Security/ })).toBeNull(); expect(within(menu).queryByRole("button", { name: "Sign out" })).toBeNull(); expect(within(menu).getByText("Appearance")).toBeInTheDocument();   // the theme choice is for everyone
  });
  it("plays a song with its lyrics and shows what an account will give: Save and Add to playlist say so", async () => {
    const f = stub(GUEST); at("/song/song-001"); fireEvent.click(await screen.findByRole("button", { name: "Play" })); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/play?slug=song-001")).toBe(true));
    expect(screen.getByLabelText("Lyrics", { selector: "p" })).toHaveTextContent("line one"); expect(document.querySelector("audio[controls]")).toBeNull();   // no browser player with a download item
    fireEvent.click(screen.getByRole("button", { name: "Add to a playlist" })); const join = await screen.findByRole("dialog", { name: "Create your account" }); expect(within(join).getByRole("link", { name: "Create account" })).toHaveAttribute("href", "/join");
    expect(f.mock.calls.some(([u]) => String(u).startsWith("/api/library") || String(u).startsWith("/api/playlists"))).toBe(false);   // nothing is asked of the server that needs an account
  });
  it("plays a song from its cover on Browse without opening the song page", async () => {
    const f = stub(GUEST); at("/"); fireEvent.click((await screen.findAllByRole("button", { name: "Play Tere Hone Se" }))[0]);   // the song is in Newest and in its language row
    await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/play?slug=song-001")).toBe(true));
    expect(screen.getByRole("heading", { name: "Browse", level: 1 })).toBeInTheDocument();   // still on Browse
    expect((await screen.findAllByRole("button", { name: "Pause Tere Hone Se" })).length).toBeGreaterThan(0);   // the cover's button follows the song
  });
  it("shares the song's page address without making a link on the server", async () => {
    const f = stub(GUEST); at("/song/song-001"); fireEvent.click(await screen.findByRole("button", { name: "Share" }));
    expect(await screen.findByLabelText(/Anyone with this link can listen/)).toHaveValue(`${location.origin}/app/song/song-001`);
    expect(f.mock.calls.some(([u]) => u === "/api/share")).toBe(false); expect(screen.queryByRole("button", { name: "Stop sharing" })).toBeNull();
  });
  it("the Library is open to visitors: songs to browse, and Create playlist leads to Create account; the studio screens say they are not here, with no sign in", async () => {
    const f = stub(GUEST); at("/library"); expect(await screen.findByText("Create your first playlist")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Create playlist/ })).toHaveAttribute("href", "/join"); expect(f.mock.calls.some(([u]) => String(u).startsWith("/api/playlists"))).toBe(false); cleanup();
    stub(GUEST); at("/studio/settings"); expect(await screen.findByText("This page is not available here")).toBeInTheDocument(); expect(screen.queryByRole("link", { name: /sign in/i })).toBeNull();
  });
  it("Create account asks what they like and keeps it, saying accounts open soon", async () => {
    const f = vi.fn((u: string, init?: RequestInit) => Promise.resolve(u.startsWith("/api/me") ? json(GUEST) : u.startsWith("/api/catalog/filters") ? json({ albums: [], languages: ["Hindi"], genres: ["Indie"] }) : json(init ? { ok: true } : [])));
    vi.stubGlobal("fetch", f); at("/join");
    fireEvent.click(await screen.findByRole("button", { name: "Calm" })); fireEvent.click(await screen.findByRole("button", { name: "Indie" })); fireEvent.change(screen.getByLabelText(/Email/), { target: { value: "a@b.co" } });
    fireEvent.click(screen.getByRole("button", { name: "Create my account" })); expect(await screen.findByText(/Accounts open soon/)).toBeInTheDocument();
    const call = f.mock.calls.find(([u]) => u === "/api/site/interest") as unknown as [string, RequestInit]; expect(JSON.parse(String(call[1].body))).toMatchObject({ moods: ["Calm"], genres: ["Indie"], languages: [], email: "a@b.co", website: "" });
  });
});

describe("feedback on a song", () => {
  const sent = (f: ReturnType<typeof stub>, path: string) => f.mock.calls.filter(([u]) => u === path).map(([, i]) => JSON.parse(String(i?.body)));
  it("counts thumbs up, love it and thumbs down, lets the visitor change their mind or take one back, and remembers it", async () => {
    const f = stub(GUEST); at("/song/song-001"); fireEvent.click(await screen.findByRole("button", { name: "What did you think?" })); await screen.findByRole("button", { name: "Thumbs up" });   // the reactions are in the sheet the icon at the top opens
    const b = (n: string | RegExp) => screen.getByRole("button", { name: n }); const pressed = (n: string | RegExp, v: string) => waitFor(() => expect(b(n)).toHaveAttribute("aria-pressed", v));
    fireEvent.click(b("Thumbs up")); await pressed("Thumbs up", "true"); expect(sent(f, "/api/site/react")).toEqual([{ slug: "song-001", reaction: "up" }]);
    fireEvent.click(b(/Love it/)); await pressed(/Love it/, "true"); expect(b("Thumbs up")).toHaveAttribute("aria-pressed", "false"); expect(sent(f, "/api/site/react")[1]).toEqual({ slug: "song-001", reaction: "love", previous: "up" });
    fireEvent.click(b(/Love it/)); await pressed(/Love it/, "false"); expect(sent(f, "/api/site/react")[2]).toEqual({ slug: "song-001", reaction: null, previous: "love" });   // taken back: no new reaction
    fireEvent.click(b("Thumbs down")); await pressed("Thumbs down", "true"); expect(localStorage.getItem("navaan-react:song-001")).toBe("down"); expect(await screen.findByText(/Tell us what to improve/)).toBeInTheDocument();   // a thumbs down invites a word
    cleanup(); stub(GUEST); at("/song/song-001"); fireEvent.click(await screen.findByRole("button", { name: "What did you think?" })); expect(await screen.findByRole("button", { name: "Thumbs down" })).toHaveAttribute("aria-pressed", "true");   // it came back
  });
  it("sends a message with an optional email, never shows the bot field, and says thank you", async () => {
    const f = stub(GUEST); at("/song/song-001"); fireEvent.click(await screen.findByRole("button", { name: "What did you think?" })); fireEvent.click(await screen.findByRole("button", { name: /Send feedback/ })); const dlg = await screen.findByRole("dialog", { name: /Feedback on/ });
    expect(within(dlg).getByLabelText(/Your email/)).not.toBeRequired(); expect(within(dlg).getByRole("button", { name: "Send" })).toBeDisabled();
    fireEvent.change(within(dlg).getByLabelText("Your message"), { target: { value: "Lovely second verse" } }); fireEvent.click(within(dlg).getByRole("button", { name: "Send" }));
    await waitFor(() => expect(sent(f, "/api/site/feedback")).toEqual([{ slug: "song-001", message: "Lovely second verse", website: "" }])); expect(await within(dlg).findByText(/Thank you/)).toBeInTheDocument();
  });
  it("sends the email when one is given, and shows the server's refusal", async () => {
    const f = vi.fn((u: string, _i?: RequestInit) => Promise.resolve(u.startsWith("/api/me") ? json(GUEST) : u.startsWith("/api/catalog/track/") ? json(TRACK) : u === "/api/site/feedback" ? json({ error: "that email address does not look right (you can leave it empty)" }, 400) : json([])));
    vi.stubGlobal("fetch", f); at("/song/song-001"); fireEvent.click(await screen.findByRole("button", { name: "What did you think?" })); fireEvent.click(await screen.findByRole("button", { name: /Send feedback/ })); const dlg = await screen.findByRole("dialog", { name: /Feedback on/ });
    fireEvent.change(within(dlg).getByLabelText("Your message"), { target: { value: "hi" } }); fireEvent.change(within(dlg).getByLabelText(/Your email/), { target: { value: "fan@example.com" } }); fireEvent.click(within(dlg).getByRole("button", { name: "Send" }));
    expect(await within(dlg).findByRole("alert")).toHaveTextContent("does not look right"); expect(JSON.parse(String(f.mock.calls.find(([u]) => u === "/api/site/feedback")![1]?.body)).email).toBe("fan@example.com");
  });
});

describe("one sign in for the owner on both hosts", () => {
  it("on the public site the owner sees Studio, and Settings and Security in the menu, as links to the studio host", async () => {
    stub(OWNER_PUBLIC); at("/"); await screen.findByRole("heading", { name: "Browse", level: 1 });
    expect(screen.getAllByRole("link", { name: /Studio/ })[0]).toHaveAttribute("href", "https://studio.navaan.online/app/studio");
    fireEvent.click(screen.getAllByRole("button", { name: /Account menu/ })[0]); const menu = await screen.findByRole("dialog", { name: "Account menu" });
    expect(within(menu).getByRole("link", { name: "Settings" })).toHaveAttribute("href", "https://studio.navaan.online/app/studio/settings"); expect(within(menu).getByRole("link", { name: "Security" })).toHaveAttribute("href", "https://studio.navaan.online/app/account/security");
    expect(within(menu).getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
  it("on the studio host the menu has a link to the public site", async () => {
    stub(OWNER_STUDIO); at("/studio"); await screen.findByRole("heading", { name: "Studio", level: 1 });
    fireEvent.click(screen.getAllByRole("button", { name: /Account menu/ })[0]); expect(within(await screen.findByRole("dialog", { name: "Account menu" })).getByRole("link", { name: /Public site/ })).toHaveAttribute("href", "https://navaan.online/app/");
  });
});

describe("the player's volume", () => {
  it("sets the loudness, mutes and unmutes, and remembers the level", async () => {
    stub(GUEST); at("/song/song-001"); fireEvent.click(await screen.findByRole("button", { name: "Play" })); const bar = await screen.findByRole("region", { name: "Now playing" }); const audio = document.querySelector("audio")!;
    expect(bar.querySelector("img")).toHaveAttribute("src", "/img/song-001/640.jpg");   // the bar shows the song's picture, not its first letter
    const slider = within(bar).getByLabelText("Volume") as HTMLInputElement; expect(audio.volume).toBe(1);
    fireEvent.change(slider, { target: { value: "40" } }); expect(audio.volume).toBeCloseTo(0.4); expect(localStorage.getItem("navaan-volume")).toBe("0.4");
    fireEvent.click(within(bar).getByRole("button", { name: "Mute" })); expect(audio.muted).toBe(true); expect(within(bar).getByRole("button", { name: "Unmute" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(within(bar).getByRole("button", { name: "Unmute" })); expect(audio.muted).toBe(false);
    fireEvent.change(slider, { target: { value: "0" } }); expect(audio.muted).toBe(true);   // all the way down is silent
    cleanup(); stub(GUEST); at("/song/song-001"); fireEvent.click(await screen.findByRole("button", { name: "Play" })); await screen.findByRole("region", { name: "Now playing" }); expect(document.querySelector("audio")!.volume).toBe(0);   // the level came back
  });
});
