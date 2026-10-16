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
  media: { settings: { image_provider: "flow", voice: "frank" }, keys: { openai: true, elevenlabs: false }, usage: { openai_usd: 0.5, eleven_seconds: 12 }, voices: { frank: "Frank (deep, wise)" }, choices: { image_provider: ["flow", "openai"], voice: ["frank"] } },
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
