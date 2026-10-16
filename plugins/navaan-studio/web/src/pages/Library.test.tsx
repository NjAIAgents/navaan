import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json", "X-Request-Id": "req-7" } });
function mock(routes: Record<string, (init?: RequestInit) => unknown | Response>) {
  const f = vi.fn((url: string, init?: RequestInit) => { const k = Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => url === r || url.startsWith(r + "?")) ?? Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => url.startsWith(r)); const v = k ? routes[k](init) : { error: "no route " + url }; return Promise.resolve(v instanceof Response ? v : json(v, k ? 200 : 404)); });
  vi.stubGlobal("fetch", f); return f;
}
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
const posts = (f: ReturnType<typeof mock>, path: string) => f.mock.calls.filter(([u]) => u === path).map(([, i]) => JSON.parse(String(i?.body)));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const pl = (o: object = {}) => ({ id: "11111111-1111-1111-1111-111111111111", name: "Evening", description: "", visibility: "private", tracks: 2, updated_at: "2026-10-16T00:00:00Z", ...o });
const detail = (o: object = {}) => ({ id: "11111111-1111-1111-1111-111111111111", name: "Evening", description: "", visibility: "private", tracks: [{ slug: "song-001", title: "One", position: "a" }, { slug: "song-002", title: "Two", position: "b" }, { slug: "song-003", title: "Three", position: "c" }], ...o });

describe("Library", () => {
  it("lists playlists and saved songs and creates a playlist", async () => {
    let lists = [pl()];
    const f = mock({ "/api/playlists/create": () => { lists = [...lists, pl({ id: "22222222-2222-2222-2222-222222222222", name: "Road", tracks: 0 })]; return { id: "x" }; }, "/api/playlists": () => lists, "/api/library": () => ({ tracks: [{ slug: "song-002", title: "Two" }], albums: [], following: false }) });
    at("/library");
    expect(await screen.findByRole("link", { name: /Evening/ })).toHaveAttribute("href", "/library/playlists/11111111-1111-1111-1111-111111111111");
    expect(screen.getByRole("link", { name: /Two/ })).toHaveAttribute("href", "/song/song-002");
    fireEvent.change(screen.getByLabelText("New playlist name"), { target: { value: "Road" } }); fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("link", { name: /Road/ })).toBeInTheDocument(); expect(posts(f, "/api/playlists/create")).toEqual([{ name: "Road" }]);
  });
  it("shows the plan's limit message with a way to the plans when the server refuses", async () => {
    mock({ "/api/playlists/create": () => json({ error: "Your Free plan includes 3 playlists. A higher plan has more.", limit: 3, plan: "free", upgrade: "/app/plans" }, 403), "/api/playlists": () => [pl()], "/api/library": () => ({ tracks: [], albums: [], following: false }) });
    at("/library"); await screen.findByRole("link", { name: /Evening/ });
    fireEvent.change(screen.getByLabelText("New playlist name"), { target: { value: "A fourth" } }); fireEvent.click(screen.getByRole("button", { name: "Create" }));
    const a = await screen.findByRole("alert"); expect(a).toHaveTextContent("Your Free plan includes 3 playlists"); expect(within(a).getByRole("link", { name: /See the plans/ })).toHaveAttribute("href", "/plans");
  });
});

describe("a playlist", () => {
  const setup = () => mock({ "/api/playlists/move": () => ({ ok: true }), "/api/playlists/remove": () => ({ ok: true }), "/api/playlists/update": () => ({ ok: true }), "/api/playlists/delete": () => ({ ok: true }), "/api/playlists/1": () => detail(), "/api/library": () => ({ tracks: [], albums: [], following: false }), "/api/playlists": () => [pl()] });
  it("moves a song up and down by saying which song it goes after", async () => {
    const f = setup(); at("/library/playlists/11111111-1111-1111-1111-111111111111");
    await screen.findByRole("heading", { name: "Evening", level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Move Three up" })); await waitFor(() => expect(posts(f, "/api/playlists/move")).toHaveLength(1));
    expect(posts(f, "/api/playlists/move")[0]).toMatchObject({ slug: "song-003", after: "song-001" });          // up one: after the song two above
    fireEvent.click(screen.getByRole("button", { name: "Move Two up" })); await waitFor(() => expect(posts(f, "/api/playlists/move")).toHaveLength(2));
    expect(posts(f, "/api/playlists/move")[1]).toMatchObject({ slug: "song-002", after: "" });                 // to the top
    fireEvent.click(screen.getByRole("button", { name: "Move One down" })); await waitFor(() => expect(posts(f, "/api/playlists/move")).toHaveLength(3));
    expect(posts(f, "/api/playlists/move")[2]).toMatchObject({ slug: "song-001", after: "song-002" });
    expect(screen.getByRole("button", { name: "Move One up" })).toBeDisabled(); expect(screen.getByRole("button", { name: "Move Three down" })).toBeDisabled();
  });
  it("removes a song, renames, and asks before deleting", async () => {
    const f = setup(); at("/library/playlists/11111111-1111-1111-1111-111111111111");
    await screen.findByRole("heading", { name: "Evening", level: 1 });
    fireEvent.click(screen.getByRole("button", { name: /Remove Two/ })); await waitFor(() => expect(posts(f, "/api/playlists/remove")).toEqual([{ id: "11111111-1111-1111-1111-111111111111", slug: "song-002" }]));
    fireEvent.change(screen.getByLabelText("Playlist name"), { target: { value: "Night" } }); fireEvent.click(screen.getByRole("button", { name: "Rename" }));
    await waitFor(() => expect(posts(f, "/api/playlists/update")).toEqual([{ id: "11111111-1111-1111-1111-111111111111", name: "Night" }]));
    fireEvent.click(screen.getByRole("button", { name: "Delete playlist" })); expect(posts(f, "/api/playlists/delete")).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete" })); await waitFor(() => expect(posts(f, "/api/playlists/delete")).toHaveLength(1));
  });
});

describe("Plans", () => {
  const plans = { plans: [{ key: "free", name: "Free", price_minor: null, currency: null, interval: null, buyable: false, entitlements: [{ feature: "playlists.max", enabled: true, limit: 3 }, { feature: "offline", enabled: false, limit: null }] },
    { key: "premium", name: "Premium", price_minor: null, currency: null, interval: null, buyable: false, entitlements: [{ feature: "playlists.max", enabled: true, limit: null }, { feature: "offline", enabled: true, limit: null }] }],
    mine: { plan: { key: "free", name: "Free", status: "active" }, entitlements: { "playlists.max": { enabled: true, limit: 3 } }, unlimited: false, usage: { playlists: 2 } } };
  it("compares the plans from the data and says how much of yours is used", async () => {
    mock({ "/api/plans": () => plans }); at("/plans");
    expect(await screen.findByText(/2 of 3 playlists used/)).toBeInTheDocument();
    const row = screen.getByRole("rowheader", { name: "Playlists" }).closest("tr")!; expect(row).toHaveTextContent("Up to 3"); expect(row).toHaveTextContent("Included");
    expect(screen.getByRole("rowheader", { name: "Listen offline" }).closest("tr")).toHaveTextContent("Not included"); expect(screen.getByText(/Premium cannot be bought yet/)).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Free \(yours\)/ })).toBeInTheDocument();
  });
  it("tells the owner there are no limits", async () => { mock({ "/api/plans": () => ({ ...plans, mine: { ...plans.mine, unlimited: true } }) }); at("/plans"); expect(await screen.findByText(/no limits apply/)).toBeInTheDocument(); });
});

describe("keeping a published song", () => {
  const song = { slug: "song-001", steps: [], next: { type: "done" }, text: { "title.txt": "Tere Hone Se" }, meta: { type: "music", state: "published", history: [] }, approvals: {}, job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "" };
  it("saves it and adds it to a playlist, showing the server's message when it cannot", async () => {
    let n = 0;
    const f = mock({ "/api/library/save": () => ({ ok: true }), "/api/playlists/add": () => (++n === 1 ? { ok: true } : json({ error: "this track is already in the playlist" }, 400)), "/api/playlists": () => [pl()], "/api/library": () => ({ tracks: [], albums: [], following: false }), "/api/song/": () => song });
    at("/studio/songs/song-001");
    fireEvent.click(await screen.findByRole("button", { name: "Save song" })); await screen.findByRole("button", { name: "Saved" }); expect(posts(f, "/api/library/save")).toEqual([{ kind: "track", slug: "song-001", on: true }]);
    fireEvent.click(await screen.findByRole("button", { name: "Add to playlist" })); expect(await screen.findByText('Added to "Evening".')).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add to playlist" })); expect(await screen.findByText(/already in the playlist/)).toBeInTheDocument();
  });
});

describe("accessibility", () => {
  it("has no serious violations on Library, a playlist and Plans", async () => {
    for (const path of ["/library", "/library/playlists/11111111-1111-1111-1111-111111111111", "/plans"]) {
      cleanup(); mock({ "/api/playlists/1": () => detail(), "/api/playlists": () => [pl()], "/api/library": () => ({ tracks: [{ slug: "song-002", title: "Two" }], albums: [], following: false }),
        "/api/plans": () => ({ plans: [{ key: "free", name: "Free", price_minor: null, currency: null, interval: null, buyable: false, entitlements: [{ feature: "playlists.max", enabled: true, limit: 3 }] }], mine: { plan: { key: "free", name: "Free", status: "active" }, entitlements: {}, unlimited: false, usage: { playlists: 1 } } }) });
      at(path); await screen.findAllByRole("heading", { level: 1 }); await waitFor(() => expect(screen.queryByText("Loading…")).toBeNull()); await new Promise((r) => setTimeout(r, 30));
      const r = await axe.run(document.body, { rules: { "color-contrast": { enabled: false } } });
      expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${path} ${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    }
  });
});
