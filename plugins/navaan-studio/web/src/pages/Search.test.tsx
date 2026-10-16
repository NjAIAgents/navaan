import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json", "X-Request-Id": "req-3" } });
function mock(routes: Record<string, (init?: RequestInit) => unknown | Response>) {
  const f = vi.fn((url: string, init?: RequestInit) => { const k = Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => url.startsWith(r)); const v = k ? routes[k](init) : { error: "no route " + url }; return Promise.resolve(v instanceof Response ? v : json(v, k ? 200 : 404)); });
  vi.stubGlobal("fetch", f); return f;
}
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const hit = { kind: "track", id: "u1", slug: "song-003", title: "तेरे होने से", title_roman: "tere hone se", score: 1.75 };

describe("search", () => {
  it("the top bar search goes to the results page with what was typed", async () => {
    const f = mock({ "/api/search": () => ({ hits: [hit] }) });
    at("/studio/songs");
    fireEvent.change(screen.getByRole("searchbox", { name: "Search songs, albums, lyrics" }), { target: { value: "tere hone se" } });
    fireEvent.submit(screen.getByRole("searchbox", { name: "Search songs, albums, lyrics" }).closest("form")!);
    const link = await screen.findByRole("link", { name: /तेरे होने से/ });
    expect(link).toHaveAttribute("href", "/song/song-003"); expect(link).toHaveTextContent("tere hone se"); expect(link).toHaveTextContent("Song");
    expect(f.mock.calls.some(([u]) => u === "/api/search?q=tere%20hone%20se")).toBe(true);
  });
  it("says so when nothing is found, and does not search for a single letter", async () => {
    const f = mock({ "/api/search": () => ({ hits: [] }) });
    at("/search?q=zzzz"); expect(await screen.findByText(/Nothing found for "zzzz"/)).toBeInTheDocument();
    cleanup(); f.mockClear(); at("/search?q=z"); await new Promise((r) => setTimeout(r, 20)); expect(f.mock.calls.some(([u]) => String(u).startsWith("/api/search"))).toBe(false);
  });
  it("shows the server's error with its request id", async () => {
    mock({ "/api/search": () => json({ error: "database down" }, 500) }); at("/search?q=tere");
    expect(await screen.findByRole("alert")).toHaveTextContent("database down (ref req-3)");
  });
  it("has no serious accessibility violations", async () => {
    mock({ "/api/search": () => ({ hits: [hit] }) }); at("/search?q=tere"); await screen.findByRole("link", { name: /तेरे होने से/ });
    const r = await axe.run(document.body, { rules: { "color-contrast": { enabled: false } } });
    expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
  });
});

describe("share link on a published song", () => {
  const detail = (state: string) => ({ slug: "song-001", steps: [], next: { type: "done" }, text: { "title.txt": "Tere Hone Se" }, meta: { type: "music", state, history: [] }, approvals: {}, job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "" });
  it("creates a link and can stop it; an unpublished song has no Share section", async () => {
    const f = mock({ "/api/song/": () => detail("published"), "/api/share/revoke": () => ({ revoked: true }), "/api/share": () => ({ token: "tok123", url: "https://navaan.example/s/tok123" }) });
    at("/studio/songs/song-001");
    fireEvent.click(await screen.findByRole("button", { name: "Create a share link" }));
    expect(await screen.findByLabelText(/Anyone with this link can listen/)).toHaveValue("https://navaan.example/s/tok123");
    fireEvent.click(screen.getByRole("button", { name: "Stop sharing" }));
    await screen.findByText("That link no longer works.");
    expect(JSON.parse(String(f.mock.calls.find(([u]) => u === "/api/share/revoke")![1]?.body))).toEqual({ token: "tok123" });
    cleanup(); mock({ "/api/song/": () => detail("drafted") }); at("/studio/songs/song-001"); await screen.findByRole("heading", { level: 1, name: "Tere Hone Se" }); expect(screen.queryByRole("button", { name: "Create a share link" })).toBeNull();
  });
  it("shows why a link cannot be made", async () => {
    mock({ "/api/song/": () => detail("published"), "/api/share": () => json({ error: "this track's licence is not confirmed, so it cannot be shared yet" }, 400) });
    at("/studio/songs/song-001"); fireEvent.click(await screen.findByRole("button", { name: "Create a share link" }));
    expect(await screen.findByText(/licence is not confirmed/)).toBeInTheDocument();
  });
});
