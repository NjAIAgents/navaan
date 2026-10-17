import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { LISTENER, OWNER } from "../components/Shell.test";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json", "X-Request-Id": "req-8" } });
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

const detail = (o: object = {}) => ({ slug: "song-001", steps: [], next: { type: "run", step: "lyrics" }, text: { "title.txt": "Tere" }, files: {}, meta: { type: "music", state: "drafted", history: [] }, approvals: {}, job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "", ...o });

describe("New song and New inspiration", () => {
  it("creates a song from an idea and opens it", async () => {
    const f = route(OWNER, { "/api/new": () => ({ rc: 0, slug: "song-007" }), "/api/songs": () => [], "/api/song/": () => detail({ slug: "song-007" }) });
    at("/studio/songs"); fireEvent.click(await screen.findByRole("button", { name: "New song" }));
    fireEvent.change(screen.getByLabelText("Idea (optional)"), { target: { value: "  a song about rain  " } }); fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(posts(f, "/api/new")).toEqual([{ type: "music", idea: "a song about rain" }]));
    await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/song/song-007")).toBe(true));   // it opened the new song
  });
  it("needs a quote for an inspiration and shows the server's refusal", async () => {
    const f = route(OWNER, { "/api/new": () => json({ error: "the inspiration pipeline is planned" }, 400), "/api/songs": () => [] });
    at("/studio/inspiration"); fireEvent.click(await screen.findByRole("button", { name: "New inspiration" }));
    fireEvent.click(screen.getByRole("button", { name: "Create" })); expect(await screen.findByRole("alert")).toHaveTextContent("Write the quote or the idea first."); expect(posts(f, "/api/new")).toHaveLength(0);
    fireEvent.change(screen.getByLabelText("Quote or idea"), { target: { value: "Maybe you are not behind" } }); fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByText(/inspiration pipeline is planned \(ref req-8\)/)).toBeInTheDocument(); expect(posts(f, "/api/new")[0]).toEqual({ type: "inspiration", idea: "Maybe you are not behind", narrate: "eleven", voice: "suno1" });   // narration is a standard step: on unless unticked
  });
  it("imports from a Suno link, with an MP3 as well, and refuses an empty or too big import", async () => {
    const f = route(OWNER, { "/api/import": () => ({ slug: "song-008", started: true }), "/api/songs": () => [], "/api/song/": () => detail({ slug: "song-008" }) });
    at("/studio/songs"); fireEvent.click(await screen.findByRole("button", { name: "New song" })); fireEvent.click(screen.getByRole("button", { name: "Import from Suno" }));
    fireEvent.click(screen.getByRole("button", { name: "Import" })); expect(await screen.findByRole("alert")).toHaveTextContent("Give the Suno link, an MP3, or both.");
    const big = new File([new Uint8Array(1)], "big.mp3", { type: "audio/mpeg" }); Object.defineProperty(big, "size", { value: 23 * 1024 * 1024 });
    fireEvent.change(screen.getByLabelText(/MP3 file/), { target: { files: [big] } }); fireEvent.click(screen.getByRole("button", { name: "Import" })); expect(await screen.findByRole("alert")).toHaveTextContent("over 22 MB"); expect(posts(f, "/api/import")).toHaveLength(0);
    fireEvent.change(screen.getByLabelText(/MP3 file/), { target: { files: [new File(["abc"], "song.mp3", { type: "audio/mpeg" })] } }); fireEvent.change(screen.getByLabelText("Suno link"), { target: { value: "https://suno.com/song/abc" } }); fireEvent.click(screen.getByRole("button", { name: "Import" }));
    await waitFor(() => expect(posts(f, "/api/import")).toHaveLength(1)); const b = posts(f, "/api/import")[0]; expect(b.url).toBe("https://suno.com/song/abc"); expect(b.audio).toEqual({ name: "song.mp3", data: "YWJj" });
  });
  it("is not offered to a listener", async () => { route(LISTENER, { "/api/catalog/tracks": () => [] }); at("/"); await screen.findByRole("heading", { name: "Browse", level: 1 }); expect(screen.queryByRole("button", { name: "New song" })).toBeNull(); });
});

describe("answering the agent, uploading Suno's MP3, revoking an approval", () => {
  const q = { id: "q1", text: "Which cover do you want?", allow_text: false, options: [{ id: "a", label: "Option A", text: false }, { id: "file", label: "Use my file", text: true }] };
  it("answers a question with a button, and asks for the text before an answer that needs it", async () => {
    const f = route(OWNER, { "/api/answer": () => ({ ok: true }), "/api/song/": () => detail({ question: q }) });
    at("/studio/songs/song-001"); expect(await screen.findByRole("heading", { name: "The agent is asking you" })).toBeInTheDocument(); expect(screen.getByText("Which cover do you want?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Use my file" })); expect(await screen.findByRole("alert")).toHaveTextContent("Type the answer in the box first."); expect(posts(f, "/api/answer")).toHaveLength(0);
    fireEvent.change(screen.getByLabelText("Your answer"), { target: { value: "cover.png" } }); fireEvent.click(screen.getByRole("button", { name: "Use my file" }));
    await waitFor(() => expect(posts(f, "/api/answer")).toEqual([{ slug: "song-001", choice: "file", text: "cover.png" }]));
    fireEvent.click(screen.getByRole("button", { name: "Option A" })); await waitFor(() => expect(posts(f, "/api/answer")).toHaveLength(2)); expect(posts(f, "/api/answer")[1]).toMatchObject({ choice: "a" });
  });
  it("answers a free-text question", async () => {
    const f = route(OWNER, { "/api/answer": () => ({ ok: true }), "/api/song/": () => detail({ question: { id: "q2", text: "What is the mood?", allow_text: true, options: [] } }) });
    at("/studio/songs/song-001"); fireEvent.click(await screen.findByRole("button", { name: "Send answer" })); expect(await screen.findByRole("alert")).toHaveTextContent("Type the answer");
    fireEvent.change(screen.getByLabelText("Your answer"), { target: { value: "warm" } }); fireEvent.click(screen.getByRole("button", { name: "Send answer" })); await waitFor(() => expect(posts(f, "/api/answer")).toEqual([{ slug: "song-001", choice: null, text: "warm" }]));
  });
  it("offers the MP3 upload only for a Suno import that has no audio", async () => {
    const failed = { source: "suno_import", suno: { auto_failed: "403 from the audio host" }, type: "music", state: "drafted", history: [] };
    const f = route(OWNER, { "/api/suno/audio": () => ({ ok: true, started: true }), "/api/song/": () => detail({ meta: failed }) });
    at("/studio/songs/song-001"); const inp = await screen.findByLabelText(/MP3 file/); expect(screen.getByText("403 from the audio host")).toBeInTheDocument();
    fireEvent.change(inp, { target: { files: [new File(["abc"], "x.mp3", { type: "audio/mpeg" })] } }); await waitFor(() => expect(posts(f, "/api/suno/audio")).toEqual([{ slug: "song-001", name: "x.mp3", data: "YWJj" }]));
    cleanup(); route(OWNER, { "/api/song/": () => detail({ meta: failed, files: { "final.mp3": 5 } }) }); at("/studio/songs/song-001"); await screen.findByRole("heading", { level: 1 }); expect(screen.queryByLabelText(/MP3 file/)).toBeNull();   // the audio is there
  });
  it("lists what is approved and revokes one only after a confirmation", async () => {
    const f = route(OWNER, { "/api/revoke": () => ({ ok: true }), "/api/song/": () => detail({ approvals: { lyrics: { at: "2026-10-16T01:00:00Z", via: "ui:meera" } } }) });
    at("/studio/songs/song-001?tab=activity"); const item = (await screen.findByText("Lyrics", { selector: "b" })).closest("li")!; expect(item).toHaveTextContent("meera");
    fireEvent.click(screen.getByRole("button", { name: "Revoke approval of Lyrics" })); expect(posts(f, "/api/revoke")).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Yes, revoke" })); await waitFor(() => expect(posts(f, "/api/revoke")).toEqual([{ slug: "song-001", gate: "lyrics" }]));
  });
});

describe("accessibility", () => {
  it("has no serious violations with the New panel open, a question, and approvals", async () => {
    const q = { id: "q1", text: "Which cover?", allow_text: true, options: [{ id: "a", label: "Option A", text: false }] };
    for (const [path, open] of [["/studio/songs", true], ["/studio/inspiration", true], ["/studio/songs/song-001", false]] as const) {
      cleanup(); route(OWNER, { "/api/songs": () => [], "/api/song/": () => detail({ question: q, approvals: { lyrics: { at: "2026-10-16T01:00:00Z", via: "ui:meera" } }, meta: { source: "suno_import", suno: { auto_failed: "x" }, type: "music", state: "drafted", history: [] } }) });
      at(path); await screen.findAllByRole("heading", { level: 1 }); await waitFor(() => expect(screen.queryByText("Loading…")).toBeNull()); await new Promise((r) => setTimeout(r, 30));
      if (open) { fireEvent.click(await screen.findByRole("button", { name: /^New / })); await screen.findByRole("heading", { name: /^New / }); }
      const r = await axe.run(document.body, { rules: { "color-contrast": { enabled: false } } });
      expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${path} ${v.id}: ${v.nodes[0]?.html.slice(0, 140)}`)).toEqual([]);
    }
  });
});

describe("narration offered for an inspiration", () => {
  const SET = (key: boolean) => ({ media: { keys: { elevenlabs: key, openai: true }, voices: { frank: "Frank (deep, wise)", nj: "NJ (my own voice)" }, settings: { voice: "frank" }, choices: {}, usage: {} } });
  it("is on by default, with the voice to pick, and is sent with the new inspiration", async () => {
    const f = route(OWNER, { "/api/new": () => ({ rc: 0, slug: "insp-005" }), "/api/songs": () => [], "/api/settings": () => SET(true), "/api/song/": () => detail({ slug: "insp-005" }) });
    at("/studio/inspiration"); fireEvent.click(await screen.findByRole("button", { name: "New inspiration" }));
    const box = await screen.findByLabelText(/Narrate the quote with ElevenLabs/); expect(box).toBeChecked(); expect(box).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Voice"), { target: { value: "nj" } });
    fireEvent.change(screen.getByLabelText("Quote or idea"), { target: { value: "You are allowed to outgrow your old life." } }); fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(posts(f, "/api/new")).toEqual([{ type: "inspiration", idea: "You are allowed to outgrow your old life.", narrate: "eleven", voice: "nj" }]));
  });
  it("stays a standard step without a key, says the key is needed before it runs, and can be unticked for a music and text only short", async () => {
    const f = route(OWNER, { "/api/new": () => ({ rc: 0, slug: "insp-005" }), "/api/songs": () => [], "/api/settings": () => SET(false), "/api/song/": () => detail({ slug: "insp-005" }) });
    at("/studio/inspiration"); fireEvent.click(await screen.findByRole("button", { name: "New inspiration" }));
    const box = await screen.findByLabelText(/Narrate the quote with ElevenLabs/); expect(box).toBeChecked(); expect(await screen.findByText(/Paste an ElevenLabs key in Settings before this step runs/)).toBeInTheDocument();
    fireEvent.click(box); expect(box).not.toBeChecked();
    fireEvent.change(screen.getByLabelText("Quote or idea"), { target: { value: "Stay soft." } }); fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(posts(f, "/api/new")).toEqual([{ type: "inspiration", idea: "Stay soft.", narrate: "none" }]));
  });
  it("is mentioned on the quote and the video approvals when the short has no voice", async () => {
    route(OWNER, { "/api/song/": () => detail({ slug: "insp-004", next: { type: "gate", step: "render", gate: "media" }, meta: { type: "inspiration", state: "quote_ok", history: [] }, narrate: { on: false, voice: "frank", voices: {}, estimate_s: 12, used_s: 0, cap_s: 1500, key: true } }) });
    at("/studio/inspiration/insp-004");
    expect(await screen.findByText(/no narration on this short, so the video has music and text only/)).toBeInTheDocument();
  });
});

describe("an approval a running job is waiting for", () => {
  it("is shown with an Approve button that works, not hidden behind Running (inspiration insp-004: the job waits for the media gate)", async () => {
    const waiting = detail({ slug: "insp-004", next: { type: "gate", step: "render", gate: "media" }, meta: { type: "inspiration", state: "quote_ok", history: [] }, job: { running: true, queued: false, rc: null }, status_text: "waiting for you: approve gate media", files: { "final_reel_9x16.mp4": 1000 } });
    const f = route(OWNER, { "/api/approve": () => ({ ok: true }), "/api/song/": () => waiting });
    at("/studio/inspiration/insp-004");
    expect(await screen.findByRole("heading", { name: "Review the videos" })).toBeInTheDocument(); expect(screen.getByText("Waiting for you")).toBeInTheDocument(); expect(screen.queryByText("Running")).toBeNull();
    const ok = screen.getByRole("button", { name: "Approve" }); expect(ok).toBeEnabled(); fireEvent.click(ok);
    await waitFor(() => expect(posts(f, "/api/approve")).toEqual([{ slug: "insp-004", gate: "media" }]));
  });
  it("a run stopped by a restart has no failed step: its button runs the next step again instead of being switched off", async () => {
    const f = route(OWNER, { "/api/run": () => ({ started: true }), "/api/song/": () => detail({ slug: "insp-004", next: { type: "run", step: "narrate" }, meta: { type: "inspiration", state: "quote_ok", history: [] }, failure: { step: "", error: "the worker stopped before the job finished", ref: "job-1" } }) });
    at("/studio/inspiration/insp-004");
    const b = await screen.findByRole("button", { name: /Run again: Narrate the quote/ }); expect(b).toBeEnabled(); fireEvent.click(b);
    await waitFor(() => expect(posts(f, "/api/run")).toEqual([{ slug: "insp-004", all: true }]));
  });
  it("also offers to stop the waiting run, so something earlier can be changed", async () => {
    const f = route(OWNER, { "/api/stop": () => ({ stopped: true }), "/api/song/": () => detail({ slug: "insp-004", next: { type: "gate", step: "render", gate: "media" }, meta: { type: "inspiration", state: "quote_ok", history: [] }, job: { running: true, queued: false, rc: null }, status_text: "waiting for you: approve gate media" }) });
    at("/studio/inspiration/insp-004");
    expect(await screen.findByText(/A run is waiting for this approval/)).toBeInTheDocument(); fireEvent.click(screen.getByRole("button", { name: "Stop the run" }));
    await waitFor(() => expect(posts(f, "/api/stop")).toEqual([{ slug: "insp-004" }]));
    expect(await screen.findByRole("button", { name: "Stopping…" })).toBeDisabled();   // the worker takes a few seconds to act: say so, so it is not clicked again
  });
  it("still shows Running with Stop while a step really runs (no approval is next)", async () => {
    route(OWNER, { "/api/song/": () => detail({ slug: "insp-004", next: { type: "run", step: "render" }, meta: { type: "inspiration", state: "quote_ok", history: [] }, job: { running: true, queued: false, rc: null }, status_text: "running render" }) });
    at("/studio/inspiration/insp-004");
    expect(await screen.findByText("Running")).toBeInTheDocument(); expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument(); expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });
});

describe("the pipeline page: one thing that needs you, honest words, sections in tabs", () => {
  const step = (id: string, o: object = {}) => ({ id, label: id, kind: "script", done: false, redo: true, restart: false, spends: false, status: "ready", needs_gate: null, scheduled_for: null, ...o });
  it("lists the steps top to bottom with their state, and shows only the Pipeline section by default", async () => {
    route(OWNER, { "/api/song/": () => detail({ slug: "insp-004", meta: { type: "inspiration", state: "quote_ok", history: [] }, next: { type: "run", step: "narrate" }, steps: [step("quote", { done: true, status: "done" }), step("narrate"), step("render")] }) });
    at("/studio/inspiration/insp-004");
    expect(await screen.findByRole("heading", { name: "Next: Narrate the quote (ElevenLabs)" })).toBeInTheDocument();
    const rows = screen.getAllByRole("listitem").filter((li) => li.id.startsWith("step-")); expect(rows.map((r) => r.id)).toEqual(["step-quote", "step-narrate", "step-render"]);   // in order, each with the anchor
    expect(rows[0]).toHaveTextContent("done: Write the quote"); expect(rows[1]).toHaveAttribute("aria-current", "step"); expect(rows[2]).toHaveTextContent("later: Render the video");
    expect(screen.getByRole("tab", { name: "Pipeline" })).toHaveAttribute("aria-selected", "true"); expect(screen.queryByRole("heading", { name: "Narration" })).toBeNull();   // the editors are under Content
    fireEvent.click(screen.getByRole("tab", { name: "Content" })); expect(await screen.findByRole("heading", { name: "Narration" })).toBeInTheDocument();
  });
  it("says exactly what the credits approval spends, from the item's own steps, and never Suno for an inspiration", async () => {
    route(OWNER, { "/api/song/": () => detail({ slug: "insp-004", meta: { type: "inspiration", state: "quote_ok", history: [] }, next: { type: "gate", step: "background", gate: "credits" },
      steps: [step("background", { spends: true, spends_what: "OpenAI: the background picture" }), step("narrate", { spends: true, spends_what: "ElevenLabs: the voice of the quote (counts against your monthly seconds)" }), step("render")] }) });
    at("/studio/inspiration/insp-004");
    expect(await screen.findByText("OpenAI: the background picture")).toBeInTheDocument(); expect(screen.getByText(/ElevenLabs: the voice of the quote/)).toBeInTheDocument();
    expect(screen.queryByText(/Suno/)).toBeNull(); expect(screen.getByText(/Nothing is running: it is paused here/)).toBeInTheDocument();
  });
  it("shows a failure in plain words first, the raw error folded away, and only that one card", async () => {
    route(OWNER, { "/api/song/": () => detail({ slug: "insp-004", meta: { type: "inspiration", state: "quote_ok", history: [] }, next: { type: "run", step: "render" }, steps: [step("render")], failure: { step: "render", error: "FileNotFoundError: scenes/bg.png", ref: "job-9", plain: "A file this step needs is missing (bg.png). Making the step before it again usually fixes this." } }) });
    at("/studio/inspiration/insp-004");
    expect(await screen.findByText(/A file this step needs is missing \(bg.png\)/)).toBeInTheDocument();
    expect(screen.getByText("The raw error, for the log").closest("details")).not.toHaveAttribute("open"); expect(screen.queryByRole("heading", { name: /^Next:/ })).toBeNull();   // one card, not a failure and a next-step card
  });
  it("marks the Pipeline tab when something needs you and keeps the tab in the address", async () => {
    route(OWNER, { "/api/song/": () => detail({ slug: "insp-004", meta: { type: "inspiration", state: "quote_ok", history: [] }, next: { type: "gate", step: "render", gate: "media" } }) });
    at("/studio/inspiration/insp-004");
    const tab = await screen.findByRole("tab", { name: /Pipeline/ }); expect(tab).toContainElement(screen.getByRole("img", { name: "needs you" }));
    fireEvent.click(screen.getByRole("tab", { name: "Activity" })); expect(screen.getByRole("tab", { name: "Activity" })).toHaveAttribute("aria-selected", "true"); expect(screen.getByRole("heading", { name: "History" })).toBeInTheDocument();
  });
});

describe("what an approval asks you to review is on the approval", () => {
  it("shows the videos on the 'Review the videos' card, not a tab away, and the song on 'Listen'", async () => {
    route(OWNER, { "/api/song/": () => detail({ slug: "insp-004", meta: { type: "inspiration", state: "media_ready", history: [] }, next: { type: "gate", step: "render", gate: "media" }, files: { "final_reel_9x16.mp4": 5916178, "clips~a.mp4": 10, "voiceover.mp3": 99 } }) });
    at("/studio/inspiration/insp-004");
    const v = await screen.findByLabelText("final_reel_9x16.mp4"); expect(v.tagName).toBe("VIDEO"); expect(v).toHaveAttribute("src", "/media/insp-004/final_reel_9x16.mp4?v=5916178");   // the size stops an old cached video from playing
    expect(screen.queryByLabelText("clips~a.mp4")).toBeNull(); expect(screen.queryByLabelText("voiceover.mp3")).toBeNull();
    cleanup(); route(OWNER, { "/api/song/": () => detail({ next: { type: "gate", step: "suno", gate: "listen" }, files: { "final.mp3": 4000, "final_16x9.mp4": 7 } }) });
    at("/studio/songs/song-001");
    const a = await screen.findByLabelText("final.mp3"); expect(a.tagName).toBe("AUDIO"); expect(a).toHaveAttribute("src", "/media/song-001/final.mp3?v=4000"); expect(screen.queryByLabelText("final_16x9.mp4")).toBeNull();   // listening needs the song, not the video
  });
});

describe("opening a step from the pipeline", () => {
  it("shows the opened step's detail in place of what needs you, keeps it in the address, and goes back", async () => {
    const step = (id: string, o: object = {}) => ({ id, label: id, kind: "script", done: false, redo: true, restart: false, spends: false, status: "ready", needs_gate: null, scheduled_for: null, made: [], texts: [], ...o });
    route(OWNER, { "/api/song/": () => detail({ slug: "insp-004", meta: { type: "inspiration", state: "quote_ok", history: ["2026-10-17T05:56:08Z step background_prompt done (attempt 1)"] }, next: { type: "gate", step: "render", gate: "media" },
      steps: [step("background_prompt", { done: true, status: "done", texts: [{ name: "scenes/background.txt", text: "A quiet harbour at dusk." }] }), step("render", { done: true, status: "waiting for approval", needs_gate: "media" })] }) });
    at("/studio/inspiration/insp-004");
    expect(await screen.findByRole("heading", { name: "Review the videos" })).toBeInTheDocument();   // what needs you first
    fireEvent.click(screen.getByRole("button", { name: /done: Write the background prompt/ }));
    expect(await screen.findByLabelText("scenes/background.txt")).toHaveTextContent("A quiet harbour at dusk."); expect(screen.queryByRole("heading", { name: "Review the videos" })).toBeNull();
    expect(screen.getByText(/step background_prompt done \(attempt 1\)/)).toBeInTheDocument();   // its own history
    fireEvent.click(screen.getByRole("button", { name: /Back to what needs you/ })); expect(await screen.findByRole("heading", { name: "Review the videos" })).toBeInTheDocument();
  });
});

describe("the shot list approval", () => {
  it("shows the pictures of the shots, with the raw list folded away, and the steps by their real names", async () => {
    const shots = JSON.stringify({ shots: [{ id: 1, label: "Instrumental 1", start: 0, end: 17.15, image: "images/pic_01.png", camera: "push_in", scene: "A late-night cafe." }] });
    const step = (id: string, o: object = {}) => ({ id, label: id, kind: "script", done: false, redo: true, restart: false, spends: false, status: "ready", needs_gate: null, scheduled_for: null, made: [], texts: [], ...o });
    route(OWNER, { "/api/song/": () => detail({ next: { type: "gate", step: "shots", gate: "shots" }, text: { "title.txt": "Tere", "shots.json": shots }, steps: [step("prompts", { done: true, status: "done" }), step("pictures", { done: true, status: "done" }), step("shots", { done: true, status: "waiting for approval", needs_gate: "shots" }), step("motion_plan")] }) });
    at("/studio/songs/song-001");
    expect(await screen.findByAltText("Picture for Instrumental 1")).toHaveAttribute("src", "/media/song-001/images~pic_01.png");
    expect(screen.getByText("The raw shot list").closest("details")).not.toHaveAttribute("open");
    for (const name of [/: Write the picture plan$/, /: Create the pictures$/, /: Plan the shots$/, /: Plan what moves$/]) expect(screen.getByRole("button", { name })).toBeInTheDocument();   // not "prompts", "pictures", "shots", "motion plan"
  });
});

describe("a song with no lyrics", () => {
  it("says so before anything is run, with a way to the Content tab", async () => {
    route(OWNER, { "/api/song/": () => detail({ notes: ["This song has no lyrics saved. The picture plan and the captions are written from them. Add the lyrics on the Content tab."], next: { type: "run", step: "prompts" } }) });
    at("/studio/songs/song-001");
    const note = await screen.findByRole("note"); expect(note).toHaveTextContent("This song has no lyrics saved");
    fireEvent.click(screen.getByRole("button", { name: "Open Content" })); expect(screen.getByRole("tab", { name: "Content" })).toHaveAttribute("aria-selected", "true"); expect(screen.queryByRole("note")).toBeNull();   // the notice belongs to the Pipeline tab
  });
});
