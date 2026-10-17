import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { Cover } from "./Cover";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
const detail = { slug: "song-001", steps: [], next: { type: "done" }, text: { "title.txt": "Tere Hone Se" }, meta: { type: "music", state: "published", history: [] }, approvals: {}, job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "" };
let plays: string[]; let paused: boolean;
beforeEach(() => {
  plays = []; paused = true;
  Object.defineProperty(HTMLMediaElement.prototype, "paused", { configurable: true, get: () => paused });
  HTMLMediaElement.prototype.play = vi.fn(function (this: HTMLMediaElement) { plays.push(this.src); paused = false; this.dispatchEvent(new Event("play")); return Promise.resolve(); });
  HTMLMediaElement.prototype.pause = vi.fn(function (this: HTMLMediaElement) { paused = true; this.dispatchEvent(new Event("pause")); });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Cover", () => {
  it("asks for the right sizes and formats over the dominant colour, and fades in when loaded", () => {
    const { container } = render(<Cover slug="song-001" title="Tere" size={56} art={{ colour: "#c82828" }} />);
    const tile = container.querySelector(".cover") as HTMLElement; expect(tile.style.background).toBe("rgb(200, 40, 40)"); expect(tile.style.width).toBe("56px");   // the tile has its size before the picture arrives: no layout shift
    expect(container.querySelector('source[type="image/avif"]')).toHaveAttribute("srcset", "/img/song-001/320.avif 320w, /img/song-001/640.avif 640w, /img/song-001/1280.avif 1280w");
    expect(container.querySelector('source[type="image/webp"]')).toHaveAttribute("srcset", expect.stringContaining("/img/song-001/1280.webp 1280w"));
    const img = container.querySelector("img")!; expect(img).toHaveAttribute("src", "/img/song-001/640.jpg"); expect(img).toHaveAttribute("loading", "lazy"); expect(img.className).toBe("");
    fireEvent.load(img); expect(img.className).toBe("in");
  });
  it("shows the letter tile without art and when the picture fails", () => {
    const { container, rerender } = render(<Cover slug="song-002" title="Pata" art={null} />);
    expect(container.querySelector("img")).toBeNull(); expect(container.querySelector("b")).toHaveTextContent("P");
    rerender(<Cover slug="song-002" title="Pata" art={{ colour: null }} />); fireEvent.error(container.querySelector("img")!); expect(container.querySelector("img")).toBeNull();
  });
});

describe("playing a song", () => {
  it("plays through a link from /api/play, marks the song with an equaliser and keeps playing across screens", async () => {
    const f = vi.fn((url: string) => Promise.resolve(url.startsWith("/api/play") ? json({ url: "https://bucket.example/final.mp3", expires_in: 300 }) : url.startsWith("/api/song/") ? json(detail) : url.startsWith("/api/songs") ? json([]) : json({})));
    vi.stubGlobal("fetch", f);
    render(<MemoryRouter initialEntries={["/studio/songs/song-001?tab=publish"]}><App /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: /^Play/ }));
    await waitFor(() => expect(plays).toEqual(["https://bucket.example/final.mp3"]));
    expect(f.mock.calls.some(([u]) => u === "/api/play?slug=song-001")).toBe(true);
    expect((await screen.findAllByRole("img", { name: "Now playing" })).length).toBeGreaterThan(0);   // beside the title and in the bar
    const bar = screen.getByRole("region", { name: "Now playing" }); expect(bar).toHaveTextContent("Tere Hone Se");
    fireEvent.click(screen.getAllByRole("link", { name: "Songs" })[0]);   // another screen: the song goes on
    expect(await screen.findByRole("region", { name: "Now playing" })).toBeInTheDocument(); expect(HTMLMediaElement.prototype.pause).not.toHaveBeenCalled();
    fireEvent.click(within_(bar, "Pause")); await waitFor(() => expect(screen.queryAllByRole("img", { name: "Now playing" })).toHaveLength(0));   // paused: the equaliser stops marking it
    expect(plays).toHaveLength(1);
  });
  it("says so when the play link cannot be made", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(url.startsWith("/api/play") ? json({ error: "cannot make a play link right now" }, 502) : url.startsWith("/api/song/") ? json(detail) : json([]))));
    render(<MemoryRouter initialEntries={["/studio/songs/song-001?tab=publish"]}><App /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: /^Play/ }));
    expect(await screen.findByText(/cannot make a play link right now/)).toBeInTheDocument(); expect(plays).toHaveLength(0);
  });
});

const within_ = (el: HTMLElement, name: string) => Array.from(el.querySelectorAll("button")).find((b) => (b.getAttribute("aria-label") ?? b.textContent ?? "").startsWith(name))!;

describe("quality rules in the stylesheet", () => {
  const css = readFileSync(`${process.cwd()}/src/styles/base.css`, "utf8");
  it("stops every animation and transition when the person asks for reduced motion", () => { expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)[^}]*animation: none !important[^}]*transition: none !important/); });
  it("falls back to solid surfaces without backdrop-filter and with reduced transparency", () => {
    expect(css).toMatch(/@supports not \(\(backdrop-filter: blur\(1px\)\) or \(-webkit-backdrop-filter: blur\(1px\)\)\)/); expect(css).toMatch(/@media \(prefers-reduced-transparency: reduce\)/);
  });
  it("eases each block of a new screen in with opacity and transform only (nothing that shifts the layout)", () => {
    expect(css).toMatch(/\.page > \* \{ animation: rise /); const rise = css.slice(css.indexOf("@keyframes rise")); expect(rise.slice(0, rise.indexOf("}") + 1)).toMatch(/opacity: 0; transform: translateY\(8px\)/); expect(rise.slice(0, 160)).not.toMatch(/margin|height|width|top|left/);
  });
  it("shows no loading placeholder for a quick answer and soft blocks for a slow one, with the words always there for screen readers", async () => {
    vi.useFakeTimers(); const { Loading } = await import("./Loading"); const { container } = render(<Loading />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading…"); expect(container.querySelector(".skel")).toBeNull();
    await act(async () => { vi.advanceTimersByTime(200); }); expect(container.querySelector(".skel")).not.toBeNull(); vi.useRealTimers();
  });
});
void act;
