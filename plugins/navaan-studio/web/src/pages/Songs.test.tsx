import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json", "X-Request-Id": "req-1" } });
const row = (o: object) => ({ slug: "song-001", type: "music", title: "Tere Hone Se", state: "drafted", status: "approval", album: "", steps_done: 2, steps_total: 9, public: false, published: false, scheduled: "", next: { type: "gate", step: "suno", gate: "lyrics" }, ...o });
const step = (id: string, o: object = {}) => ({ id, label: id, kind: "claude", done: true, redo: true, restart: false, spends: false, status: "done", needs_gate: null, scheduled_for: null, ...o });
const detail = (o: object = {}) => ({
  slug: "song-001", steps: [step("lyrics", { status: "waiting for approval", needs_gate: "lyrics" }), step("suno", { done: false, status: "blocked" })], next: { type: "gate", step: "lyrics", gate: "lyrics" },
  text: { "title.txt": "Tere Hone Se\n", "lyrics.txt": "Tere hone se\nrang hai" }, meta: { state: "drafted", history: ["2026-10-16T01:00:00Z gate lyrics approved via ui:owner"] }, approvals: {},
  job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "", ...o,
});

function mock(routes: Record<string, (init?: RequestInit) => unknown>) {
  const f = vi.fn((url: string, init?: RequestInit) => { const k = Object.keys(routes).find((r) => url.startsWith(r)); return Promise.resolve(k ? json(routes[k](init)) : json({ error: "no route " + url }, 404)); });
  vi.stubGlobal("fetch", f); return f;
}
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Studio > Songs", () => {
  it("lists a refused YouTube thumbnail on Approvals with the way to fix it", async () => {
    mock({ "/api/songs": () => [row({ slug: "song-009", title: "Thumb One", status: "done", thumb_pending: true, next: { type: "done" } })] });
    at("/studio/approvals");
    expect(await screen.findByRole("heading", { name: "Set the YouTube thumbnail" })).toBeInTheDocument(); expect(screen.getByRole("link", { name: "Open Thumb One" })).toBeInTheDocument();
    expect(screen.queryByText("Nothing is waiting for you.")).toBeNull();
  });
  it("finds a song, groups by album, shows where its files are and its views, and filters to published or in the cloud", async () => {
    mock({ "/api/me": () => ({ user: "owner", roles: ["owner"], permissions: ["studio.access"] }), "/api/analytics/by-song": () => ({ "song-002": { views: 1200, yt_views: 300 } }),
      "/api/songs": () => [row({ album: "Monsoon" }), row({ slug: "song-002", title: "Done One", status: "done", published: true, archived: true, verified: true, album: "Monsoon", next: { type: "done" } }), row({ slug: "song-003", title: "Old One", archived: true, cleaned: true, thumb_pending: true })] });
    at("/studio/songs");
    const done = await screen.findByRole("link", { name: /Done One/ }); expect(done).toHaveTextContent("In the cloud"); await waitFor(() => expect(done).toHaveTextContent("1,200 on Instagram · 300 on YouTube views"));
    expect(screen.getByRole("link", { name: /Old One/ })).toHaveTextContent("Local cleaned"); expect(screen.getByRole("link", { name: /Old One/ })).toHaveTextContent("Thumbnail not set");
    fireEvent.change(screen.getByLabelText("Find a song"), { target: { value: "done" } }); expect(screen.queryByRole("link", { name: /Tere Hone Se/ })).toBeNull(); fireEvent.change(screen.getByLabelText("Find a song"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Group by"), { target: { value: "album" } }); expect(screen.getByRole("region", { name: "Monsoon" })).toHaveTextContent("Done One"); expect(screen.getByRole("region", { name: "No album" })).toHaveTextContent("Old One");
    fireEvent.click(screen.getByRole("button", { name: /^In the cloud/ })); expect(screen.queryByRole("link", { name: /Tere Hone Se/ })).toBeNull(); expect(screen.getByRole("link", { name: /Old One/ })).toBeInTheDocument();
    try { localStorage.removeItem("navaan.list.group"); } catch { /* storage may be blocked */ }
  });
  it("lists music with its state and next action, and filters", async () => {
    mock({ "/api/songs": () => [row({}), row({ slug: "song-002", title: "Done One", status: "done", published: true, next: { type: "done" } }), row({ slug: "insp-001", type: "inspiration" })] });
    at("/studio/songs");
    const link = await screen.findByRole("link", { name: /Tere Hone Se/ });
    expect(link).toHaveAttribute("href", "/studio/songs/song-001"); expect(link).toHaveTextContent("Waiting for you: Lyrics");
    expect(screen.queryByText("insp-001")).toBeNull();   // inspiration is NAV-14
    fireEvent.click(screen.getByRole("button", { name: /Done/ }));
    expect(screen.queryByRole("link", { name: /Tere Hone Se/ })).toBeNull(); expect(screen.getByRole("link", { name: /Done One/ })).toHaveTextContent("Published");
  });
});

describe("Studio > song", () => {
  it("shows the gate with what is approved, and Approve posts and reloads", async () => {
    let approved = false;
    const f = mock({ "/api/song/": () => (approved ? detail({ next: { type: "run", step: "suno" }, meta: { state: "approved", history: ["2026-10-16T02:00:00Z gate lyrics approved via ui:owner"] } }) : detail()), "/api/approve": () => { approved = true; return { ok: true }; } });
    at("/studio/songs/song-001");
    expect(await screen.findByRole("heading", { name: "Lyrics" })).toBeInTheDocument();
    expect(screen.getByLabelText(/lyrics.txt/)).toHaveTextContent("Tere hone se");
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await screen.findByRole("heading", { name: /Generate the song on Suno/ });
    const post = f.mock.calls.find(([u]) => u === "/api/approve")!; expect(JSON.parse(String(post[1]?.body))).toEqual({ slug: "song-001", gate: "lyrics" });
    fireEvent.click(screen.getByRole("tab", { name: "Activity" })); expect(screen.getByText(/gate lyrics approved via ui:owner/)).toBeInTheDocument();   // history says who
  });
  it("asks twice before a gate that spends credits", async () => {
    const f = mock({ "/api/song/": () => detail({ next: { type: "gate", step: "pictures", gate: "credits" } }), "/api/approve": () => ({ ok: true }) });
    at("/studio/songs/song-001");
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(f.mock.calls.some(([u]) => u === "/api/approve")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Yes, approve" }));
    await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/approve")).toBe(true));
  });
  it("Request changes needs a note and posts it", async () => {
    const f = mock({ "/api/song/": () => detail(), "/api/request-changes": () => ({ ok: true }) });
    at("/studio/songs/song-001");
    fireEvent.click(await screen.findByRole("button", { name: "Request changes" }));
    expect(screen.getByRole("button", { name: "Send back" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("What should change?"), { target: { value: "second verse too long" } });
    fireEvent.click(screen.getByRole("button", { name: "Send back" }));
    await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/request-changes")).toBe(true));
    expect(JSON.parse(String(f.mock.calls.find(([u]) => u === "/api/request-changes")![1]?.body))).toMatchObject({ gate: "lyrics", note: "second verse too long" });
  });
  it("shows a failed step with its log reference and a retry", async () => {
    const f = mock({ "/api/song/": () => detail({ next: { type: "run", step: "suno" }, steps: [step("suno", { done: false, status: "ready" })], failure: { step: "suno", error: "step suno failed after 3 attempts", ref: "job-42" } }), "/api/redo": () => ({ started: true }) });
    at("/studio/songs/song-001");
    const alert = await screen.findByRole("alert"); expect(alert).toHaveTextContent("Generate the song on Suno failed"); expect(alert).toHaveTextContent("job-42");
    fireEvent.click(screen.getByRole("button", { name: /Retry Generate the song on Suno/ }));
    await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/redo")).toBe(true));
    expect(JSON.parse(String(f.mock.calls.find(([u]) => u === "/api/redo")![1]?.body))).toEqual({ slug: "song-001", step: "suno" });
  });
  it("shows the server's error and request id when an action fails", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(url.startsWith("/api/song/") ? json(detail()) : json({ error: "a run is in progress" }, 409))));
    at("/studio/songs/song-001");
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("a run is in progress (ref req-1)");
  });
  it("has no serious accessibility violations (list, gate, failure)", async () => {
    for (const [path, routes] of [
      ["/studio/songs", { "/api/songs": () => [row({})] }],
      ["/studio/songs/song-001", { "/api/song/": () => detail() }],
      ["/studio/songs/song-001", { "/api/song/": () => detail({ failure: { step: "suno", error: "boom", ref: "job-1" }, next: { type: "run", step: "suno" } }) }],
    ] as const) {
      cleanup(); mock(routes); at(path); await screen.findAllByRole("heading", { level: 1 });
      await waitFor(() => expect(screen.queryByText("Loading…")).toBeNull());
      const r = await axe.run(document.body, { rules: { "color-contrast": { enabled: false } } });   // jsdom has no layout; contrast is covered by the theme test and the browser check
      expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    }
  });
});
