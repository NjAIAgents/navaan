import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { monthGrid } from "../lib/calendar";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
const row = (o: object) => ({ slug: "song-001", type: "music", title: "Tere Hone Se", state: "drafted", status: "approval", album: "", steps_done: 2, steps_total: 9, public: false, published: false, scheduled: "", next: { type: "gate", step: "suno", gate: "lyrics" }, ...o });
function mock(routes: Record<string, unknown>) {
  const f = vi.fn((url: string) => { const k = Object.keys(routes).find((r) => url.startsWith(r)); return Promise.resolve(k ? json(routes[k]) : json({ error: "no route " + url }, 404)); });
  vi.stubGlobal("fetch", f); return f;
}
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("month grid", () => {
  it("puts the 1st under the right weekday (Monday first) and fills whole weeks", () => {
    const oct = monthGrid(2026, 9);   // 1 Oct 2026 is a Thursday
    expect(oct.length).toBe(5); expect(oct.every((w) => w.length === 7)).toBe(true);
    expect(oct[0].findIndex((c) => c.inMonth)).toBe(3); expect(oct[0][3].date.getDate()).toBe(1);
    expect(oct[4][oct[4].length - 1].date.getTime()).toBeGreaterThanOrEqual(new Date(2026, 9, 31).getTime());
    const nov = monthGrid(2026, 10);  // starts on a Sunday: the last column
    expect(nov.length).toBe(6); expect(nov[0].findIndex((c) => c.inMonth)).toBe(6);
    expect(monthGrid(2027, 1).length).toBe(4);   // Feb 2027 starts on a Monday and has 28 days
    expect(monthGrid(2026, 11).flat().filter((c) => c.inMonth).length).toBe(31);
  });
});

describe("Studio > Approvals, Inspiration, Schedule", () => {
  it("Approvals groups everything waiting by what is asked, one action each", async () => {
    mock({ "/api/songs": [row({}), row({ slug: "insp-001", type: "inspiration", title: "Quote", next: { type: "gate", step: "quote", gate: "quote" } }), row({ slug: "song-002", title: "Other", next: { type: "gate", step: "x", gate: "lyrics" } }), row({ slug: "song-003", status: "done", next: { type: "done" } })] });
    at("/studio/approvals");
    const lyr = (await screen.findByRole("heading", { name: "Lyrics" })).closest("section")!;
    expect(within(lyr).getAllByRole("link", { name: /Review/ })).toHaveLength(2); expect(within(lyr).getAllByRole("link", { name: /Review/ })[0]).toHaveAttribute("href", "/studio/songs/song-001");
    const quo = screen.getByRole("heading", { name: "Quote" }).closest("section")!; expect(within(quo).getByRole("link", { name: /Review/ })).toHaveAttribute("href", "/studio/inspiration/insp-001");
    expect(screen.queryByText("song-003")).toBeNull();
  });
  it("Approvals says when nothing waits", async () => { mock({ "/api/songs": [] }); at("/studio/approvals"); expect(await screen.findByText("Nothing is waiting for you.")).toBeInTheDocument(); });
  it("Inspiration lists only inspiration and opens the item page", async () => {
    mock({ "/api/songs": [row({}), row({ slug: "insp-001", type: "inspiration", title: "Tired of being strong", next: { type: "gate", step: "quote", gate: "quote" } })] });
    at("/studio/inspiration");
    const link = await screen.findByRole("link", { name: /Tired of being strong/ }); expect(link).toHaveAttribute("href", "/studio/inspiration/insp-001"); expect(link).toHaveTextContent("Waiting for you: Quote");
    expect(screen.queryByText(/Tere Hone Se/)).toBeNull();
  });
  it("an inspiration item follows its own steps and goes back to Inspiration", async () => {
    mock({ "/api/song/": { slug: "insp-001", steps: [{ id: "quote", label: "q", kind: "claude", done: true, redo: true, restart: false, spends: false, status: "waiting for approval", needs_gate: "quote", scheduled_for: null }, { id: "typeset", label: "t", kind: "script", done: false, redo: true, restart: false, spends: false, status: "blocked", needs_gate: null, scheduled_for: null }], next: { type: "gate", step: "quote", gate: "quote" }, text: { "title.txt": "Tired of being strong", "quote.json": '{"quote":"x"}' }, meta: { type: "inspiration", state: "drafted", history: [] }, approvals: {}, job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "" } });
    at("/studio/inspiration/insp-001");
    expect(await screen.findByRole("heading", { name: "Quote" })).toBeInTheDocument(); expect(screen.getByText("Write the quote")).toBeInTheDocument(); expect(screen.getByText("Plan the typography")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Inspiration/ }).some((a) => a.className === "back" && a.getAttribute("href") === "/studio/inspiration")).toBe(true);
  });
  const entry = (o: object) => { const d = new Date(); d.setDate(15); d.setHours(12, 0, 0, 0); return { slug: "song-001", title: "Tere Hone Se", type: "music", platform: "YouTube", at: d.toISOString(), state: "scheduled", reason: "", ...o }; };
  it("Schedule shows each platform and time in the calendar and the list, and marks missed and blocked", async () => {
    mock({ "/api/schedule": [entry({}), entry({ platform: "Instagram", state: "blocked", reason: "waiting for approval: instagram_caption" }), entry({ slug: "insp-001", type: "inspiration", title: "Quote", state: "missed" })] });
    at("/studio/schedule");
    const table = await screen.findByRole("table"); expect(within(table).getAllByRole("columnheader")).toHaveLength(7);
    expect(within(table).getAllByRole("link")).toHaveLength(3);
    const list = screen.getByRole("heading", { name: "Day by day" }).closest("section")!;
    expect(within(list).getAllByRole("heading", { level: 3 })).toHaveLength(1);   // one day, one heading
    expect(within(list).getByText("Missed")).toBeInTheDocument(); expect(within(list).getByText("Blocked")).toBeInTheDocument(); expect(within(list).getByText("Scheduled")).toBeInTheDocument();
    expect(within(list).getByText(/waiting for approval: instagram_caption/)).toBeInTheDocument();
    expect(screen.getByText(/2 need a look/)).toBeInTheDocument();
    expect(within(list).getByRole("link", { name: /Quote/ })).toHaveAttribute("href", "/studio/inspiration/insp-001");
  });
  it("Schedule moves between months", async () => {
    mock({ "/api/schedule": [entry({})] }); at("/studio/schedule");
    await screen.findByRole("table"); expect(screen.getAllByRole("link", { name: /Tere Hone Se/ }).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Next month" }));
    await waitFor(() => expect(screen.getByText(/Nothing scheduled in/)).toBeInTheDocument()); expect(within(screen.getByRole("table")).queryAllByRole("link")).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Previous month" })); await waitFor(() => expect(screen.queryByText(/Nothing scheduled in/)).toBeNull());
  });
  it("has no serious accessibility violations on the three screens", async () => {
    for (const [path, routes] of [
      ["/studio/approvals", { "/api/songs": [row({})] }], ["/studio/inspiration", { "/api/songs": [row({ type: "inspiration" })] }], ["/studio/schedule", { "/api/schedule": [entry({}), entry({ state: "missed" })] }],
    ] as const) {
      cleanup(); mock(routes); at(path); await screen.findAllByRole("heading", { level: 1 }); await waitFor(() => expect(screen.queryByText("Loading…")).toBeNull());
      const r = await axe.run(document.body, { rules: { "color-contrast": { enabled: false } } });
      expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    }
  });
});
