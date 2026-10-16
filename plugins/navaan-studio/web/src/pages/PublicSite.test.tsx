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
  paused = true; try { localStorage.clear(); } catch { /* storage may be blocked */ }
  Object.defineProperty(HTMLMediaElement.prototype, "paused", { configurable: true, get: () => paused });
  HTMLMediaElement.prototype.play = vi.fn(function (this: HTMLMediaElement) { paused = false; this.dispatchEvent(new Event("play")); return Promise.resolve(); });
  HTMLMediaElement.prototype.pause = vi.fn(function (this: HTMLMediaElement) { paused = true; this.dispatchEvent(new Event("pause")); });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("the free public site (not signed in)", () => {
  it("opens on Browse with only Home in the navigation, and the menu offers the studio sign in, not Account or Sign out", async () => {
    stub(GUEST); at("/"); expect(await screen.findByRole("heading", { name: "Browse", level: 1 })).toBeInTheDocument();
    const nav = screen.getAllByRole("navigation", { name: "Main" })[0]; expect(within(nav).getAllByRole("link").map((a) => a.textContent?.trim())).toEqual(["Home"]);
    fireEvent.click(screen.getAllByRole("button", { name: /Account menu, Visitor/ })[0]); const menu = await screen.findByRole("dialog", { name: "Account menu" });
    expect(within(menu).getByRole("link", { name: /Studio sign in/ })).toHaveAttribute("href", "https://studio.navaan.online/app/");
    expect(within(menu).queryByRole("link", { name: /Account|Plan|Security/ })).toBeNull(); expect(within(menu).queryByRole("button", { name: "Sign out" })).toBeNull(); expect(within(menu).getByText("Appearance")).toBeInTheDocument();   // the theme choice is for everyone
  });
  it("plays a song with its lyrics and shows what an account will give: Save and Add to playlist say so", async () => {
    const f = stub(GUEST); at("/song/song-001"); fireEvent.click(await screen.findByRole("button", { name: "Play" })); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/play?slug=song-001")).toBe(true));
    expect(screen.getByLabelText("Lyrics", { selector: "p" })).toHaveTextContent("line one"); expect(document.querySelector("audio[controls]")).toBeNull();   // no browser player with a download item
    fireEvent.click(screen.getByRole("button", { name: "Add to playlist" })); expect(await screen.findByText(/Accounts are coming soon/)).toBeInTheDocument();
    expect(f.mock.calls.some(([u]) => String(u).startsWith("/api/library") || String(u).startsWith("/api/playlists"))).toBe(false);   // nothing is asked of the server that needs an account
  });
  it("shares the song's page address without making a link on the server", async () => {
    const f = stub(GUEST); at("/song/song-001"); fireEvent.click(await screen.findByRole("button", { name: "Share" }));
    expect(await screen.findByLabelText(/Anyone with this link can listen/)).toHaveValue(`${location.origin}/app/song/song-001`);
    expect(f.mock.calls.some(([u]) => u === "/api/share")).toBe(false); expect(screen.queryByRole("button", { name: "Stop sharing" })).toBeNull();
  });
  it("member-only screens invite instead of failing, and the studio ones point to the studio sign in", async () => {
    stub(GUEST); at("/library"); expect(await screen.findByText(/Accounts are coming soon/)).toBeInTheDocument(); cleanup();
    stub(GUEST); at("/studio/settings"); expect(await screen.findByText("The studio is for the owner")).toBeInTheDocument(); expect(screen.getByRole("link", { name: "Studio sign in" })).toHaveAttribute("href", "https://studio.navaan.online/app/");
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
    const slider = within(bar).getByLabelText("Volume") as HTMLInputElement; expect(audio.volume).toBe(1);
    fireEvent.change(slider, { target: { value: "40" } }); expect(audio.volume).toBeCloseTo(0.4); expect(localStorage.getItem("navaan-volume")).toBe("0.4");
    fireEvent.click(within(bar).getByRole("button", { name: "Mute" })); expect(audio.muted).toBe(true); expect(within(bar).getByRole("button", { name: "Unmute" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(within(bar).getByRole("button", { name: "Unmute" })); expect(audio.muted).toBe(false);
    fireEvent.change(slider, { target: { value: "0" } }); expect(audio.muted).toBe(true);   // all the way down is silent
    cleanup(); stub(GUEST); at("/song/song-001"); fireEvent.click(await screen.findByRole("button", { name: "Play" })); await screen.findByRole("region", { name: "Now playing" }); expect(document.querySelector("audio")!.volume).toBe(0);   // the level came back
  });
});
