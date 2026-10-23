import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { OWNER } from "../components/Shell.test";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json", "X-Request-Id": "req-9" } });
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
const detail = (o: object = {}) => ({ slug: "reel-001", steps: [], next: { type: "run", step: "ingest" }, text: { "title.txt": "Quiet beach" }, files: {}, meta: { type: "reel", state: "draft", history: [] }, approvals: {}, job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "", ...o });
const settings = { media: { keys: { elevenlabs: true }, voices: { suno1: "Suno 1" }, settings: { voice: "suno1" } } };

// A stand-in for the browser's XMLHttpRequest: records what was sent and answers at once.
class FakeXHR {
  static sent: { url: string; token: string; body: unknown }[] = []; static status = 200; static reply = "{}";
  upload: { onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null; onerror: (() => void) | null = null; status = 0; responseText = ""; private url = ""; private token = "";
  open(_m: string, url: string) { this.url = url; }
  setRequestHeader(k: string, v: string) { if (k === "X-Navaan-Token") this.token = v; }
  send(body: unknown) { FakeXHR.sent.push({ url: this.url, token: this.token, body }); this.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 5 }); this.status = FakeXHR.status; this.responseText = FakeXHR.reply; setTimeout(() => this.onload?.(), 0); }
}

describe("Reels", () => {
  it("lists only reels, and creating one needs a video", async () => {
    const f = route(OWNER, { "/api/songs": () => [{ slug: "reel-001", type: "reel", title: "Quiet beach", state: "draft", status: "production", steps_done: 1, steps_total: 9, public: false, published: false, scheduled: "", album: "" }, { slug: "insp-004", type: "inspiration", title: "Tired", state: "draft", status: "production", steps_done: 1, steps_total: 9, public: false, published: false, scheduled: "", album: "" }], "/api/settings": () => settings });
    at("/studio/reels");
    expect(await screen.findByRole("heading", { name: "Reels", level: 1 })).toBeInTheDocument();
    expect(await screen.findByText("Quiet beach")).toBeInTheDocument(); expect(screen.queryByText("Tired")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "New reel" }));
    expect(screen.queryByLabelText(/Suno link/)).toBeNull(); expect(screen.queryByText(/When should it be published/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose your video first."); expect(posts(f, "/api/new")).toHaveLength(0);
  });

  it("creates the reel, sends the video as the raw body, then starts the pipeline", async () => {
    FakeXHR.sent = []; FakeXHR.status = 200; vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const f = route(OWNER, { "/api/new": () => ({ slug: "reel-001" }), "/api/run": () => ({ started: true }), "/api/songs": () => [], "/api/settings": () => settings, "/api/song/": () => detail() });
    at("/studio/reels"); fireEvent.click(await screen.findByRole("button", { name: "New reel" }));
    const video = new File(["frames"], "my walk.mp4", { type: "video/mp4" });
    fireEvent.change(screen.getByLabelText(/Your video/), { target: { files: [video] } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(posts(f, "/api/run")).toEqual([{ slug: "reel-001", all: true }]));
    expect(posts(f, "/api/new")[0]).toEqual({ type: "reel", idea: "", narrate: "eleven", voice: "suno1" });
    expect(FakeXHR.sent).toHaveLength(1); expect(FakeXHR.sent[0].url).toBe("/api/reel/upload?slug=reel-001&name=my%20walk.mp4"); expect(FakeXHR.sent[0].body).toBe(video);   // the file itself, not base64 in JSON
    await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/song/reel-001")).toBe(true));   // it opened the new reel
  });

  it("still opens the reel when the upload fails, and the reel's page offers the upload again", async () => {
    FakeXHR.sent = []; FakeXHR.status = 413; FakeXHR.reply = JSON.stringify({ error: "that video is 3000 MB; the limit is 2048 MB" }); vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const f = route(OWNER, { "/api/new": () => ({ slug: "reel-001" }), "/api/run": () => ({ started: true }), "/api/songs": () => [], "/api/settings": () => settings, "/api/song/": () => detail() });
    at("/studio/reels"); fireEvent.click(await screen.findByRole("button", { name: "New reel" }));
    fireEvent.change(screen.getByLabelText(/Your video/), { target: { files: [new File(["x"], "big.mov")] } }); fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("heading", { name: "This reel has no footage yet" })).toBeInTheDocument();
    expect(posts(f, "/api/run")).toHaveLength(0);   // nothing is started without footage
    const back = document.querySelector("a.back"); expect(back).toHaveTextContent("Reels"); expect(back).toHaveAttribute("href", "/studio/reels");   // the back link names the list
  });

  it("does not ask for footage once the working copy exists, or while a job runs", async () => {
    route(OWNER, { "/api/songs": () => [], "/api/song/": () => detail({ files: { "source.mp4": 9000 } }) });
    at("/studio/reels/reel-001"); expect(await screen.findByRole("heading", { name: "Quiet beach", level: 1 })).toBeInTheDocument();
    expect(screen.queryByText("This reel has no footage yet")).toBeNull();
    cleanup();
    route(OWNER, { "/api/songs": () => [], "/api/song/": () => detail({ job: { running: true, queued: false, rc: null }, status_text: "running ingest" }) });
    at("/studio/reels/reel-001"); expect(await screen.findByRole("heading", { name: "Quiet beach", level: 1 })).toBeInTheDocument();
    expect(screen.queryByText("This reel has no footage yet")).toBeNull();
  });

  it("shows the edit plan in words at its approval, and the critic's notes at the final cut", async () => {
    route(OWNER, { "/api/songs": () => [], "/api/song/": () => detail({ files: { "source.mp4": 9000 }, next: { type: "gate", step: "edit_check", gate: "edit_plan" }, gates: ["edit_plan"], text: { "title.txt": "Quiet beach", "edl.json": "{\"segments\": []}", "edl_summary.md": "# Edit plan: 14.0 s reel\n1. footage 2.0-9.0 s -> reel 0.0-7.0 s" } }) });
    at("/studio/reels/reel-001");
    expect(await screen.findByRole("heading", { name: "Edit plan" })).toBeInTheDocument();
    expect(screen.getByLabelText("The edit plan in plain words")).toHaveTextContent("footage 2.0-9.0 s -> reel 0.0-7.0 s");
    expect(screen.getByRole("button", { name: /Approve/ })).toBeInTheDocument();
    cleanup();
    route(OWNER, { "/api/songs": () => [], "/api/song/": () => detail({ files: { "source.mp4": 9000, "final_reel_9x16.mp4": 5000 }, next: { type: "gate", step: "critique", gate: "media" }, gates: ["media"], text: { "title.txt": "Quiet beach", "critique.json": JSON.stringify({ verdict: "fix", summary: "The last quote line sits low.", fixes: ["Move the quote up (edit plan)"] }) } }) });
    at("/studio/reels/reel-001");
    expect(await screen.findByText("The reviewer suggests changes")).toBeInTheDocument();
    expect(screen.getByText("Move the quote up (edit plan)")).toBeInTheDocument();
  });

  it("shows the automatic check of an inspiration at the video approval, in its own words, beside Approve (NAV-147)", async () => {
    const qa = (o: object) => JSON.stringify({ source: "checks", ...o });
    route(OWNER, { "/api/songs": () => [], "/api/song/": () => detail({ slug: "insp-008", files: { "final_reel_9x16.mp4": 5000 }, next: { type: "gate", step: "qa", gate: "media" }, gates: ["media"], meta: { type: "inspiration", state: "rendered", history: [] },
      text: { "title.txt": "Let it go", "qa.json": qa({ verdict: "fix", summary: "insp-008: the automatic checks found 1 problem.", fixes: ["line 5 (\"Your peace matters too.\") is lit 6.4 s from where it is spoken"] }) } }) });
    at("/studio/inspiration/insp-008");
    expect(await screen.findByText("The automatic check suggests changes")).toBeInTheDocument();
    expect(screen.getByText(/lit 6\.4 s from where it is spoken/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Approve/ })).toBeInTheDocument();   // the owner can still decide
    cleanup();
    route(OWNER, { "/api/songs": () => [], "/api/song/": () => detail({ slug: "insp-008", files: { "final_reel_9x16.mp4": 5000 }, next: { type: "gate", step: "qa", gate: "media" }, gates: ["media"], meta: { type: "inspiration", state: "rendered", history: [] },
      text: { "title.txt": "Let it go", "qa.json": qa({ verdict: "pass", summary: "Nothing to fix.", fixes: [] }) } }) });
    at("/studio/inspiration/insp-008");
    expect(await screen.findByText("The automatic check found nothing to fix")).toBeInTheDocument();
  });
});
