import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
export const OWNER = { user: "meera", roles: ["owner"], permissions: ["studio.access", "studio.settings", "library.view", "playlists.write", "account.manage"] };
export const LISTENER = { user: "asha", roles: ["listener"], permissions: ["library.view", "playlists.write", "account.manage"] };
export function stub(me: unknown, routes: Record<string, unknown> = {}) {
  const f = vi.fn((u: string) => { const k = Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => u.startsWith(r)); return Promise.resolve(u.startsWith("/api/me") ? json(me) : json(k ? routes[k] : [])); });
  vi.stubGlobal("fetch", f); return f;
}
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("the shell for the studio side", () => {
  it("has the four main areas in the sidebar and the tab bar, and marks the current one", async () => {
    stub(OWNER); at("/");
    await screen.findAllByRole("link", { name: "Studio" });
    for (const nav of screen.getAllByRole("navigation", { name: "Main" })) {
      for (const label of ["Home", "Studio", "Library", "Albums"]) expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
      expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
    }
  });
  it("shows the Studio sub-menu with Podcasts marked Soon", async () => {
    stub(OWNER); at("/studio/songs");
    const side = screen.getByRole("complementary", { name: "Sidebar" });
    for (const label of ["Songs", "Inspiration", "Approvals", "Schedule", "Analytics"]) expect(await within(side).findByRole("link", { name: label })).toBeInTheDocument();
    expect(within(side).getByRole("link", { name: /Podcasts/ })).toHaveTextContent("Soon");
  });
  it("credits NAVAAN Studio in the sidebar, with links to the privacy policy and the terms", async () => {
    stub(OWNER); at("/studio"); const side = await screen.findByRole("complementary", { name: "Sidebar" }); const f = within(side).getByText(/All rights reserved/);
    expect(f).toHaveTextContent(/NAVAAN Studio . © \d{4} NAVAAN Studio/); expect(f.textContent).not.toMatch(/NJ ?LABS/i);
    expect(within(f).getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy"); expect(within(f).getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms");
    expect(document.querySelector("main footer, .main > footer")).toBeNull();   // no footer under the page: it moved as the page filled in
  });
  it("the Studio page links to each area and does not send you to the classic view", async () => {
    stub(OWNER); at("/studio");
    expect(await screen.findByRole("link", { name: /Settings/ })).toHaveAttribute("href", "/studio/settings");
    for (const n of ["Songs", "Approvals", "Schedule", "Analytics", "Cloud"]) expect(screen.getAllByRole("link", { name: new RegExp(n) }).length).toBeGreaterThan(0);
    expect(screen.queryByText(/classic view has everything/)).toBeNull(); expect(screen.queryByText(/This screen is coming/)).toBeNull();
  });
  it("lists what needs you, what is in production and what is done", async () => {
    const rows = [
      { slug: "song-003", type: "music", title: "Tere Hone Se", state: "media_ready", status: "approval", album: "", steps_done: 8, steps_total: 14, public: false, published: false, scheduled: "", next: { type: "gate", gate: "publish_youtube" } },
      { slug: "song-001", type: "music", title: "Pehla", state: "published", status: "done", album: "", steps_done: 14, steps_total: 14, public: true, published: true, scheduled: "", next: { type: "done" } },
    ];
    stub(OWNER, { "/api/songs": rows }); at("/");
    expect(await screen.findByText("Tere Hone Se")).toBeInTheDocument();
    expect(screen.getByText(/Waiting for you: publish youtube/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Tere Hone Se/ })).toHaveAttribute("href", "/studio/songs/song-003");
    expect(screen.getByText("Nothing is being made right now.")).toBeInTheDocument();
  });
});

describe("the shell for a listener", () => {
  it("shows no Studio or Albums, no classic view, and Browse as Home", async () => {
    const rows = [{ slug: "song-001", title: "Tere Hone Se", language: "Hindi", genre: "Romantic", albums: [], licence: "confirmed", art: null }];
    stub(LISTENER, { "/api/catalog/tracks": rows }); at("/");
    expect(await screen.findByRole("heading", { name: "Browse", level: 1 })).toBeInTheDocument();
    for (const nav of screen.getAllByRole("navigation", { name: "Main" })) { expect(within(nav).queryByRole("link", { name: "Studio" })).toBeNull(); expect(within(nav).queryByRole("link", { name: "Albums" })).toBeNull(); expect(within(nav).getByRole("link", { name: "Library" })).toBeInTheDocument(); }
    expect(screen.queryByRole("link", { name: /Classic view/ })).toBeNull();
    expect((await screen.findAllByRole("link", { name: /Tere Hone Se/ }))[0]).toHaveAttribute("href", "/song/song-001");   // in Newest and under its language
    fireEvent.click(screen.getAllByRole("button", { name: /Account menu/ })[0]);
    const dlg = screen.getByRole("dialog", { name: "Account menu" }); expect(within(dlg).getByRole("link", { name: /Account/ })).toBeInTheDocument(); expect(within(dlg).queryByRole("link", { name: /Settings/ })).toBeNull(); expect(within(dlg).queryByRole("link", { name: /Classic view/ })).toBeNull();
  });
});

describe("the account menu", () => {
  it("opens with the themes and closes on Escape", async () => {
    stub(OWNER); at("/albums");
    fireEvent.click((await screen.findAllByRole("button", { name: /Account menu/ }))[0]);
    const dlg = screen.getByRole("dialog", { name: "Account menu" });
    for (const label of [/Midnight Cinema/, /Ivory & Gold/, /Match my device/, /Sign out/]) expect(within(dlg).getByRole("button", { name: label })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it("shows the version when the portal reports one", async () => {
    const f = vi.fn((u: string) => Promise.resolve(json(u.includes("/auth/state") ? { state: "authed", version: "9.9.9" } : u.startsWith("/api/me") ? OWNER : [])));
    vi.stubGlobal("fetch", f); at("/albums");
    await screen.findAllByRole("button", { name: /Account menu/ }); await new Promise((r) => setTimeout(r, 20));
    fireEvent.click(screen.getAllByRole("button", { name: /Account menu/ })[0]);
    const menu = await screen.findByRole("dialog", { name: "Account menu" }); expect(menu).toHaveTextContent(/NAVAAN Studio 9\.9\.9 . © \d{4} NAVAAN Studio/); expect(within(menu).getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy");
  });
  it("shows who is signed in from /api/me", async () => {
    stub(OWNER); at("/albums");
    expect(await screen.findAllByRole("button", { name: "Account menu, meera" })).not.toHaveLength(0);
  });
});
