import { render, screen, within, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import App from "../App";

const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

describe("the shell", () => {
  it("has the four main areas in the sidebar and the tab bar, and marks the current one", () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } }))));
    at("/");
    for (const nav of screen.getAllByRole("navigation", { name: "Main" })) {
      for (const label of ["Home", "Studio", "Library", "Albums"]) expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
      expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
    }
  });
  it("shows the Studio sub-menu with Podcasts marked Soon", () => {
    at("/studio/songs");
    const side = screen.getByRole("complementary", { name: "Sidebar" });
    for (const label of ["Songs", "Inspiration", "Approvals", "Schedule", "Analytics"]) expect(within(side).getByRole("link", { name: label })).toBeInTheDocument();
    expect(within(side).getByRole("link", { name: /Podcasts/ })).toHaveTextContent("Soon");
  });
  it("a route without a screen yet links to the classic view", () => {
    at("/library");
    expect(screen.getByRole("link", { name: /Open in the classic view/ })).toHaveAttribute("href", "/legacy");
  });
  it("opens the account menu with the themes and closes on Escape", () => {
    at("/albums");
    fireEvent.click(screen.getAllByRole("button", { name: /Navjyot|Account menu/ })[0]);
    const dlg = screen.getByRole("dialog", { name: "Account menu" });
    for (const label of [/Midnight Cinema/, /Ivory & Gold/, /Match my device/, /Sign out/]) expect(within(dlg).getByRole("button", { name: label })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it("lists what needs you, what is in production and what is done", async () => {
    const rows = [
      { slug: "song-003", type: "music", title: "Tere Hone Se", state: "media_ready", status: "approval", album: "", steps_done: 8, steps_total: 14, public: false, published: false, scheduled: "", next: { type: "gate", gate: "publish_youtube" } },
      { slug: "song-001", type: "music", title: "Pehla", state: "published", status: "done", album: "", steps_done: 14, steps_total: 14, public: true, published: true, scheduled: "", next: { type: "done" } },
    ];
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify(rows), { status: 200, headers: { "Content-Type": "application/json" } }))));
    at("/");
    expect(await screen.findByText("Tere Hone Se")).toBeInTheDocument();
    expect(screen.getByText(/Waiting for you: publish youtube/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Tere Hone Se/ })).toHaveAttribute("href", "/legacy#/song/song-003");
    expect(screen.getByText("Nothing is being made right now.")).toBeInTheDocument();
  });
});
