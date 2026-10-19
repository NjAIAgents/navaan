import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { OWNER } from "../components/Shell.test";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json", "X-Request-Id": "req-11" } });
function route(me: unknown, routes: Record<string, (init?: RequestInit) => unknown>) {
  const f = vi.fn((u: string, init?: RequestInit) => {
    if (u.startsWith("/api/me")) return Promise.resolve(json(me));
    const k = Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => u === r || u.startsWith(r)); const v = k ? routes[k](init) : [];
    return Promise.resolve(v instanceof Response ? v : json(v));
  });
  vi.stubGlobal("fetch", f); return f;
}
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
const posts = (f: ReturnType<typeof route>, path: string) => f.mock.calls.filter(([u]) => u === path).map(([, i]) => JSON.parse(String(i?.body)));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const detail = (o: object = {}) => ({ slug: "insp-001", steps: [], next: { type: "run", step: "background" }, text: { "title.txt": "Quiet" }, files: {}, meta: { type: "inspiration", state: "draft", history: [] }, approvals: {}, job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "", ...o });
const settings = { media: { keys: { elevenlabs: true }, voices: { suno1: "Suno 1" }, settings: { voice: "suno1" } } };

class FakeXHR {
  static sent: { url: string; body: unknown }[] = []; static status = 200; static reply = "{}";
  upload: { onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null; onerror: (() => void) | null = null; status = 0; responseText = ""; private url = "";
  open(_m: string, url: string) { this.url = url; }
  setRequestHeader() { /* the token is not needed here */ }
  send(body: unknown) { FakeXHR.sent.push({ url: this.url, body }); this.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 5 }); this.status = FakeXHR.status; this.responseText = FakeXHR.reply; setTimeout(() => this.onload?.(), 0); }
}

describe("An inspiration's own scene video", () => {
  it("can be chosen when the short is created, and goes up after it is made", async () => {
    FakeXHR.sent = []; FakeXHR.status = 200; vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const f = route(OWNER, { "/api/new": () => ({ slug: "insp-009" }), "/api/songs": () => [], "/api/settings": () => settings, "/api/song/": () => detail({ slug: "insp-009" }) });
    at("/studio/inspiration"); fireEvent.click(await screen.findByRole("button", { name: "New inspiration" }));
    const scene = new File(["frames"], "my scene.mp4", { type: "video/mp4" });
    fireEvent.change(screen.getByLabelText(/Suno link/), { target: { value: "https://suno.com/s/abc" } });
    fireEvent.change(screen.getByLabelText(/Scene video/), { target: { files: [scene] } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(FakeXHR.sent).toHaveLength(1));
    expect(FakeXHR.sent[0].url).toBe("/api/reel/upload?slug=insp-009&name=my%20scene.mp4"); expect(FakeXHR.sent[0].body).toBe(scene);
    expect(posts(f, "/api/new")[0]).toMatchObject({ type: "inspiration", suno_url: "https://suno.com/s/abc" });
    await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/song/insp-009")).toBe(true));
  });

  it("is optional: without one the short is made as before, with no upload", async () => {
    FakeXHR.sent = []; vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const f = route(OWNER, { "/api/new": () => ({ slug: "insp-010" }), "/api/songs": () => [], "/api/settings": () => settings, "/api/song/": () => detail({ slug: "insp-010" }) });
    at("/studio/inspiration"); fireEvent.click(await screen.findByRole("button", { name: "New inspiration" }));
    fireEvent.change(screen.getByLabelText(/Quote or idea/), { target: { value: "Maybe you are not behind" } }); fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(posts(f, "/api/new")).toHaveLength(1)); expect(FakeXHR.sent).toHaveLength(0);
  });

  it("is not offered when creating an Aha-lorithm short, a reel or a song", async () => {
    route(OWNER, { "/api/songs": () => [], "/api/settings": () => settings });
    at("/studio/aha"); fireEvent.click(await screen.findByRole("button", { name: "New Aha-lorithm short" })); expect(screen.queryByLabelText(/Scene video/)).toBeNull();
    cleanup(); route(OWNER, { "/api/songs": () => [], "/api/settings": () => settings });
    at("/studio/songs"); fireEvent.click(await screen.findByRole("button", { name: "New song" })); expect(screen.queryByLabelText(/Scene video/)).toBeNull();
  });

  it("is offered on the short's page before it is rendered, and goes up from there", async () => {
    FakeXHR.sent = []; FakeXHR.status = 200; vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const f = route(OWNER, { "/api/songs": () => [], "/api/song/": () => detail({ scene: { ready: false, pending: false, fit: null } }) });
    at("/studio/inspiration/insp-001?tab=content");
    expect(await screen.findByRole("heading", { name: "Scene video" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Upload" })); expect(await screen.findByRole("alert")).toHaveTextContent("Choose a video first.");
    const scene = new File(["x"], "s.mov"); fireEvent.change(screen.getByLabelText(/Your scene video/), { target: { files: [scene] } }); fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    await waitFor(() => expect(FakeXHR.sent).toHaveLength(1)); expect(FakeXHR.sent[0].url).toBe("/api/reel/upload?slug=insp-001&name=s.mov");
    await waitFor(() => expect(f.mock.calls.filter(([u]) => u === "/api/song/insp-001").length).toBeGreaterThan(1));   // the page reloads to show it
  });

  it("says how the scene was fitted, and can be removed", async () => {
    const f = route(OWNER, { "/api/scene/remove": () => ({ ok: true }), "/api/songs": () => [], "/api/song/": () => detail({ files: { "scene_src.mp4": 5000 }, scene: { ready: true, pending: false, fit: { src_seconds: 7, total: 12.4, stretch: 1.5, hold: 1.9, cut: false } } }) });
    at("/studio/inspiration/insp-001?tab=content");
    expect(await screen.findByText(/Your scene video is ready/)).toHaveTextContent("plays 1.5 times slower and its last frame is held 1.9 s, so the credit page ends the short");
    fireEvent.click(screen.getByRole("button", { name: "Remove the scene video" }));
    await waitFor(() => expect(posts(f, "/api/scene/remove")).toEqual([{ slug: "insp-001" }]));
  });

  it("is hidden once the short has its video, and for other types", async () => {
    route(OWNER, { "/api/songs": () => [], "/api/song/": () => detail({ files: { "final_reel_9x16.mp4": 9000 } }) });
    at("/studio/inspiration/insp-001?tab=content"); expect(await screen.findByRole("heading", { name: "Quiet", level: 1 })).toBeInTheDocument(); expect(screen.queryByRole("heading", { name: "Scene video" })).toBeNull();
    cleanup(); route(OWNER, { "/api/songs": () => [], "/api/song/": () => detail({ slug: "aha-001", meta: { type: "aha", state: "draft", history: [] } }) });
    at("/studio/aha/aha-001?tab=content"); expect(await screen.findByRole("heading", { name: "Quiet", level: 1 })).toBeInTheDocument(); expect(screen.queryByRole("heading", { name: "Scene video" })).toBeNull();
  });
});
