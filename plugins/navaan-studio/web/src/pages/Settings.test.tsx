import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { OWNER } from "../components/Shell.test";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
const DATA = {
  accounts: [{ type: "music", handle: "navaan", youtube_channel: "", configured: true, ig: { present: true, ok: false, error: "Token expired" }, market: { present: false }, yt: { present: true, ok: true, channel: "NAVAAN" }, yt_analytics: { present: false } }],
  cloud: { provider: "oci", bucket: "navaan", region: "ap-mumbai-1" }, secret_present: true, checked_at: "2026-10-16T00:00:00Z", claude: { credential: "subscription token", state: "ok", headless: true },
  media: { settings: { image_provider: "flow", voice: "frank", max_run_usd: 0.8, song_pictures: 16, eleven_monthly_seconds: 1500 }, keys: { openai: true, elevenlabs: false }, usage: { openai_usd: 0.5, eleven_seconds: 12 }, voices: { frank: "Frank (deep, wise)" }, choices: { image_provider: ["flow", "openai"], voice: ["frank"] } },
  gates: [{ id: "lyrics", on: true, types: ["music"] }, { id: "publish_youtube", on: true, types: ["music"] }],
};
function route(routes: Record<string, (init?: RequestInit) => unknown>) {
  const f = vi.fn((u: string, init?: RequestInit) => {
    if (u.startsWith("/api/me")) return Promise.resolve(json(OWNER));
    const k = Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => u === r || u.startsWith(r)); const v = k ? routes[k](init) : [];
    return Promise.resolve(v instanceof Response ? v : json(v));
  });
  vi.stubGlobal("fetch", f); return f;
}
const posts = (f: ReturnType<typeof route>, path: string) => f.mock.calls.filter(([u]) => u === path).map(([, i]) => JSON.parse(String(i?.body)));
const at = () => render(<MemoryRouter initialEntries={["/studio/settings"]}><App /></MemoryRouter>);
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Settings (NAV-24) and the alerts banner (NAV-27)", () => {
  const open = async (name: RegExp | string) => { const b = await screen.findByRole("button", { name }); if (b.getAttribute("aria-expanded") !== "true") fireEvent.click(b); };
  it("opens on an at-a-glance board: what needs you first, with a Fix button, and never the token", async () => {
    route({ "/api/settings": () => DATA });
    at(); const board = await screen.findByRole("heading", { name: "At a glance" });
    const rows = within(board.closest("section")!).getAllByRole("listitem").map((li) => li.textContent);
    expect(rows[0]).toContain("Music: Instagram"); expect(rows[0]).toContain("Token expired");   // the broken one is first
    expect(rows.at(-1)).toContain("Cloud storage"); expect(board.closest("section")).toHaveTextContent(/need/);
    expect(document.body.innerHTML).not.toMatch(/sk-ant|access_token/);
  });
  it("Fix on the board opens the right tab with that row folded open", async () => {
    route({ "/api/settings": () => DATA });
    at(); fireEvent.click(await screen.findByRole("button", { name: "Fix ElevenLabs" }));
    expect(await screen.findByRole("tab", { name: "AI services", selected: true })).toBeInTheDocument(); expect(screen.getByLabelText("ElevenLabs key")).toBeInTheDocument();
  });
  it("saves a new Instagram token, then clears the box", async () => {
    const f = route({ "/api/settings/ig_save": () => ({ ok: true }), "/api/settings": () => DATA });
    at(); await open(/^Instagram/); const box = await screen.findByLabelText("New Instagram token"); expect(box).toHaveAttribute("type", "password");
    fireEvent.change(box, { target: { value: "IGQ123" } }); fireEvent.click(screen.getByRole("button", { name: "Save token" }));
    await waitFor(() => expect(posts(f, "/api/settings/ig_save")).toEqual([{ type: "music", kind: "login", token: "IGQ123" }])); await waitFor(() => expect((screen.getByLabelText("New Instagram token") as HTMLInputElement).value).toBe(""));
  });
  it("switches a safe gate straight away but asks before a risky one", async () => {
    const f = route({ "/api/settings/gates_save": () => ({ gates: [] }), "/api/settings": () => DATA });
    at(); fireEvent.click(await screen.findByRole("tab", { name: "Automation" })); const lyr = await screen.findByRole("switch", { name: /Lyrics/ }); fireEvent.click(lyr);
    await waitFor(() => expect(posts(f, "/api/settings/gates_save")).toEqual([{ gates: { lyrics: false } }]));
    fireEvent.click(screen.getByRole("switch", { name: /Upload the video to YouTube|publish_youtube|YouTube/ })); expect(await screen.findByRole("alertdialog")).toHaveTextContent("approve itself"); expect(posts(f, "/api/settings/gates_save")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Yes, approve it automatically" })); await waitFor(() => expect(posts(f, "/api/settings/gates_save")[1]).toEqual({ gates: { publish_youtube: false } }));
  });
  it("switches automatic licence confirmation on with the owner's statement, and needs the statement first", async () => {
    const f = route({ "/api/settings/licence_save": () => ({ licence: {} }), "/api/settings": () => ({ ...DATA, licence: { auto: false, statement: "", suggested: "Every song I publish is made on a paid Suno plan.", set_by: "", set_at: "" } }) });
    at(); fireEvent.click(await screen.findByRole("tab", { name: "Automation" }));
    const box = await screen.findByLabelText("Your statement (in your own words)") as HTMLTextAreaElement; expect(box.value).toContain("paid Suno plan");   // the suggestion is there to edit, not saved
    const sw = screen.getByRole("switch", { name: /Confirm the licence of songs I publish automatically/ }); expect(sw).not.toBeChecked();
    fireEvent.change(box, { target: { value: "" } }); fireEvent.click(sw); expect(await screen.findByRole("alert")).toHaveTextContent("Write the statement first"); expect(posts(f, "/api/settings/licence_save")).toHaveLength(0);
    fireEvent.change(box, { target: { value: "All my songs are on a paid plan." } }); fireEvent.click(sw);
    await waitFor(() => expect(posts(f, "/api/settings/licence_save")).toEqual([{ auto: true, statement: "All my songs are on a paid plan." }]));
  });
  it("says which songs were confirmed the moment the statement was switched on", async () => {
    route({ "/api/settings/licence_save": () => ({ licence: {}, note: "Confirmed now: song-008, song-009. They show on the site." }), "/api/settings": () => ({ ...DATA, licence: { auto: false, statement: "", suggested: "Every song I publish is made on a paid Suno plan.", set_by: "", set_at: "" } }) });
    at(); fireEvent.click(await screen.findByRole("tab", { name: "Automation" }));
    fireEvent.change(await screen.findByLabelText("Your statement (in your own words)"), { target: { value: "All my songs are on a paid plan." } }); fireEvent.click(screen.getByRole("switch", { name: /Confirm the licence of songs I publish automatically/ }));
    expect(await screen.findByText(/Confirmed now: song-008, song-009/)).toBeInTheDocument();
  });
  it("saves the dev.to key and the LinkedIn token for the blog's Post buttons, and says whose token it is", async () => {
    const f = route({ "/api/settings/media_key": () => ({ note: "" }), "/api/settings/linkedin_save": () => ({ note: "LinkedIn says this token is for Navjyot N." }), "/api/settings": () => ({ ...DATA, media: { ...DATA.media, keys: { openai: true, elevenlabs: true } } }) });
    at(); await screen.findByRole("heading", { name: "Blog" });
    fireEvent.click(screen.getByRole("button", { name: /^dev\.to/ })); fireEvent.change(await screen.findByLabelText("dev.to API key"), { target: { value: "devkey-0123456789abcdef" } }); fireEvent.click(screen.getByRole("button", { name: "Save token" }));
    await waitFor(() => expect(posts(f, "/api/settings/media_key")).toEqual([{ provider: "devto", token: "devkey-0123456789abcdef" }]));
    fireEvent.click(screen.getByRole("button", { name: /^LinkedIn/ })); expect(await screen.findByText(/has no way to post a long article from outside/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("LinkedIn access token"), { target: { value: "AQV" + "x".repeat(60) } }); fireEvent.change(screen.getByLabelText(/Your member id/), { target: { value: "abc123" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Save token" }).at(-1)!);
    await waitFor(() => expect(posts(f, "/api/settings/linkedin_save")).toEqual([{ token: "AQV" + "x".repeat(60), author: "abc123" }])); expect(await screen.findByText("LinkedIn says this token is for Navjyot N.")).toBeInTheDocument();
  });
  it("saves a pasted YouTube token file as the fallback sign-in, and has the setup guides", async () => {
    const f = route({ "/api/settings/yt_save": () => ({ ok: true }), "/api/settings": () => DATA });
    at(); await open(/YouTube publishing/);
    fireEvent.click(await screen.findByText("Or sign in from a terminal and paste the token file"));
    fireEvent.change(screen.getByLabelText("Token file for YouTube publishing"), { target: { value: '{"token": "x"}' } }); fireEvent.click(screen.getByRole("button", { name: "Save the token file" }));
    await waitFor(() => expect(posts(f, "/api/settings/yt_save")).toEqual([{ type: "music", which: "publish", content: '{"token": "x"}' }]));
    expect(screen.getByText("How to set up YouTube (first time)")).toBeInTheDocument();
  });
  it("sets the spending limits: the most one run may spend on pictures, pictures per song, narration per month", async () => {
    const f = route({ "/api/settings/media_save": () => ({ ok: true }), "/api/settings": () => DATA });
    at(); fireEvent.click(await screen.findByRole("tab", { name: "AI services" }));
    const cap = await screen.findByLabelText("Most one run may spend on pictures (US dollars)"); expect(cap).toHaveValue(0.8); expect(screen.getByLabelText("Pictures planned per song")).toHaveValue(16);
    fireEvent.change(cap, { target: { value: "1.5" } }); fireEvent.click(screen.getByRole("button", { name: "Save these choices" }));
    await waitFor(() => expect(posts(f, "/api/settings/media_save")).toEqual([{ settings: { max_run_usd: "1.5" } }]));
  });
  it("has a Muse key box and a Picture maker choice, and saves the Muse key as provider muse", async () => {
    const f = route({ "/api/settings/media_key": () => ({ note: "" }), "/api/settings": () => ({ ...DATA, media: { ...DATA.media, settings: { ...DATA.media.settings, image_engine: "openai" }, keys: { openai: true, muse: false, elevenlabs: false }, choices: { ...DATA.media.choices, image_engine: ["openai", "muse"] } } }) });
    at(); fireEvent.click(await screen.findByRole("tab", { name: "AI services" })); expect(await screen.findByLabelText("Picture maker")).toHaveValue("openai");
    await open(/^Muse/); fireEvent.change(await screen.findByLabelText("Muse key"), { target: { value: "LLM|0123456789abcdef" } }); fireEvent.click(screen.getByRole("button", { name: "Save token" }));
    await waitFor(() => expect(posts(f, "/api/settings/media_key")).toEqual([{ provider: "muse", token: "LLM|0123456789abcdef" }]));
  });
  it("says in words what Made by and Picture maker mean, and that Muse ignores model and quality", async () => {
    route({ "/api/settings": () => ({ ...DATA, media: { ...DATA.media, settings: { ...DATA.media.settings, image_provider: "openai", image_engine: "muse" }, choices: { ...DATA.media.choices, image_engine: ["openai", "muse"], image_model: ["gpt-image-2.5-flare"], image_quality: ["high"] } } }) });
    at(); fireEvent.click(await screen.findByRole("tab", { name: "AI services" }));
    expect(await screen.findByLabelText("Pictures are made by")).toHaveDisplayValue("Automatic (an image API, chosen below)"); expect(screen.getByLabelText("Picture maker")).toHaveDisplayValue("Muse (Meta, $0.01 a picture)");
    expect(screen.getByText(/Muse has one model and no quality setting/)).toBeInTheDocument(); expect(screen.queryByLabelText("Model")).toBeNull(); expect(screen.queryByLabelText("Quality")).toBeNull();
    fireEvent.change(screen.getByLabelText("Picture maker"), { target: { value: "openai" } }); expect(await screen.findByLabelText("Model")).toBeInTheDocument(); expect(screen.getByLabelText("Quality")).toBeInTheDocument();
  });
  it("shows the server's refusal under the box", async () => {
    route({ "/api/settings/claude_save": () => json({ error: "that token was refused" }, 400), "/api/settings": () => DATA });
    at(); fireEvent.click(await screen.findByRole("tab", { name: "AI services" })); await open(/^Claude/);
    fireEvent.change(await screen.findByLabelText(/^Claude token/), { target: { value: "x" } }); fireEvent.click(screen.getByRole("button", { name: "Save token" }));
    expect(await screen.findByText(/that token was refused/)).toBeInTheDocument();
  });
  it("tells you next to the ElevenLabs box when the key is refused, and when it is saved with a note", async () => {
    let n = 0;
    route({ "/api/settings/media_key": () => (n++ ? { ok: true, note: "Saved. It cannot read the account, narration works if the key has Text to Speech." } : json({ error: "ElevenLabs refused the key (HTTP 401): it is not a valid key." }, 400)), "/api/settings": () => DATA });
    at(); fireEvent.click(await screen.findByRole("tab", { name: "AI services" })); await open(/^ElevenLabs/); const box = await screen.findByLabelText("ElevenLabs key"); const btn = box.closest("form")!.querySelector("button")!;
    fireEvent.change(box, { target: { value: "bad" } }); fireEvent.click(btn);
    expect(await screen.findByRole("alert")).toHaveTextContent("not a valid key");
    fireEvent.change(box, { target: { value: "good" } }); fireEvent.click(btn);
    expect(await screen.findByRole("status")).toHaveTextContent("Text to Speech");
  });
  it("shows an alert banner on a studio screen with a way to fix it", async () => {
    route({ "/api/alerts": () => ({ alerts: [{ id: "ig:music:login", kind: "ig", title: "Instagram token expires in 3 days (Music)", message: "A fresh 60 day token is one click away." }] }), "/auth/state": () => ({ scheduler: "paused", worker: "down" }), "/api/settings": () => DATA });
    at(); const r = await screen.findByRole("region", { name: "Needs attention" });
    expect(r).toHaveTextContent("Instagram token expires in 3 days"); expect(r).toHaveTextContent("The schedule is paused"); expect(r).toHaveTextContent("The worker is down");
  });
  it("has no serious accessibility violations", async () => {
    route({ "/api/settings": () => DATA });
    const { container } = at(); await screen.findByRole("heading", { name: "At a glance" });
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } }); expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  });
});
