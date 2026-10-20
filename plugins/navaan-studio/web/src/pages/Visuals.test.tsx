import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { OWNER } from "../components/Shell.test";

const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { "Content-Type": "application/json", "X-Request-Id": "req-13" } });
function route(routes: Record<string, () => unknown>) {
  const f = vi.fn((u: string) => {
    if (u.startsWith("/api/me")) return Promise.resolve(json(OWNER));
    const k = Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => u === r || u.startsWith(r));
    return Promise.resolve(json(k ? routes[k]() : []));
  });
  vi.stubGlobal("fetch", f);
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const detail = (text: Record<string, string>) => ({ slug: "aha-001", steps: [], next: { type: "gate", step: "quote", gate: "quote" }, gates: ["quote"], text: { "title.txt": "Confidence", ...text }, files: {}, meta: { type: "aha", state: "draft", history: [] }, approvals: {},
  job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "" });

describe("The visual plan at the script's approval", () => {
  it("is said in words beside the script, one line per beat, with the source of a figure", async () => {
    const plan = { beats: [{ line: 0, treatment: "hook" }, { line: 2, treatment: "stat", data: { value: 87, label: "x", source: "https://example.org/report" } }, { line: 3, treatment: "compare", data: {} }] };
    route({ "/api/songs": () => [], "/api/song/": () => detail({ "quote.json": JSON.stringify({ lines: ["a", "b", "c", "d"] }), "visual_plan.json": JSON.stringify(plan) }) });
    render(<MemoryRouter initialEntries={["/studio/aha/aha-001"]}><App /></MemoryRouter>);
    const box = await screen.findByLabelText("The visual plan in plain words");
    expect(box).toHaveTextContent("Beat 1: the words come in one by one over its picture");
    expect(box).toHaveTextContent("Beat 3: one number counting up, instead of a picture (source: https://example.org/report)");
    expect(box).toHaveTextContent("Beat 4: two things side by side, instead of a picture");
  });

  it("says the caption look of a narrated inspiration, and is absent without a plan", async () => {
    route({ "/api/songs": () => [], "/api/song/": () => ({ ...detail({ "quote.json": "{\"lines\": [\"a\"]}", "visual_plan.json": JSON.stringify({ caption: { treatment: "rise" } }) }), slug: "insp-001", meta: { type: "inspiration", state: "draft", history: [] } }) });
    render(<MemoryRouter initialEntries={["/studio/inspiration/insp-001"]}><App /></MemoryRouter>);
    expect(await screen.findByLabelText("The visual plan in plain words")).toHaveTextContent("Captions: words rise out of the dark as they are spoken");
    cleanup();
    route({ "/api/songs": () => [], "/api/song/": () => detail({ "quote.json": "{\"lines\": [\"a\"]}" }) });
    render(<MemoryRouter initialEntries={["/studio/aha/aha-001"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Confidence", level: 1 })).toBeInTheDocument(); expect(screen.queryByLabelText("The visual plan in plain words")).toBeNull();
  });
});
