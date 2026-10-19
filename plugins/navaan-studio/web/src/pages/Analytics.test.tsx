import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json", "X-Request-Id": "req-9" } });
const rec = (o: object = {}) => ({ rec_id: "c-aaaaaa", title: "Post on a fixed schedule", why: "Only 0.5 posts per week.", action: "Batch four clips.", expected_effect: "More posts to measure.", priority: 1, category: "cadence", confidence: "low", status: "open", dismissed_reason: null, account: "inspiration", evidence: [{ title: "About 0.8 posts per week", severity: "medium" }], ...o });
const series = (a: number, b: number): [string, number][] => [["2026-10-01", a], ["2026-10-02", (a + b) / 2], ["2026-10-03", b]];
const ig = (o: object = {}) => ({
  empty: false, account: "all", days: 30, accounts: [{ label: "music" }, { label: "inspiration" }], kpis: { followers: 8, followers_change: 5, views: 825, interactions: 46, accounts_engaged: 22, waiting: 0 },
  series: { followers: series(3, 8), views: series(100, 400) },
  posts: [{ media_id: "m1", title: "Quote One", slug: "insp-001", posted_at: "2026-10-02T10:00:00Z", permalink: "https://ig/p/1", views: 321, reach: 200, saved: 7, shares: 3, engagement_rate: 4.5 }],
  reco: { ready: true, open: [rec()], done: [rec({ rec_id: "c-bbbbbb", title: "Already did this", status: "done" })], dismissed: [rec({ rec_id: "c-cccccc", title: "Not for me", status: "dismissed", dismissed_reason: "no time" })] },
  besttime: { music: { label: "music", empty: false, hours: Array.from({ length: 24 }, (_, h) => (h === 23 ? 100 : h === 0 ? 90 : 20)), weekdays: [60, 70, 80, 90, 100, 50, 40], slots: [{ at: "2026-10-20T23:00:00Z", score: 97 }], notes: ["Few own posts yet."], basis: { signals: ["followers online"], own_posts: 12, peer_posts: 140 } } },
  runs: [{ started_at: "2026-10-14T23:00:00Z", status: "ok", errors: 0, first_error: "" }], collect: { running: false }, ...o,
});
const yt = () => ({ ...ig(), kpis: { subscribers: 6, subscribers_change: -1, views: 207, watch_hours: 0.6, subs_gained: 4, waiting: 1 }, series: { subscribers: series(5, 6) }, posts: undefined, videos: [{ video_id: "v1", title: "Finding Your Way Back", kind: "video", published_at: "2026-10-01T10:00:00Z", url: "https://yt/v1", views: 99, likes: 5, comments: 1, avg_view_s: 12.3 }] });

function mock(routes: Record<string, (init?: RequestInit) => unknown>) {
  const f = vi.fn((url: string, init?: RequestInit) => { const k = Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => url.startsWith(r)); return Promise.resolve(k ? json(routes[k](init)) : json({ error: "no route " + url }, 404)); });
  vi.stubGlobal("fetch", f); return f;
}
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
const posts = (f: ReturnType<typeof mock>, path: string) => f.mock.calls.filter(([u]) => u === path);
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Studio > Analytics", () => {
  it("shows the three tabs and the same numbers the API returns", async () => {
    const f = mock({ "/api/analytics": () => ig() });
    at("/studio/analytics");
    expect(await screen.findByRole("tab", { name: "Analytics" })).toHaveAttribute("aria-selected", "true");
    for (const t of ["Recommendations", "Interactions"]) expect(screen.getByRole("tab", { name: new RegExp(t) })).toBeInTheDocument();
    await screen.findAllByText("Followers");   // the numbers arrive after the tabs: wait for them
    const kpi = (label: string) => screen.getAllByText(label).map((e) => e.closest(".kpi")).find(Boolean) as HTMLElement;
    expect(kpi("Followers")).toHaveTextContent("8"); expect(kpi("Followers")).toHaveTextContent("+5"); expect(kpi("Views")).toHaveTextContent("825"); expect(kpi("Interactions")).toHaveTextContent("46"); expect(kpi("Accounts engaged")).toHaveTextContent("22");
    const row = screen.getByRole("link", { name: "Quote One" }).closest("tr")!; expect(row).toHaveTextContent("321"); expect(within(row).getByText("4.5%")).toBeInTheDocument();
    expect(row.querySelectorAll("td[data-label]").length).toBe(11);   // each cell carries its label, so the phone can stack it (post, 9 numbers, views over time)
    expect(f.mock.calls.some(([u]) => u === "/api/analytics?account=all&days=30")).toBe(true);
    expect(screen.getByRole("img", { name: /followers: from 3 on 2026-10-01 to 8/i })).toBeInTheDocument();
  });
  it("changing platform, account and period asks for that data", async () => {
    const f = mock({ "/api/analytics/youtube": () => yt(), "/api/analytics": () => ig() });
    at("/studio/analytics");
    await screen.findByRole("tab", { name: "Analytics" });
    fireEvent.click(screen.getByRole("button", { name: "YouTube" }));
    expect(await screen.findByRole("link", { name: "Finding Your Way Back" })).toBeInTheDocument(); expect(screen.getByText("Subscribers").closest(".kpi")).toHaveTextContent("-1");
    fireEvent.change(screen.getByLabelText("Period"), { target: { value: "90" } });
    await waitFor(() => expect(f.mock.calls.some(([u]) => u === "/api/analytics/youtube?account=all&days=90")).toBe(true));
  });
  it("opens on the tab named in the address", async () => {
    mock({ "/api/analytics": () => ig() }); at("/studio/analytics?tab=recommendations");
    expect(await screen.findByRole("tab", { name: /Recommendations/ })).toHaveAttribute("aria-selected", "true"); expect(await screen.findByRole("heading", { name: "Post on a fixed schedule" })).toBeInTheDocument();
  });
});

describe("Studio > Analytics > Recommendations", () => {
  it("shows the evidence and the action, and Done or Dismiss posts that recommendation's id", async () => {
    const f = mock({ "/api/analytics/rec": () => ({ ok: true }), "/api/analytics": () => ig() });
    at("/studio/analytics?tab=recommendations");
    const card = (await screen.findByRole("heading", { name: "Post on a fixed schedule" })).closest("article")!;
    expect(card).toHaveTextContent("About 0.8 posts per week"); expect(card).toHaveTextContent("Batch four clips.");
    fireEvent.click(within(card).getByRole("button", { name: /Dismiss/ }));
    await waitFor(() => expect(posts(f, "/api/analytics/rec")).toHaveLength(1));
    expect(JSON.parse(String(posts(f, "/api/analytics/rec")[0][1]?.body))).toEqual({ id: "c-aaaaaa", status: "dismissed" });
    fireEvent.click(within(card).getByRole("button", { name: /Done/ }));
    await waitFor(() => expect(JSON.parse(String(posts(f, "/api/analytics/rec")[1][1]?.body))).toEqual({ id: "c-aaaaaa", status: "done" }));
  });
  it("a dismissed one is under Dismissed with its reason and can be reopened", async () => {
    const f = mock({ "/api/analytics/rec": () => ({ ok: true }), "/api/analytics": () => ig() });
    at("/studio/analytics?tab=recommendations");
    await screen.findByRole("heading", { name: "Post on a fixed schedule" }); expect(screen.queryByText("Not for me")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Dismissed/ }));
    const card = screen.getByRole("heading", { name: "Not for me" }).closest("article")!; expect(card).toHaveTextContent("Dismissed: no time");
    fireEvent.click(within(card).getByRole("button", { name: /Reopen/ }));
    await waitFor(() => expect(JSON.parse(String(posts(f, "/api/analytics/rec")[0][1]?.body))).toEqual({ id: "c-cccccc", status: "open" }));
  });
});

describe("Studio > Analytics > Interactions", () => {
  const item = (o: object = {}) => ({ comment_id: "Ugx1", username: "@viewer", text: "Thank you for this", posted_at: "2026-10-13T06:58:29Z", post_id: "v1", post: "Finding Your Way Back", account: "inspiration", link: "https://yt/v1&lc=Ugx1", reply: null, ...o });
  it("sends nothing until Approve and send is pressed and confirmed", async () => {
    let waiting = [item()];
    const f = mock({ "/api/analytics": () => ig(), "/api/replies/send": () => { waiting = []; return { ok: true, reply: { status: "sent" } }; }, "/api/replies": () => ({ items: waiting }) });
    at("/studio/analytics?tab=interactions&platform=youtube");
    const box = await screen.findByLabelText("Your reply"); expect(screen.getByRole("button", { name: "Approve and send" })).toBeDisabled();
    fireEvent.change(box, { target: { value: "Thank you, take care." } });
    fireEvent.click(screen.getByRole("button", { name: "Approve and send" }));
    expect(posts(f, "/api/replies/send")).toHaveLength(0); expect(screen.getByText(/posts the reply publicly on YouTube/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Yes, send" }));
    await screen.findByText("No comments are waiting for a reply.");
    expect(JSON.parse(String(posts(f, "/api/replies/send")[0][1]?.body))).toEqual({ platform: "youtube", comment_id: "Ugx1", text: "Thank you, take care." });
  });
  it("drafts on request, shows the draft to edit, and skip removes the comment", async () => {
    let waiting = [item()];
    const f = mock({ "/api/analytics": () => ig(), "/api/replies/draft": () => ({ ok: true, reply: { draft: "Thank you so much." } }), "/api/replies/skip": () => { waiting = []; return { ok: true }; }, "/api/replies": () => ({ items: waiting }) });
    at("/studio/analytics?tab=interactions&platform=youtube");
    fireEvent.click(await screen.findByRole("button", { name: "Draft with Claude" }));
    await waitFor(() => expect(screen.getByLabelText("Your reply")).toHaveValue("Thank you so much."));
    expect(posts(f, "/api/replies/send")).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Skip" })); await screen.findByText("No comments are waiting for a reply.");
  });
  it("shows the server's error with its request id", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(url.startsWith("/api/replies") ? json({ error: "token expired" }, 502) : json(ig()))));
    at("/studio/analytics?tab=interactions"); expect(await screen.findByRole("alert")).toHaveTextContent("token expired (ref req-9)");
  });
});

const T = (v: number) => ({ views: v, plays: 2, seconds: 150, pitch: 1, visitors: 3 });
const VISITS = { days: 30, totals: { today: T(4), d7: T(9), d30: T(20) }, songs: [{ slug: "song-001", title: "Tere Hone Se", views: 7, plays: 2, seconds: 150, visitors: 3 }],
  sources: [{ name: "youtube", views: 5, plays: 2, visitors: 2 }, { name: "direct", views: 2, plays: 0, visitors: 1 }], devices: [{ name: "mobile", views: 7, plays: 2, visitors: 3 }], daily: [] };

describe("Studio > Analytics > audience and what works (NAV-29)", () => {
  const P = { language: [{ name: "hi", posts: 3, videos: 3, avg_views: 300 }, { name: "en", posts: 1, videos: 1, avg_views: 120 }], genre: [{ name: "folk", posts: 2, videos: 2, avg_views: 250 }], kind: [{ name: "short", videos: 3, avg_views: 400, avg_view_pct: 71 }, { name: "video", videos: 1, avg_views: 90, avg_view_pct: 34 }] };
  const three = (p: object) => [p, { ...p, media_id: "m2", video_id: "v2" }, { ...p, media_id: "m3", video_id: "v3" }];
  it("Instagram: who the followers are, when they are online, and average views by language and genre", async () => {
    mock({ "/api/analytics": () => ig({ posts: three(ig().posts![0]), patterns: P, audience: { city: [["Mumbai, Maharashtra", 40]], country: [["IN", 70], ["US", 9]], age: [["25-34", 31]], gender: [["F", 52]] }, hours: Array.from({ length: 24 }, (_, h) => [h, h === 15 ? 90 : 10]) }) });
    at("/studio/analytics");
    expect(await screen.findByRole("list", { name: "Top countries" })).toHaveTextContent("IN"); expect(screen.getByRole("list", { name: "Top cities" })).toHaveTextContent("Mumbai");
    expect(screen.getByRole("img", { name: /Most at 15:00/ })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Average views by language" })).toHaveTextContent("hi (3)"); expect(screen.getByText(/Early signal from 3 posts/)).toBeInTheDocument();
  });
  it("YouTube: traffic sources with shares, retention curves, and how much of Shorts and videos is watched", async () => {
    mock({ "/api/analytics/youtube": () => ({ ...yt(), videos: three(yt().videos![0]), patterns: P, traffic: [{ source: "YT_SHORTS", views: 75 }, { source: "SUBSCRIBER", views: 25 }], audience: { country: [["IN", 80]], age: [["age25-34", 41.5]], gender: [["female", 55.2]] },
      retention: [{ name: "Finding Your Way Back", kind: "short", points: [[0, 1], [0.5, 0.6], [1, 0.4]] }] }), "/api/analytics": () => ig() });
    at("/studio/analytics?platform=youtube");
    expect(await screen.findByRole("list", { name: "Traffic sources" })).toHaveTextContent("shorts75 · 75%");
    expect(screen.getByRole("list", { name: "Age" })).toHaveTextContent("25-3441.5%");
    expect(screen.getByRole("img", { name: /Finding Your Way Back: share still watching from start to end, 40% at the end/ })).toBeInTheDocument();
    expect(screen.getByText("Average share of the video watched: Shorts 71%, videos 34%.")).toBeInTheDocument();
  });
  it("sorts the posts by any column and filters YouTube to Shorts, with a views-over-time line per row", async () => {
    const p0 = ig().posts![0];
    mock({ "/api/analytics": () => ig({ posts: [{ ...p0, title: "Low", media_id: "a", views: 10, like_count: 9, trend: [1, 5, 10] }, { ...p0, title: "High", media_id: "b", views: 900, like_count: 2 }] }) });
    at("/studio/analytics");
    const order = () => within(screen.getByRole("region", { name: /^Posts/ })).getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("link")[0].textContent);
    await screen.findByRole("link", { name: "High" }); expect(order()).toEqual(["High", "Low"]);   // most views first
    fireEvent.click(screen.getByRole("button", { name: "Likes" })); expect(order()).toEqual(["Low", "High"]);
    expect(screen.getByRole("img", { name: "Low: views from 1 to 10" })).toBeInTheDocument();
    cleanup(); const v0 = yt().videos![0];
    mock({ "/api/analytics/youtube": () => ({ ...yt(), videos: [{ ...v0, title: "Long one" }, { ...v0, video_id: "s1", title: "Short one", kind: "short", privacy: "private" }] }), "/api/analytics": () => ig() });
    at("/studio/analytics?platform=youtube"); await screen.findByRole("link", { name: "Short one" });
    fireEvent.click(screen.getByRole("button", { name: "Shorts" })); expect(screen.queryByRole("link", { name: "Long one" })).toBeNull(); expect(screen.getByText("private", { exact: false })).toBeInTheDocument();
  });
  it("recommendations: what changed after one was done, Claude's sources, and a Claude run that did not finish", async () => {
    const done = rec({ rec_id: "c-d1", title: "Post at 6 pm", status: "done", done_at: "2026-10-10T10:00:00Z", outcome: { verdict: "improved", change_pct: { median_views: 24 }, posts_after: 3 } });
    const open = rec({ source: "claude", sources: [{ topic: "Shorts hooks", url: "https://example.org/hooks", title: "Hook study" }] });
    mock({ "/api/analytics": () => ig({ reco: { ready: true, findings: 1, notes: 2, open: [open], done: [done], dismissed: [], ask: { running: false, rc: 1, tail: "claude: rate limited" } } }) });
    at("/studio/analytics?tab=recommendations");
    expect(await screen.findByText(/1 open finding/)).toHaveTextContent("2 market notes"); expect(screen.getByRole("heading", { name: "The last Claude run did not finish" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Hook study" })).toHaveAttribute("href", "https://example.org/hooks"); expect(screen.getByText("Claude")).toBeInTheDocument();
    fireEvent.click(within(screen.getByRole("group", { name: "Recommendation status" })).getByRole("button", { name: /^Done/ })); expect(await screen.findByText("improved")).toBeInTheDocument(); expect(screen.getByText(/median views \+24%\. 3 posts since/)).toBeInTheDocument();
  });
  it("tells you how to start when nothing is collected, and when YouTube shows public counts only", async () => {
    mock({ "/api/analytics": () => ({ empty: true, reason: "no_data", db: "/data/analytics" }) });
    at("/studio/analytics");
    expect(await screen.findByRole("heading", { name: "No Instagram data yet" })).toBeInTheDocument(); expect(screen.getByText(/Sign in to Instagram for the account in Settings/)).toBeInTheDocument();
    cleanup(); mock({ "/api/analytics/youtube": () => ({ ...yt(), analytics_ok: false }), "/api/analytics": () => ig() });
    at("/studio/analytics?platform=youtube"); expect(await screen.findByText(/Showing public counts only/)).toBeInTheDocument();
  });
  it("says why the audience and patterns are empty instead of showing blank cards", async () => {
    mock({ "/api/analytics": () => ig() });
    at("/studio/analytics");
    expect(await screen.findByText("Instagram shares audience data once the account has 100 followers.")).toBeInTheDocument(); expect(screen.getByText(/Patterns appear once at least 3 posts have numbers. Right now 1 does/)).toBeInTheDocument();
  });
});

describe("Studio > Analytics > Best time to publish", () => {
  it("shows the hours to post in Central Time, the weekdays and the next slots, above the peers", async () => {
    mock({ "/api/analytics": () => ig({ peers: { rows: [{ username: "peer1", followers: 900 }], own: [] } }) });
    at("/studio/analytics");
    const bt = await screen.findByRole("region", { name: "Best time to publish" });
    expect(within(bt).getByRole("img", { name: /music: best hours to post, Central Time: (6pm, 7pm|5pm, 6pm)/ })).toBeInTheDocument();   // 23:00 and 00:00 UTC: 6 and 7 pm in daylight time, 5 and 6 pm in standard time
    expect(bt).toHaveTextContent("Fri 100"); expect(within(bt).getByRole("link", { name: "Tue 6:00 PM CT · 97" })).toHaveAttribute("href", "/studio/schedule?open=1&type=music&at=2026-10-20T23%3A00%3A00Z");   // a slot opens the scheduler with that time expect(bt).toHaveTextContent("12 own posts · 140 peer posts");
    const peers = screen.getByRole("region", { name: /Peers/ });
    expect(bt.compareDocumentPosition(peers) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

const C3 = (p: number, n: number, x: number) => ({ positive: p, neutral: n, negative: x });
const SENT = { days: 30, totals: { ...C3(6, 3, 1), total: 10 }, daily: [{ day: "2026-10-17", ...C3(2, 1, 0) }, { day: "2026-10-18", ...C3(4, 2, 1) }],
  songs: [{ slug: "song-001", ...C3(5, 2, 1), total: 8 }], themes: [{ theme: "voice", n: 4, ...C3(4, 0, 0) }],
  best: [{ src: "youtube", text: "Beautiful voice", slug: "song-001", link: "https://www.youtube.com/watch?v=v1&lc=y1", conf: 0.9, at: "2026-10-18" }], worst: [{ src: "site", text: "Audio too low", slug: null, link: null, conf: 0.8, at: "2026-10-18" }],
  waiting: 12, running: false, last_run: { started_at: "2026-10-18T10:00:00Z", finished_at: "2026-10-18T10:01:00Z", scored: 40, usd: 0.03, error: null } };

describe("Studio > Analytics > Sentiment (NAV-68)", () => {
  it("shows how the audience feels, per song, themes and the strongest comments, and starts scoring in the background", async () => {
    const f = mock({ "/api/analytics/sentiment/run": () => ({ started: true }), "/api/analytics/sentiment": () => SENT, "/api/analytics": () => ig() });
    at("/studio/analytics?tab=sentiment");
    expect(await screen.findByRole("img", { name: "All comments: 60% positive, 30% neutral, 10% negative" })).toBeInTheDocument();
    expect(screen.getByText(/10 comments:/)).toBeInTheDocument(); expect(screen.getByText(/40 scored, about \$0\.03 of Claude use/)).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "8" })).toBeInTheDocument(); expect(screen.getByText("voice 4")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "open the post" })).toHaveAttribute("href", "https://www.youtube.com/watch?v=v1&lc=y1");
    fireEvent.click(screen.getByRole("button", { name: "Score new comments (12 waiting)" }));
    await waitFor(() => expect(f.mock.calls.some(([u, i]) => u === "/api/analytics/sentiment/run" && (i as RequestInit | undefined)?.method === "POST")).toBe(true));
    expect(await screen.findByText(/Scoring started/)).toBeInTheDocument();
  });
});

describe("Studio > Analytics > Visitors (NAV-33)", () => {
  it("shows today, 7 and 30 days, then songs, sources and devices for the chosen period", async () => {
    const f = mock({ "/api/site/visits": () => VISITS, "/api/analytics": () => ig() });
    at("/studio/analytics?tab=visitors&days=7");
    const today = await screen.findByLabelText("Today"); expect(today).toHaveTextContent("3 visitors, 4 page views"); expect(today).toHaveTextContent("2 plays, 3 min listened · 1 opened the account page");
    expect(screen.getByRole("link", { name: "Tere Hone Se" })).toHaveAttribute("href", "/studio/songs/song-001");
    expect(screen.getByRole("cell", { name: "YouTube" })).toBeInTheDocument(); expect(screen.getByRole("cell", { name: "Direct or an app" })).toBeInTheDocument(); expect(screen.getByRole("cell", { name: "Phone" })).toBeInTheDocument();
    expect(f.mock.calls.some(([u]) => u === "/api/site/visits?days=7")).toBe(true);
  });
});

describe("accessibility", () => {
  it("has no serious violations on the three tabs", async () => {
    for (const tab of ["analytics", "recommendations", "interactions", "visitors", "sentiment"]) {
      cleanup(); mock({ "/api/analytics/sentiment": () => SENT, "/api/site/visits": () => VISITS, "/api/analytics": () => ig(), "/api/replies": () => ({ items: [{ comment_id: "u", username: "@v", text: "hi", posted_at: "2026-10-13T06:58:29Z", post_id: "v", post: "P", account: "a", link: "https://x", reply: null }] }) });
      at(`/studio/analytics?tab=${tab}`); await screen.findAllByRole("heading", { level: 1 }); await waitFor(() => expect(screen.queryByText("Loading…")).toBeNull());
      await screen.findByRole("tabpanel"); await new Promise((r) => setTimeout(r, 20));
      const r = await axe.run(document.body, { rules: { "color-contrast": { enabled: false } } });
      expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${tab} ${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    }
  });
});
