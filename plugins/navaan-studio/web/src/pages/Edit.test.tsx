import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { OWNER } from "../components/Shell.test";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
function route(routes: Record<string, (init?: RequestInit) => unknown>) {
  const f = vi.fn((u: string, init?: RequestInit) => {
    if (u.startsWith("/api/me")) return Promise.resolve(json(OWNER));
    const k = Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => u === r || u.startsWith(r)); const v = k ? routes[k](init) : [];
    return Promise.resolve(v instanceof Response ? v : json(v));
  });
  vi.stubGlobal("fetch", f); return f;
}
const posts = (f: ReturnType<typeof route>, path: string) => f.mock.calls.filter(([u]) => u === path).map(([, i]) => JSON.parse(String(i?.body)));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); });

const SHOTS = JSON.stringify({ duration: 30, notes: "", shots: [{ id: 1, label: "open", start: 0, end: 5, image: "images/a.png", camera: "push_in", focus: [0.5, 0.5], scene: "", lyric: "" }] });
const detail = (o: object = {}) => ({
  slug: "song-001", steps: [], next: { type: "run", step: "lyrics" }, text: { "title.txt": "Tere", "lyrics.txt": "line one", "shots.json": SHOTS }, files: { "final.mp3": 5, "video.mp4": 9 },
  meta: { type: "music", state: "drafted", history: [] }, approvals: {}, job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "",
  cameras: ["push_in", "hold"], images: ["a.png", "b.png"], cloud: false, ...o,
});
const open = (name: string) => { const s = screen.getByText(name, { selector: "summary b" }); fireEvent.click(s); };

describe("editing a song (NAV-22)", () => {
  it("saves edited lyrics and shows the change as saved", async () => {
    const f = route({ "/api/save": () => ({ ok: true }), "/api/song/": () => detail() });
    render(<MemoryRouter initialEntries={["/studio/songs/song-001"]}><App /></MemoryRouter>);
    await screen.findByRole("heading", { name: "Words and settings" }); open("Lyrics");
    const box = screen.getByLabelText(/^Lyrics/); fireEvent.change(box, { target: { value: "line one\nline two" } });
    expect(screen.getByText(/Unsaved changes/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save lyrics" }));
    await waitFor(() => expect(posts(f, "/api/save")).toEqual([{ slug: "song-001", file: "lyrics.txt", content: "line one\nline two" }]));
  });
  it("keeps an unsaved draft for the tab and warns before leaving", async () => {
    route({ "/api/song/": () => detail() });
    const warn = vi.fn(); window.addEventListener("beforeunload", warn);
    render(<MemoryRouter initialEntries={["/studio/songs/song-001"]}><App /></MemoryRouter>);
    await screen.findByRole("heading", { name: "Words and settings" }); open("Lyrics");
    fireEvent.change(screen.getByLabelText(/^Lyrics/), { target: { value: "half done" } });
    await waitFor(() => expect(sessionStorage.getItem("navaan-draft:song-001:lyrics.txt")).toBe("half done"));
    const ev = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(ev); expect(ev.defaultPrevented).toBe(true);
    window.removeEventListener("beforeunload", warn);
  });
  it("shows the server's refusal and keeps the text", async () => {
    route({ "/api/save": () => json({ error: "Expecting value" }, 400), "/api/song/": () => detail({ text: { "tags.json": "{}" } }) });
    render(<MemoryRouter initialEntries={["/studio/songs/song-001"]}><App /></MemoryRouter>);
    await screen.findByRole("heading", { name: "Words and settings" }); open("Tags");
    fireEvent.change(screen.getByLabelText(/^Tags/), { target: { value: "{" } }); fireEvent.click(screen.getByRole("button", { name: "Save tags" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Expecting value"); expect((screen.getByLabelText(/^Tags/) as HTMLTextAreaElement).value).toBe("{");
  });
  it("saves the shot list with the changed camera move", async () => {
    const f = route({ "/api/shots/save": () => ({ ok: true }), "/api/song/": () => detail() });
    render(<MemoryRouter initialEntries={["/studio/songs/song-001"]}><App /></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText("Camera move"), { target: { value: "hold" } });
    fireEvent.click(screen.getByRole("button", { name: "Save shot list" }));
    await waitFor(() => expect(posts(f, "/api/shots/save")).toHaveLength(1)); const b = posts(f, "/api/shots/save")[0];
    expect(b.shots[0]).toMatchObject({ camera: "hold", image: "images/a.png", start: 0, end: 5 }); expect(b.slug).toBe("song-001");
  });
  it("plays the made audio and video, and falls back to the bucket copy when audio is archived", async () => {
    route({ "/api/song/": () => detail() });
    const { unmount } = render(<MemoryRouter initialEntries={["/studio/songs/song-001"]}><App /></MemoryRouter>);
    expect(await screen.findByLabelText("final.mp3")).toHaveAttribute("src", "/media/song-001/final.mp3"); expect(screen.getByLabelText("video.mp4")).toHaveAttribute("src", "/media/song-001/video.mp4");
    unmount(); cleanup();
    route({ "/api/song/": () => detail({ files: {}, cloud: true }) });
    render(<MemoryRouter initialEntries={["/studio/songs/song-001"]}><App /></MemoryRouter>);
    expect(await screen.findByText(/archived in the bucket/)).toBeInTheDocument(); expect(screen.getByLabelText("final.mp3")).toHaveAttribute("src", "/media/song-001/final.mp3");
  });
  it("attaches a narration to an inspiration, with words when there is no .srt", async () => {
    const f = route({ "/api/narration/upload": () => ({ ok: true }), "/api/song/": () => detail({ meta: { type: "inspiration", state: "drafted", history: [] }, files: {} }) });
    render(<MemoryRouter initialEntries={["/studio/inspiration/song-001"]}><App /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Attach narration" })); expect(await screen.findByRole("alert")).toHaveTextContent("Pick the narration audio first.");
    fireEvent.change(screen.getByLabelText(/^Audio/), { target: { files: [new File(["abc"], "v.mp3", { type: "audio/mpeg" })] } });
    fireEvent.change(screen.getByLabelText("Words, one line per row"), { target: { value: "one\ntwo" } }); fireEvent.click(screen.getByRole("button", { name: "Attach narration" }));
    await waitFor(() => expect(posts(f, "/api/narration/upload")).toHaveLength(1)); expect(posts(f, "/api/narration/upload")[0]).toMatchObject({ slug: "song-001", audio_name: "v.mp3", audio: "YWJj", srt: "", text: "one\ntwo" });
  });
  it("has no serious accessibility violations", async () => {
    route({ "/api/song/": () => detail() });
    const { container } = render(<MemoryRouter initialEntries={["/studio/songs/song-001"]}><App /></MemoryRouter>);
    await screen.findByRole("heading", { name: "Shot list" }); open("Lyrics");
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } }); expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  });
});

describe("choosing the visuals (NAV-23)", () => {
  const gated = (o: object = {}) => detail({ next: { type: "gate", step: "visuals", gate: "visuals_mode" }, text: { "title.txt": "Tere" }, images: [], files: {}, visuals: {}, ...o });
  it("needs 4 pictures for a video, takes uploads, and saves the choice", async () => {
    let images: string[] = [];
    const f = route({ "/api/visuals/upload": () => { images = [...images, `p${images.length}.png`]; return { path: "x" }; }, "/api/visuals/save": () => ({ ok: true }), "/api/song/": () => gated({ images }) });
    render(<MemoryRouter initialEntries={["/studio/songs/song-001"]}><App /></MemoryRouter>);
    const save = await screen.findByRole("button", { name: "Save and continue" }); expect(save).toBeDisabled(); expect(screen.getByText(/0 pictures added, 4 needed/)).toBeInTheDocument();
    const file = (n: string) => new File(["abc"], n, { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Pictures"), { target: { files: [file("a.png"), file("b.png"), file("c.png"), file("d.png")] } });
    await waitFor(() => expect(posts(f, "/api/visuals/upload")).toHaveLength(4)); expect(posts(f, "/api/visuals/upload")[0]).toEqual({ slug: "song-001", name: "a.png", data: "YWJj" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Save and continue" })).toBeEnabled());
    fireEvent.change(screen.getByLabelText(/^Look notes/), { target: { value: "monsoon night" } }); fireEvent.click(screen.getByRole("button", { name: "Save and continue" }));
    await waitFor(() => expect(posts(f, "/api/visuals/save")).toEqual([{ slug: "song-001", mode: "own", layout: "video", camera: "", scene: "monsoon night" }]));
  });
  it("lets Google Flow skip the pictures and removes a picture", async () => {
    const f = route({ "/api/visuals/remove": () => ({ ok: true }), "/api/visuals/save": () => ({ ok: true }), "/api/song/": () => gated({ images: ["a.png"] }) });
    render(<MemoryRouter initialEntries={["/studio/songs/song-001"]}><App /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Remove picture a.png" })); await waitFor(() => expect(posts(f, "/api/visuals/remove")).toEqual([{ slug: "song-001", path: "images/a.png" }]));
    fireEvent.change(screen.getByLabelText("Look"), { target: { value: "flow" } }); expect(screen.getByRole("button", { name: "Save and continue" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Save and continue" })); await waitFor(() => expect(posts(f, "/api/visuals/save")[0]).toMatchObject({ mode: "flow" }));
  });
  it("writes and copies prompts, and runs the 2-picture test when OpenAI is on", async () => {
    const pack = { aspect: "16:9", style_line: "Cinematic", prompts: [{ n: 1, section: "verse", prompt: "a lamp" }] };
    const writeText = vi.fn(() => Promise.resolve()); Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const f = route({ "/api/visuals/prompts": () => ({ ok: true }), "/api/visuals/try": () => ({ ok: true }), "/api/song/": () => gated({ prompt_pack: pack, openai_pictures: true, images: ["a.png"] }) });
    render(<MemoryRouter initialEntries={["/studio/songs/song-001"]}><App /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Copy prompt 1 with style line" })); await waitFor(() => expect(writeText).toHaveBeenCalledWith("Cinematic a lamp"));
    fireEvent.click(screen.getByRole("button", { name: "Write them again" })); await waitFor(() => expect(posts(f, "/api/visuals/prompts")).toHaveLength(1));
    fireEvent.click(screen.getByRole("button", { name: /Try the first 2 pictures/ })); await waitFor(() => expect(posts(f, "/api/visuals/try")).toHaveLength(1));
    expect(screen.getByText(/OpenAI will make the pictures after you save/)).toBeInTheDocument();
  });
  it("has no serious accessibility violations", async () => {
    route({ "/api/song/": () => gated({ images: ["a.png"], prompt_pack: { style_line: "S", prompts: [{ n: 1, section: "v", prompt: "p" }] } }) });
    const { container } = render(<MemoryRouter initialEntries={["/studio/songs/song-001"]}><App /></MemoryRouter>);
    await screen.findByRole("heading", { name: "How should the video look?" });
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } }); expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  });
});

describe("redo and restart a step", () => {
  it("asks first, then redoes only that step, or restarts from it", async () => {
    const steps = [{ id: "video", label: "Build the video", kind: "x", done: true, redo: true, restart: true, spends: false, status: "done", needs_gate: null, scheduled_for: null }];
    const f = route({ "/api/redo": () => ({ started: true }), "/api/restart": () => ({ started: true }), "/api/song/": () => detail({ steps }) });
    render(<MemoryRouter initialEntries={["/studio/songs/song-001"]}><App /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Redo Build the video" })); expect(posts(f, "/api/redo")).toHaveLength(0); expect(screen.getByRole("group", { name: /Confirm redo/ })).toHaveTextContent("_prev");
    fireEvent.click(screen.getByRole("button", { name: "Yes, redo it" })); await waitFor(() => expect(posts(f, "/api/redo")).toEqual([{ slug: "song-001", step: "video" }]));
    fireEvent.click(await screen.findByRole("button", { name: "Restart from Build the video" })); fireEvent.click(screen.getByRole("button", { name: "Yes, restart" })); await waitFor(() => expect(posts(f, "/api/restart")).toEqual([{ slug: "song-001", step: "video" }]));
  });
});
