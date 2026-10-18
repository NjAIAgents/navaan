import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
    fireEvent.click(screen.getByRole("button", { name: "Create" })); expect(await screen.findByRole("alert")).toHaveTextContent("Write the quote or the idea first, or paste a Suno link."); expect(posts(f, "/api/new")).toHaveLength(0);
    fireEvent.change(screen.getByLabelText("Quote or idea"), { target: { value: "Maybe you are not behind" } }); fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByText(/inspiration pipeline is planned \(ref req-8\)/)).toBeInTheDocument(); expect(posts(f, "/api/new")[0]).toEqual({ type: "inspiration", idea: "Maybe you are not behind", narrate: "eleven", voice: "suno1" });   // narration is a standard step: on unless unticked
  });
  it("asks when to publish at the first step, for a song and an inspiration: when the pipeline finishes by default, or a date and time in Central Time", async () => {
    const f = route(OWNER, { "/api/import": () => ({ slug: "song-008", started: true }), "/api/new": () => ({ slug: "insp-009" }), "/api/songs": () => [], "/api/inspirations": () => [], "/api/song/": () => detail({ slug: "song-008" }), "/api/settings": () => ({}) });
    at("/studio/songs"); fireEvent.click(await screen.findByRole("button", { name: "New song" })); fireEvent.click(screen.getByRole("button", { name: "Import from Suno" }));
    expect(screen.getByRole("radio", { name: /When the pipeline finishes/ })).toBeChecked(); expect(screen.queryByLabelText(/Central Time/)).toBeNull();
    fireEvent.change(screen.getByLabelText(/Suno link/), { target: { value: "https://suno.com/s/1K4BKj0pldFbnlkF" } });
    fireEvent.click(screen.getByRole("radio", { name: /On a date and time/ })); fireEvent.click(screen.getByRole("button", { name: "Import" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Pick the date and time to publish"); expect(posts(f, "/api/import")).toHaveLength(0);
    fireEvent.change(screen.getByLabelText(/Central Time/), { target: { value: "2030-12-01T18:30" } }); fireEvent.click(screen.getByRole("button", { name: "Import" }));
    await waitFor(() => expect(posts(f, "/api/import")).toEqual([{ url: "https://suno.com/s/1K4BKj0pldFbnlkF", publish_at_ct: "2030-12-01T18:30" }]));
    cleanup(); at("/studio/inspiration"); fireEvent.click(await screen.findByRole("button", { name: "New inspiration" }));
    fireEvent.change(screen.getByLabelText(/Quote or idea/), { target: { value: "Hope" } }); fireEvent.click(screen.getByRole("radio", { name: /On a date and time/ }));
    fireEvent.change(screen.getByLabelText(/Central Time/), { target: { value: "2030-12-02T09:00" } }); fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(posts(f, "/api/new")[0]).toMatchObject({ type: "inspiration", publish_at_ct: "2030-12-02T09:00" }));
  });
  it("has The Aha-lorithm as its own list, starting a short from an idea or from nothing, never a Suno link (NAV-67)", async () => {
    const f = route(OWNER, { "/api/new": () => ({ slug: "aha-001" }), "/api/songs": () => [{ slug: "aha-001", type: "aha", title: "AI knows your weekday", state: "draft", status: "production", steps_done: 2, steps_total: 13, public: false, published: false, scheduled: "", album: "" }, { slug: "insp-004", type: "inspiration", title: "Tired", state: "published", status: "done", steps_done: 14, steps_total: 14, public: true, published: true, scheduled: "", album: "" }], "/api/song/": () => detail({ slug: "aha-001", meta: { type: "aha", state: "draft", history: [] } }), "/api/settings": () => ({}) });
    at("/studio/aha");
    expect(await screen.findByRole("heading", { name: "The Aha-lorithm", level: 1 })).toBeInTheDocument();
    expect(await screen.findByText("AI knows your weekday")).toBeInTheDocument(); expect(screen.queryByText("Tired")).toBeNull();   // only its own items
    fireEvent.click(screen.getByRole("button", { name: "New Aha-lorithm short" }));
    expect(screen.queryByLabelText(/Suno link/)).toBeNull();   // the narration is ElevenLabs reading the script
    fireEvent.click(screen.getByRole("button", { name: "Create" }));   // an empty idea is allowed: Claude picks the topic
    await waitFor(() => expect(posts(f, "/api/new")[0]).toMatchObject({ type: "aha", idea: "" })); expect(posts(f, "/api/new")[0]).not.toHaveProperty("suno_url");
    expect(await screen.findByRole("link", { name: "The Aha-lorithm" })).toHaveAttribute("href", "/studio/aha");   // the back link from the new short names the channel list
  });
  it("needs the Suno link, takes the sound from the Suno page unless an audio file is added, and refuses a too big file", async () => {
    const f = route(OWNER, { "/api/import": () => ({ slug: "song-008", started: true }), "/api/songs": () => [], "/api/song/": () => detail({ slug: "song-008" }) });
    at("/studio/songs"); fireEvent.click(await screen.findByRole("button", { name: "New song" })); fireEvent.click(screen.getByRole("button", { name: "Import from Suno" }));
    expect(screen.getByLabelText(/Suno link \(required\)/)).toBeRequired(); expect(screen.getByLabelText(/Audio file \(optional/)).not.toBeRequired();   // the file is optional now
    fireEvent.click(screen.getByRole("button", { name: "Import" })); expect(await screen.findByRole("alert")).toHaveTextContent("Add the Suno link: the title, lyrics and style are read from it.");
    fireEvent.change(screen.getByLabelText(/Suno link/), { target: { value: "https://suno.com/s/1K4BKj0pldFbnlkF" } });   // the link alone is enough: the sound comes from the Suno page
    fireEvent.click(screen.getByRole("button", { name: "Import" })); await waitFor(() => expect(posts(f, "/api/import")).toHaveLength(1)); expect(posts(f, "/api/import")[0]).toEqual({ url: "https://suno.com/s/1K4BKj0pldFbnlkF" });   // no audio sent
    cleanup(); at("/studio/songs"); fireEvent.click(await screen.findByRole("button", { name: "New song" })); fireEvent.click(screen.getByRole("button", { name: "Import from Suno" })); fireEvent.change(screen.getByLabelText(/Suno link/), { target: { value: "https://suno.com/s/1K4BKj0pldFbnlkF" } });
    const big = new File([new Uint8Array(1)], "big.mp3", { type: "audio/mpeg" }); Object.defineProperty(big, "size", { value: 23 * 1024 * 1024 });
    fireEvent.change(screen.getByLabelText(/Audio file/), { target: { files: [big] } }); fireEvent.click(screen.getByRole("button", { name: "Import" })); expect(await screen.findByRole("alert")).toHaveTextContent("over 22 MB"); expect(posts(f, "/api/import")).toHaveLength(1);
    fireEvent.change(screen.getByLabelText(/Audio file/), { target: { files: [new File(["abc"], "song.mp3", { type: "audio/mpeg" })] } }); fireEvent.click(screen.getByRole("button", { name: "Import" }));
    await waitFor(() => expect(posts(f, "/api/import")).toHaveLength(2)); const b = posts(f, "/api/import")[1]; expect(b.url).toBe("https://suno.com/s/1K4BKj0pldFbnlkF"); expect(b.audio).toEqual({ name: "song.mp3", data: "YWJj" });
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
  it("takes the voice and words from a Suno link when one is pasted, with ElevenLabs kept as the backup", async () => {
    const f = route(OWNER, { "/api/new": () => ({ rc: 0, slug: "insp-006" }), "/api/songs": () => [], "/api/settings": () => SET(true), "/api/song/": () => detail({ slug: "insp-006" }) });
    at("/studio/inspiration"); fireEvent.click(await screen.findByRole("button", { name: "New inspiration" }));
    fireEvent.change(await screen.findByLabelText("Suno link (optional)"), { target: { value: "https://suno.com/s/hhExPklJS2a69Wv1" } });
    expect(screen.getByLabelText("Quote or idea")).toBeDisabled(); expect(screen.getByLabelText(/Keep ElevenLabs as the backup voice/)).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(posts(f, "/api/new")).toEqual([{ type: "inspiration", idea: "", narrate: "eleven", voice: "frank", suno_url: "https://suno.com/s/hhExPklJS2a69Wv1" }]));
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
    expect(await screen.findByRole("heading", { name: "Narrate the quote (ElevenLabs)" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^\d+ done/ }));   // finished steps are folded into one line
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
    const v = await screen.findByLabelText("Reel without lyrics"); expect(v.tagName).toBe("VIDEO"); expect(v).toHaveAttribute("src", "/media/insp-004/final_reel_9x16.mp4?v=5916178");   // the size stops an old cached video from playing
    expect(screen.queryByLabelText("clips~a.mp4")).toBeNull(); expect(screen.queryByLabelText("voiceover.mp3")).toBeNull();
    cleanup(); route(OWNER, { "/api/song/": () => detail({ next: { type: "gate", step: "suno", gate: "listen" }, files: { "final.mp3": 4000, "final_16x9.mp4": 7 } }) });
    at("/studio/songs/song-001");
    const a = await screen.findByLabelText("final.mp3"); expect(a.tagName).toBe("AUDIO"); expect(a).toHaveAttribute("src", "/media/song-001/final.mp3?v=4000"); expect(screen.queryByLabelText("final_16x9.mp4")).toBeNull();   // listening needs the song, not the video
  });
});

describe("opening a step from the pipeline", () => {
  it("shows the opened step's detail under what needs you, keeps it in the address, and closes", async () => {
    const step = (id: string, o: object = {}) => ({ id, label: id, kind: "script", done: false, redo: true, restart: false, spends: false, status: "ready", needs_gate: null, scheduled_for: null, made: [], texts: [], ...o });
    route(OWNER, { "/api/song/": () => detail({ slug: "insp-004", meta: { type: "inspiration", state: "quote_ok", history: ["2026-10-17T05:56:08Z step background_prompt done (attempt 1)"] }, next: { type: "gate", step: "render", gate: "media" },
      steps: [step("background_prompt", { done: true, status: "done", texts: [{ name: "scenes/background.txt", text: "A quiet harbour at dusk." }] }), step("render", { done: true, status: "waiting for approval", needs_gate: "media" })] }) });
    at("/studio/inspiration/insp-004");
    expect(await screen.findByRole("heading", { name: "Review the videos" })).toBeInTheDocument();   // what needs you first
    fireEvent.click(screen.getByRole("button", { name: /^\d+ done/ }));   // finished steps are folded into one line
    fireEvent.click(screen.getByRole("button", { name: /done: Write the background prompt/ }));
    expect(await screen.findByLabelText("scenes/background.txt")).toHaveTextContent("A quiet harbour at dusk."); expect(screen.getByRole("heading", { name: "Review the videos" })).toBeInTheDocument();   // what needs you stays in front while a step is open
    expect(screen.getByText(/step background_prompt done \(attempt 1\)/)).toBeInTheDocument();   // its own history
    fireEvent.click(screen.getByRole("button", { name: "Close this step" })); await waitFor(() => expect(screen.queryByLabelText("scenes/background.txt")).toBeNull()); expect(screen.getByRole("heading", { name: "Review the videos" })).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: /^\d+ done/ }));   // finished steps are folded into one line
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

describe("the live pipeline page: a running step, the videos, the gate switch and the picture plan", () => {
  const step = (id: string, o: object = {}) => ({ id, label: id, kind: "script", done: false, redo: true, restart: false, spends: false, status: "ready", needs_gate: null, scheduled_for: null, made: [], texts: [], ...o });
  const A = "/studio/songs/song-007";

  it("shows the step that is really running, with a moving state, a bar, how long it has run and when it last did anything, and the rail row spins", async () => {
    route(OWNER, { "/api/song/": () => detail({ slug: "song-007", next: { type: "run", step: "video" }, job: { running: true, queued: false, rc: null }, status_text: "running reel", meta: { type: "music", state: "drafted", history: [], step_seconds: { video: 540 } },
      run: { step: "video", attempt: 1, attempts: 3, elapsed: 151, quiet_s: 4, pct: 40, label: "joining the pictures" }, steps: [step("reel", { done: true, status: "done" }), step("video")] }) });
    at(A);
    expect(await screen.findByRole("heading", { name: "Build the video" })).toBeInTheDocument();   // from the run, not the status text that still says reel
    expect(screen.getByText("Running")).toBeInTheDocument(); expect(screen.getAllByRole("progressbar", { name: "joining the pictures" })[0]).toHaveAttribute("aria-valuenow", "40");   // one on the card, a thin one on the row
    expect(screen.getByText(/joining the pictures \(40%\) · running for 2 min 31 s · attempt 1 of 3 · last activity 4 s ago · usually about 9 min/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
    const row = document.getElementById("step-video") as HTMLElement; expect(row.className).toContain("run"); expect(row.querySelector(".spin")).not.toBeNull(); expect(row).toHaveTextContent("running for 2 min 31 s, 40%");
  });

  it("shows the videos side by side with their names, the approval above them, and the Instagram reel can go without lyrics", async () => {
    const f = route(OWNER, { "/api/reel/lyrics": () => ({ ok: true, on: false, offset: 0 }), "/api/song/": () => detail({ slug: "song-007", next: { type: "gate", step: "video", gate: "media" }, files: { "final_16x9.mp4": 10, "final_reel_9x16.mp4": 20, "final_reel_9x16_cap.mp4": 30 }, reel_lyrics: { on: true, offset: 0 },
      steps: [step("video", { done: true, status: "waiting for approval", needs_gate: "media" })] }) });
    at(A);
    const videos = await screen.findAllByLabelText(/^(Full video|Reel without lyrics|Reel with lyrics)$/); expect(videos.map((v) => v.getAttribute("aria-label"))).toEqual(["Full video", "Reel without lyrics", "Reel with lyrics"]);
    const approve = screen.getByRole("button", { name: "Approve" }); expect(approve.compareDocumentPosition(videos[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();   // the button is above the videos
    expect(screen.getByRole("radio", { name: "With lyrics" })).toBeChecked();
    fireEvent.click(screen.getByRole("radio", { name: /Without lyrics/ }));
    await waitFor(() => expect(posts(f, "/api/reel/lyrics")).toEqual([{ slug: "song-007", on: false }]));
  });

  it("asks which video the feedback is about, needs it before it can be sent, and sends the video and the nudge so only that one is made again", async () => {
    const f = route(OWNER, { "/api/request-changes": () => ({ ok: true, started: true }), "/api/song/": () => detail({ slug: "song-007", next: { type: "gate", step: "video", gate: "media" }, files: { "final_16x9.mp4": 10, "final_reel_9x16.mp4": 20, "final_reel_9x16_cap.mp4": 30 },
      steps: [step("video", { done: true, status: "waiting for approval", needs_gate: "media" })] }) });
    at(A);
    fireEvent.click(await screen.findByRole("button", { name: "Request changes" }));
    expect(screen.getByText("Which video is this about?")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("What should change?"), { target: { value: "The lyrics are late." } });
    const send = screen.getByRole("button", { name: "Send back and make that video again" }); expect(send).toBeDisabled();   // no video chosen yet
    fireEvent.click(screen.getByRole("radio", { name: "Reel with lyrics" })); expect(send).toBeEnabled();
    fireEvent.change(screen.getByLabelText(/Lyrics early or late/), { target: { value: "-1.5" } });
    fireEvent.click(send);
    await waitFor(() => expect(posts(f, "/api/request-changes")).toEqual([{ slug: "song-007", gate: "media", note: "The lyrics are late.", video: "reel_lyrics", offset: -1.5 }]));
  });

  it("puts the approval switch on the step: a risky one asks first and applies to every song, and the switch is read back from the server", async () => {
    const f = route(OWNER, { "/api/settings/gates_save": () => ({ gates: [] }), "/api/song/": () => detail({ slug: "song-007", next: { type: "run", step: "youtube_meta" }, gates_off: ["instagram_caption"], steps: [step("youtube_meta", { done: true, status: "done" }), step("publish_youtube", { gate_before: "publish_youtube" }), step("instagram_caption", { gate_after: "instagram_caption" })] }) });
    at(`${A}?step=instagram_caption`);   // the switches are on the opened step, not on every row of the list
    expect(await screen.findByRole("switch", { name: /Ask me after it runs/ })).not.toBeChecked();   // switched off in Settings
    cleanup(); route(OWNER, { "/api/settings/gates_save": () => ({ gates: [] }), "/api/song/": () => detail({ slug: "song-007", next: { type: "run", step: "youtube_meta" }, gates_off: ["instagram_caption"], steps: [step("youtube_meta", { done: true, status: "done" }), step("publish_youtube", { gate_before: "publish_youtube" }), step("instagram_caption", { gate_after: "instagram_caption" })] }) });
    at(`${A}?step=publish_youtube`);
    const yt = await screen.findByRole("switch", { name: /Ask me before it runs/ }); expect(yt).toBeChecked();
    const saves = () => (vi.mocked(fetch).mock.calls as unknown as [string, RequestInit?][]).filter(([u]) => u === "/api/settings/gates_save").map(([, i]) => JSON.parse(String(i?.body)));
    fireEvent.click(yt); expect(await screen.findByRole("alertdialog", { name: /Confirm switching off/ })).toHaveTextContent("for every song");
    fireEvent.click(screen.getByRole("button", { name: "Keep asking me" })); expect(saves()).toEqual([]);
    fireEvent.click(yt); fireEvent.click(await screen.findByRole("button", { name: "Yes, approve it automatically" }));
    await waitFor(() => expect(saves()).toEqual([{ gates: { publish_youtube: false } }])); void f;
  });

  it("lets the picture plan be edited on its step and sends only what changed in words", async () => {
    const pk = { concept: "A quiet ache.", character: "A woman.", style_line: "Rain.", prompts: [{ n: 1, section: "Verse", lyric: "line", prompt: "First picture." }, { n: 2, section: "Chorus", prompt: "Second picture." }] };
    const f = route(OWNER, { "/api/plan/save": () => ({ ok: true }), "/api/song/": () => detail({ slug: "song-007", next: { type: "run", step: "pictures" }, prompt_pack: pk, images: [], steps: [step("prompts", { done: true, status: "done", texts: [{ name: "prompt_pack.json", text: "{}" }] }), step("pictures")] }) });
    at(`${A}?step=prompts`);
    const save = await screen.findByRole("button", { name: "Save the plan" }); expect(save).toBeDisabled();   // nothing changed
    fireEvent.change(screen.getByLabelText("The character"), { target: { value: "A lone man seen from behind." } });
    fireEvent.change(screen.getByLabelText("Prompt for picture 2"), { target: { value: "The same street, empty." } });
    expect(save).toBeEnabled(); fireEvent.click(save);
    await waitFor(() => expect(posts(f, "/api/plan/save")).toEqual([{ slug: "song-007", concept: "A quiet ache.", character: "A lone man seen from behind.", style_line: "Rain.", prompts: [{ n: 1, prompt: "First picture." }, { n: 2, prompt: "The same street, empty." }] }]));
    expect(await screen.findByText(/Pictures already made keep their old prompt/)).toBeInTheDocument();
  });
  it("answers every click in words: what is being done, what was done, and when nothing started", async () => {
    let started = true;
    const f = route(OWNER, { "/api/approve": () => ({ ok: true, started: false }), "/api/redo": () => ({ started }), "/api/stop": () => ({ stopped: true }),
      "/api/song/": () => detail({ slug: "song-007", next: { type: "gate", step: "video", gate: "media" }, steps: [step("captions", { done: true, status: "done" }), step("video", { done: true, status: "waiting for approval", needs_gate: "media" })] }) });
    at(`${A}?step=captions`);   // Redo is on the opened step
    fireEvent.click(await screen.findByRole("button", { name: "Redo Sync the captions" })); fireEvent.click(screen.getByRole("button", { name: "Yes, redo it" }));
    expect(await screen.findByText("Redo started: Sync the captions.")).toBeInTheDocument(); expect(posts(f, "/api/redo")).toEqual([{ slug: "song-007", step: "captions" }]);
    started = false; fireEvent.click(screen.getByRole("button", { name: "Redo Sync the captions" })); fireEvent.click(screen.getByRole("button", { name: "Yes, redo it" }));
    expect(await screen.findByText(/Nothing started: a run is already going/)).toBeInTheDocument();   // it does not claim a redo that did not start
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByText("Approved: Review the videos.")).toBeInTheDocument();
  });

  it("says Stop was asked for, and shows where a publish step put it as that stage's output", async () => {
    const f = route(OWNER, { "/api/stop": () => ({ stopped: true }), "/api/song/": () => detail({ slug: "song-007", next: { type: "run", step: "go_public" }, job: { running: true, queued: false, rc: null }, run: { step: "go_public", elapsed: 3 },
      steps: [step("publish_youtube", { done: true, status: "done", made: [{ name: "published.json", size: 120 }], links: [{ where: "YouTube video", url: "https://youtu.be/abc123", privacy: "private" }] }), step("go_public")] }) });
    at(`${A}?step=publish_youtube`);
    expect(await screen.findByRole("heading", { name: "Published" })).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "https://youtu.be/abc123" }); expect(link).toHaveAttribute("href", "https://youtu.be/abc123"); expect(screen.getByText(/YouTube video/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "published.json" })).toBeInTheDocument();   // and the file the stage made
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    expect(await screen.findByText("Stop requested. The step ends in a moment.")).toBeInTheDocument(); expect(posts(f, "/api/stop")).toEqual([{ slug: "song-007" }]);
  });
  it("shows YouTube and Instagram as two lanes once the videos are approved, each with its own approval or Run button, and runs just that lane's step", async () => {
    const f = route(OWNER, { "/api/run": () => ({ started: true }), "/api/song/": () => detail({ slug: "song-007", next: { type: "run", step: "instagram_caption" },
      lanes: { youtube: { type: "gate", step: "publish_youtube", gate: "publish_youtube" }, instagram: { type: "run", step: "instagram_caption" } },
      steps: [step("video", { done: true, status: "done" }), step("youtube_meta", { done: true, status: "done", lane: "youtube" }), step("publish_youtube", { status: "waiting for approval", needs_gate: "publish_youtube", gate_before: "publish_youtube", lane: "youtube" }),
              step("instagram_caption", { lane: "instagram" }), step("publish_instagram", { lane: "instagram", gate_before: "publish_instagram" })] }) });
    at(A);
    const yt = await screen.findByRole("region", { name: "YouTube" }); const ig = screen.getByRole("region", { name: "Instagram" });
    expect(yt).toHaveTextContent("Upload the video to YouTube (private)"); expect(yt.querySelector("button")).not.toBeNull();   // its own approval
    expect(ig).toHaveTextContent("Write the Instagram caption"); expect(ig).toHaveTextContent("Only this lane moves");
    expect(document.getElementById("step-publish_youtube")).toHaveTextContent("YouTube lane"); expect(document.getElementById("step-instagram_caption")).toHaveTextContent("Instagram lane");
    fireEvent.click(screen.getByRole("button", { name: "Run Write the Instagram caption" }));
    await waitFor(() => expect(posts(f, "/api/run")).toEqual([{ slug: "song-007", step: "instagram_caption" }]));   // only that lane's step
  });
  it("lets you skip Instagram for one song so the pipeline finishes without it, and turn it back on", async () => {
    const f = route(OWNER, { "/api/skip_lane": () => ({ ok: true }), "/api/song/": () => detail({ slug: "song-008", next: { type: "run", step: "publish_instagram" },
      lanes: { instagram: { type: "run", step: "publish_instagram" } }, steps: [step("publish_youtube", { done: true, status: "done", lane: "youtube" }), step("publish_instagram", { lane: "instagram" })] }) });
    at("/studio/songs/song-008");
    fireEvent.click(await screen.findByRole("button", { name: "Don't post to Instagram" }));
    await waitFor(() => expect(posts(f, "/api/skip_lane")).toEqual([{ slug: "song-008", lane: "instagram", skip: true }]));
  });
  it("says a skipped Instagram plainly and offers to post after all", async () => {
    const f = route(OWNER, { "/api/skip_lane": () => ({ ok: true }), "/api/song/": () => detail({ slug: "song-008", meta: { type: "music", state: "published", history: [], skip: { instagram: true } } }) });
    at("/studio/songs/song-008");
    expect(await screen.findByText(/Not posted to Instagram: you skipped it/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Post to Instagram after all" }));
    await waitFor(() => expect(posts(f, "/api/skip_lane")).toEqual([{ slug: "song-008", lane: "instagram", skip: false }]));
  });
  it("lets you approve in a lane while the run is waiting at that very approval (the run counts as running and must not lock its own button)", async () => {
    const f = route(OWNER, { "/api/approve": () => ({ ok: true }), "/api/song/": () => detail({ slug: "song-007", next: { type: "gate", step: "publish_youtube", gate: "publish_youtube" }, job: { running: true, queued: false, rc: null }, status_text: "waiting for you: approve gate publish_youtube",
      lanes: { youtube: { type: "gate", step: "publish_youtube", gate: "publish_youtube" }, instagram: { type: "gate", step: "instagram_caption", gate: "instagram_caption" } },
      steps: [step("video", { done: true, status: "done" }), step("publish_youtube", { status: "waiting for approval", needs_gate: "publish_youtube", gate_before: "publish_youtube", lane: "youtube" }),
              step("instagram_caption", { status: "waiting for approval", needs_gate: "instagram_caption", gate_after: "instagram_caption", lane: "instagram" })] }) });
    at(A);
    const ig = await screen.findByRole("region", { name: "Instagram" });
    expect(screen.queryByText("Running")).toBeNull();   // no spinner saying Running next to the approvals it is waiting for
    const approve = within(ig).getByRole("button", { name: "Approve" }); expect(approve).toBeEnabled();
    fireEvent.click(approve);
    await waitFor(() => expect(posts(f, "/api/approve")).toEqual([{ slug: "song-007", gate: "instagram_caption" }]));
    expect(within(screen.getByRole("region", { name: "YouTube" })).getByRole("button", { name: "Approve" })).toBeEnabled();
  });
  it("lets you change the Instagram caption and the YouTube text at their approvals, saves them, and counts what each platform allows", async () => {
    const yt = JSON.stringify({ title: "Porch Light", description: "A song about waiting.", tags: ["folk", "country"], category: "10" });
    const f = route(OWNER, { "/api/save": () => ({ ok: true }), "/api/song/": () => detail({ slug: "song-007", next: { type: "gate", step: "publish_youtube", gate: "publish_youtube" }, job: { running: true, queued: false, rc: null }, status_text: "waiting for you: approve gate publish_youtube",
      text: { "title.txt": "Porch Light", "instagram.txt": "Who kept the porch light on?", "youtube.json": yt },
      lanes: { youtube: { type: "gate", step: "publish_youtube", gate: "publish_youtube" }, instagram: { type: "gate", step: "instagram_caption", gate: "instagram_caption" } },
      steps: [step("video", { done: true, status: "done" }), step("publish_youtube", { status: "waiting for approval", needs_gate: "publish_youtube", gate_before: "publish_youtube", lane: "youtube" }),
              step("instagram_caption", { status: "waiting for approval", needs_gate: "instagram_caption", gate_after: "instagram_caption", lane: "instagram" })] }) });
    at(A);
    const ig = await screen.findByRole("region", { name: "Instagram" }); const ytc = screen.getByRole("region", { name: "YouTube" });
    const cap = within(ig).getByLabelText("Instagram caption", { selector: "textarea" }); expect(cap).toHaveValue("Who kept the porch light on?"); expect(within(ig).getByText("28 of 2,200 characters")).toBeInTheDocument();
    expect(within(ig).getByRole("button", { name: "Save the caption" })).toBeDisabled();
    fireEvent.change(cap, { target: { value: "Who kept the porch light on? #folk" } }); fireEvent.click(within(ig).getByRole("button", { name: "Save the caption" }));
    await waitFor(() => expect(posts(f, "/api/save")).toEqual([{ slug: "song-007", file: "instagram.txt", content: "Who kept the porch light on? #folk" }]));
    fireEvent.change(within(ytc).getByLabelText("YouTube title"), { target: { value: "Porch Light (official video)" } });
    fireEvent.change(within(ytc).getByLabelText("YouTube description"), { target: { value: "A song about waiting for someone." } });
    fireEvent.change(within(ytc).getByLabelText(/^Tags/), { target: { value: "folk, country, porch light" } });
    fireEvent.click(within(ytc).getByRole("button", { name: "Save the YouTube text" }));
    await waitFor(() => expect(posts(f, "/api/save")).toHaveLength(2));
    const sent = posts(f, "/api/save")[1] as { file: string; content: string }; expect(sent.file).toBe("youtube.json");
    expect(JSON.parse(sent.content)).toEqual({ title: "Porch Light (official video)", description: "A song about waiting for someone.", tags: ["folk", "country", "porch light"], category: "10" });   // what else the file holds is kept
  });
  it("names the scheduled time on a publish approval instead of saying now, and keeps the lanes visible under a failure", async () => {
    const at6 = "2030-12-02T00:00:00Z";   // 6:00 pm CST on Dec 1
    route(OWNER, { "/api/song/": () => detail({ slug: "insp-006", meta: { type: "inspiration", state: "approved", history: [] }, next: { type: "run", step: "go_public" },
      failure: { step: "", error: "", ref: "r1", plain: "A step did not finish." },
      lanes: { youtube: { type: "gate", step: "go_public", gate: "go_public" }, instagram: { type: "gate", step: "publish_instagram", gate: "publish_instagram" } },
      steps: [step("render", { done: true, status: "done" }), step("go_public", { status: "waiting for approval", needs_gate: "go_public", gate_before: "go_public", lane: "youtube", scheduled_for: at6 }),
              step("publish_instagram", { status: "waiting for approval", needs_gate: "publish_instagram", gate_before: "publish_instagram", lane: "instagram", scheduled_for: at6 })] }) });
    at("/studio/inspiration/insp-006");
    const ig = await screen.findByRole("region", { name: "Instagram" }); const yt = screen.getByRole("region", { name: "YouTube" });   // shown although the item carries a failure
    expect(ig).toHaveTextContent("Post the Reel to Instagram Sun, Dec 1 6:00 pm CT, as scheduled. Approving now does not post now."); expect(ig).not.toHaveTextContent("Publish to Instagram now");
    expect(yt).toHaveTextContent("public Sun, Dec 1 6:00 pm CT, as scheduled"); expect(within(ig).getByRole("button", { name: "Approve" })).toBeEnabled();
  });
  it("says All set with the time and the YouTube link when only the publishing time is left, and shows when it goes out top right", async () => {
    const at6 = "2030-12-02T00:00:00Z";
    route(OWNER, { "/api/song/": () => detail({ slug: "insp-006", meta: { type: "inspiration", state: "approved", history: [], schedule: { youtube_at: at6, instagram_at: at6, done: false }, published: { youtube_items: [{ id: "dUq", url: "https://youtu.be/dUq", privacy: "private" }] } }, next: { type: "run", step: "go_public" },
      lanes: { youtube: { type: "run", step: "go_public" }, instagram: { type: "run", step: "publish_instagram" } },
      steps: [step("render", { done: true, status: "done" }), step("go_public", { lane: "youtube", scheduled_for: at6 }), step("publish_instagram", { lane: "instagram", scheduled_for: at6 })] }) });
    at("/studio/inspiration/insp-006");
    const card = await screen.findByRole("region", { name: /Goes out Sun, Dec 1 6:00 pm CT/ }); expect(card).toHaveTextContent("All set");
    expect(within(card).getByRole("link", { name: /youtu\.be\/dUq/ })).toHaveAttribute("href", "https://youtu.be/dUq");
    expect(screen.queryByRole("region", { name: "YouTube" })).toBeNull();   // no lanes with Run buttons that would only wait anyway
    expect(screen.getByRole("button", { name: /^Goes out Sun, Dec 1 6:00 pm CT YouTube \+ Instagram · Change$/ })).toBeInTheDocument();   // top right
    expect(screen.getByText(/Videos approved/)).toBeInTheDocument(); expect(document.body.textContent).not.toContain("· approved ·");   // plain words, not the state name
  });
  it("offers to delete a failed item with a confirmation, deletes it and goes back to the list; a published one shows why it cannot be deleted", async () => {
    const f = route(OWNER, { "/api/delete": () => ({ ok: true, moved_to: "_deleted/song-007-x" }), "/api/songs": () => [], "/api/song/": () => detail({ slug: "song-007", failure: { step: "video", error: "boom", ref: "r1", plain: "The video could not be built." }, deletable: { ok: true, why: "" }, steps: [step("video")] }) });
    at(A);
    expect(await screen.findByText("The video could not be built.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete this song" }));
    expect(screen.getByRole("alertdialog", { name: "Confirm deleting song-007" })).toHaveTextContent("moved to a _deleted folder inside songs, not erased"); expect(posts(f, "/api/delete")).toEqual([]);   // nothing yet
    fireEvent.click(screen.getByRole("button", { name: "Keep it" })); expect(screen.queryByRole("alertdialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Delete this song" })); fireEvent.click(screen.getByRole("button", { name: "Yes, delete song-007" }));
    await waitFor(() => expect(posts(f, "/api/delete")).toEqual([{ slug: "song-007" }]));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Songs" })).toBeInTheDocument());   // back on the list
  });

  it("does not offer deleting a published item and says why", async () => {
    route(OWNER, { "/api/song/": () => detail({ slug: "song-007", deletable: { ok: false, why: "It is published (on YouTube, Instagram, the cloud bucket or the site). Take it down there first; deleting it here would leave those behind." }, steps: [step("video", { done: true, status: "done" })] }) });
    at(`${A}?tab=activity`);
    expect(await screen.findByText(/Cannot be deleted\. It is published/)).toBeInTheDocument(); expect(screen.queryByRole("button", { name: /Delete this/ })).toBeNull();
  });
});
