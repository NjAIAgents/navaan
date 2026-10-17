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
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const IG = { empty: false, slots: [{ at: "2030-01-05T13:00:00Z", score: 91, audience_peak_hour_utc: 14 }], hours: Array.from({ length: 24 }, (_, i) => (i === 13 ? 100 : 10)), weekdays: [10, 20, 30, 40, 50, 60, 100], basis: { signals: ["followers online"] } };
const YT = { kinds: { video: { empty: false, slots: [{ at: "2030-01-05T12:00:00Z", score: 80 }], confidence: "medium", basis: { signals: ["views per day"] }, notes: [] } } };
const OPTS = { songs: [{ slug: "song-001", title: "Draft One", next: "lyrics", public: false, missing_gates: ["go_public"], schedule: "" }] };

describe("Schedule editing (NAV-26)", () => {
  it("sets times from the recommendations and refuses a Reel too close to the YouTube time", async () => {
    const f = route({ "/api/schedule/set": () => ({ ok: true }), "/api/schedule/options": () => OPTS, "/api/besttime": (_i) => IG, "/api/schedule": () => [] });
    f.mockImplementation((u: string) => Promise.resolve(u.startsWith("/api/me") ? json(OWNER) : u.startsWith("/api/besttime") ? json(u.includes("youtube") ? YT : IG) : u === "/api/schedule/options?type=music" ? json(OPTS) : u === "/api/schedule/set" ? json({ ok: true }) : json([])));
    render(<MemoryRouter initialEntries={["/studio/schedule"]}><App /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Schedule publishing" }));
    fireEvent.change(await screen.findByLabelText("Item"), { target: { value: "song-001" } }); expect(await screen.findByText(/Still to approve before that time: go_public/)).toBeInTheDocument();
    await screen.findByRole("group", { name: "Recommended Instagram times" });
    fireEvent.click(screen.getByRole("group", { name: "Recommended YouTube times" }).querySelector("button")!);
    const ig = screen.getByLabelText(/^Instagram Reel at/) as HTMLInputElement, yt = screen.getByLabelText(/^YouTube public at/) as HTMLInputElement;
    expect(new Date(ig.value).getTime() - new Date(yt.value).getTime()).toBe(60 * 60000);   // the Reel follows an hour after a chosen YouTube time
    fireEvent.change(ig, { target: { value: yt.value } }); expect(await screen.findByRole("alert")).toHaveTextContent("at least 5 minutes after the YouTube time"); expect(screen.getByRole("button", { name: "Schedule" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /Instagram.*|^\w{3}, .*91/ }) as HTMLElement);
    fireEvent.click(screen.getByRole("button", { name: "Schedule" })); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/schedule/set")).toBe(true));
    const b = JSON.parse(String(f.mock.calls.find(([u]) => u === "/api/schedule/set")![1]?.body)); expect(b.slug).toBe("song-001"); expect(b.instagram_at).toMatch(/Z$/); expect(b.youtube_at).toMatch(/Z$/);
  });
  it("accepts a suggestion and clears a schedule after a confirmation", async () => {
    let sched: unknown = undefined;
    const f = vi.fn((u: string) => Promise.resolve(u.startsWith("/api/me") ? json(OWNER) : u.startsWith("/api/schedule/suggest") ? json({ suggestion: { youtube_at: null, instagram_at: "2030-01-05T13:00:00Z", confidence: "high", basis: ["followers online"], note: "" } }) : u === "/api/schedule/accept" ? (sched = { youtube_at: "2030-01-05T12:45:00Z", instagram_at: "2030-01-05T13:00:00Z" }, json({ ok: true })) : u === "/api/schedule/clear" ? (sched = undefined, json({ ok: true })) : u.startsWith("/api/song/") ? json({ slug: "song-001", steps: [], next: { type: "run", step: "lyrics" }, text: { "title.txt": "T" }, files: {}, meta: { type: "music", state: "drafted", history: [], schedule: sched }, approvals: {}, job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "" }) : json([])));
    vi.stubGlobal("fetch", f);
    render(<MemoryRouter initialEntries={["/studio/songs/song-001?tab=publish"]}><App /></MemoryRouter>);
    expect(await screen.findByText(/Suggested from your analytics/)).toBeInTheDocument(); fireEvent.click(screen.getByRole("button", { name: "Use these times" }));
    expect(await screen.findByText(/YouTube public:/)).toBeInTheDocument(); expect(screen.getByRole("button", { name: "Change" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear" })); expect(f.mock.calls.some(([u]) => u === "/api/schedule/clear")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Yes, clear it" })); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/schedule/clear")).toBe(true));
  });
  it("says when there is not enough timing data", async () => {
    vi.stubGlobal("fetch", vi.fn((u: string) => Promise.resolve(u.startsWith("/api/me") ? json(OWNER) : u.startsWith("/api/besttime") ? json({ empty: true, notes: ["Not enough posts yet."] }) : u.startsWith("/api/schedule/options") ? json(OPTS) : json([]))));
    const { container } = render(<MemoryRouter initialEntries={["/studio/schedule"]}><App /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Schedule publishing" })); expect((await screen.findAllByText(/Not enough posts yet/)).length).toBeGreaterThan(0);
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } }); expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  });
});
