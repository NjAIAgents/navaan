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
    expect(await screen.findByText(/inspiration pipeline is planned \(ref req-8\)/)).toBeInTheDocument(); expect(posts(f, "/api/new")[0]).toEqual({ type: "inspiration", idea: "Maybe you are not behind", narrate: "eleven", voice: "frank" });   // narration is a standard step: on unless unticked
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
    at("/studio/songs/song-001"); const item = (await screen.findByText("Lyrics", { selector: "b" })).closest("li")!; expect(item).toHaveTextContent("meera");
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
