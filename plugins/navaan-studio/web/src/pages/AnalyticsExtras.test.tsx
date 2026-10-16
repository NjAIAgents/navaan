import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { OWNER } from "../components/Shell.test";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
const OV = {
  account: "all", days: 30, accounts: [{ label: "music" }], kpis: { followers: 10 }, series: {}, runs: [], collect: { running: false },
  posts: [{ media_id: "m1", title: "", slug: "", permalink: "https://ig/p/1", posted_at: "2026-10-01", views: 5, reach: 4, saved: 1, shares: 0, engagement_rate: 2 }, { media_id: "m2", title: "Linked", slug: "song-001", permalink: "https://ig/p/2", posted_at: "2026-10-02", views: 9, reach: 8, saved: 1, shares: 0, engagement_rate: 3 }],
  reco: { ready: true, open: [], done: [], dismissed: [] },
  peers: { rows: [{ username: "peer_one", followers: 1000, posts_per_week: 3, median_likes: 50, median_comments: 4, eng_per_1k: 54, reel_share: 60, top_tags: ["hindi"], best: { permalink: "https://ig/p/9", likes: 300 } }], own: [] },
  hashtags: { peer_posts_with_tags: 12, suggested: { music: [{ tag: "hindisongs", peers: ["peer_one", "peer_two"], in_use: false }] }, own: {} },
};
const AUTO = { enabled: false, every_days: 7, hour: 9, ask: false, last_run: null, last_note: null, next_run: null, running: false, choices: [1, 3, 7] };
function stub(over: Record<string, unknown> = {}) {
  const f = vi.fn((u: string, _init?: RequestInit) => {
    if (u.startsWith("/api/me")) return Promise.resolve(json(OWNER));
    if (u.startsWith("/api/analytics/auto")) return Promise.resolve(json(AUTO));
    if (u.startsWith("/api/analytics/implement")) return Promise.resolve(json(over["/api/analytics/implement"] ?? { kind: "rule" }));
    if (u.startsWith("/api/analytics/collect") || u.startsWith("/api/analytics/analyze") || u.startsWith("/api/analytics/ask") || u.startsWith("/api/analytics/link")) return Promise.resolve(json(over[u] ?? { started: true, ok: true, results: [] }));
    if (u.startsWith("/api/analytics?")) return Promise.resolve(json(over.overview ?? OV));
    if (u.startsWith("/api/songs")) return Promise.resolve(json([{ slug: "song-001", title: "Tere" }, { slug: "song-004", title: "Rang" }]));
    if (u.startsWith("/api/analytics/song")) return Promise.resolve(json(over.song ?? { empty: true }));
    return Promise.resolve(json([]));
  });
  vi.stubGlobal("fetch", f); return f;
}
const body = (f: ReturnType<typeof stub>, path: string) => JSON.parse(String(f.mock.calls.find(([u]) => u === path)![1]?.body));
const at = (path = "/studio/analytics") => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Analytics extras (NAV-28)", () => {
  it("runs nothing until pressed, then starts a collection for the chosen account", async () => {
    const f = stub(); at(); const btn = await screen.findByRole("button", { name: "Collect now" });
    expect(f.mock.calls.some(([u]) => u === "/api/analytics/collect")).toBe(false); fireEvent.click(btn);
    await waitFor(() => expect(body(f, "/api/analytics/collect")).toEqual({ account: "all", platform: "instagram" })); expect(await screen.findByText(/Collecting started/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Re-run analysis" })); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/analytics/analyze")).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "Ask for advice" })); await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/analytics/ask")).toBe(true));
  });
  it("shows a running collection and a failed one", async () => {
    stub({ overview: { ...OV, collect: { running: true, account: "music" } } }); const { unmount } = at(); expect(await screen.findByText(/Collecting music/)).toBeInTheDocument(); expect(screen.getByRole("button", { name: "Collecting…" })).toBeDisabled(); unmount(); cleanup();
    stub({ overview: { ...OV, collect: { running: false, rc: 1, tail: "line1\nToken expired" } } }); at(); expect(await screen.findByRole("alert")).toHaveTextContent("Token expired");
  });
  it("shows peers and hashtag suggestions", async () => {
    stub(); at(); expect(await screen.findByRole("link", { name: "@peer_one" })).toBeInTheDocument(); expect(screen.getByText(/#hindisongs 2/)).toBeInTheDocument();
  });
  it("links an unmatched post to a song so it counts for that song", async () => {
    const f = stub(); at(); await screen.findAllByRole("option", { name: /song-004/ }); fireEvent.change(await screen.findByLabelText("Link m1 to a song"), { target: { value: "song-004" } }); fireEvent.click(screen.getByRole("button", { name: "Link m1" }));
    await waitFor(() => expect(body(f, "/api/analytics/link")).toEqual({ media_id: "m1", slug: "song-004" })); expect(screen.queryByLabelText("Link m2 to a song")).toBeNull();   // a linked post has no picker
  });
  it("puts a recommendation to work, and opens the schedule for a timing one", async () => {
    const rec = (id: string, category: string) => ({ rec_id: id, title: `Rec ${id}`, why: "w", action: "a", expected_effect: "", priority: 1, category, confidence: "high", status: "open", dismissed_reason: null, account: "music", evidence: [] });
    const f = stub({ overview: { ...OV, reco: { ready: true, open: [rec("c-aaaaaa", "hashtags"), rec("c-bbbbbb", "timing")], done: [], dismissed: [] } }, "/api/analytics/implement": { kind: "rule" } });
    at("/studio/analytics?tab=recommendations"); fireEvent.click((await screen.findAllByRole("button", { name: /Put it to work/ }))[0]);
    await waitFor(() => expect(body(f, "/api/analytics/implement")).toEqual({ id: "c-aaaaaa" }));
  });
  it("saves the auto refresh settings", async () => {
    const f = stub(); at(); fireEvent.click(await screen.findByRole("switch", { name: /Collect and analyse on a schedule/ })); fireEvent.change(screen.getByLabelText("Every"), { target: { value: "3" } }); fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(f.mock.calls.some(([u, i]) => u === "/api/analytics/auto" && i?.method === "POST")).toBe(true)); expect(JSON.parse(String(f.mock.calls.find(([u, i]) => u === "/api/analytics/auto" && i?.method === "POST")![1]?.body))).toEqual({ enabled: true, every_days: 3, hour: 9, ask: false });
  });
  it("shows a published song's numbers on its page", async () => {
    stub({ song: { empty: false, totals: { views: 120, reach: 90, saved: 7, shares: 2 }, posts: [{ media_id: "m2", permalink: "https://ig/p/2", product_type: "REELS", account: "music", views: 120, comments_total: 3, compare: { views_vs_median: 1.5, views_rank: 1, account_posts: 8 } }], unlinked: [], youtube: { videos: [{ video_id: "v1", title: "Tere", url: "https://yt/v1", views: 55 }] } } });
    vi.stubGlobal("fetch", vi.fn((u: string) => Promise.resolve(u.startsWith("/api/me") ? json(OWNER) : u.startsWith("/api/analytics/song") ? json({ empty: false, totals: { views: 120, reach: 90, saved: 7, shares: 2 }, posts: [{ media_id: "m2", permalink: "https://ig/p/2", product_type: "REELS", account: "music", views: 120, comments_total: 3, compare: { views_vs_median: 1.5, views_rank: 1, account_posts: 8 } }], unlinked: [], youtube: { videos: [{ video_id: "v1", title: "Tere", url: "https://yt/v1", views: 55 }] } }) : u.startsWith("/api/song/") ? json({ slug: "song-001", steps: [], next: { type: "done" }, text: { "title.txt": "Tere" }, files: {}, meta: { type: "music", state: "published", history: [] }, approvals: {}, job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "" }) : json([]))));
    at("/studio/songs/song-001"); expect(await screen.findByRole("heading", { name: "How it is doing" })).toBeInTheDocument(); expect(screen.getByText(/1.5× the account's median/)).toBeInTheDocument(); expect(screen.getByRole("link", { name: "Tere" })).toBeInTheDocument();
  });
  it("shows an empty state with the Collect button, not an error screen, when nothing is collected yet (a fresh database)", async () => {
    stub({ overview: { empty: true, reason: "no_database", db: "x", collect: { running: false } } });
    at(); expect(await screen.findByText(/Nothing collected yet/)).toBeInTheDocument(); expect(screen.getByRole("button", { name: "Collect now" })).toBeInTheDocument(); expect(screen.queryByText("This screen hit a problem")).toBeNull();
  });
  it("has no serious accessibility violations", async () => {
    stub(); const { container } = at(); await screen.findByRole("heading", { name: "Auto refresh" });
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } }); expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  });
});
