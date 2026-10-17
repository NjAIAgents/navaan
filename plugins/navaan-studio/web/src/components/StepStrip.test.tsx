import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { SongDetail } from "../lib/api";
import { StepStrip } from "./StepStrip";

const step = (id: string, o: object = {}) => ({ id, label: id, kind: "script", done: false, redo: true, restart: false, spends: false, status: "ready", needs_gate: null, scheduled_for: null, ...o });
const d = (o: object) => ({ slug: "insp-004", steps: [step("quote", { done: true, status: "done" }), step("originality", { done: true, status: "done" }), step("narrate"), step("typeset"), step("render")], next: { type: "run", step: "narrate" }, failure: null, ...o }) as unknown as SongDetail;
afterEach(cleanup);

describe("StepStrip", () => {
  it("says how far along it is and marks done, now and later, each linking to its row", () => {
    render(<StepStrip d={d({})} />);
    expect(screen.getByText(/2 of 5 steps done · now: Narrate the quote/)).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Pipeline progress" });
    expect(within(nav).getByRole("link", { name: "Write the quote: done" })).toHaveAttribute("href", "#step-quote");
    expect(within(nav).getByRole("link", { name: /Narrate the quote .*: now/ })).toHaveAttribute("aria-current", "step");
    expect(within(nav).getByRole("link", { name: "Render the video: later" })).toBeInTheDocument();
  });
  it("shows a step that waits for you and a step that failed", () => {
    const { rerender } = render(<StepStrip d={d({ steps: [step("quote", { done: true, status: "waiting for approval", needs_gate: "quote" }), step("render")], next: { type: "gate", step: "quote", gate: "quote" } })} />);
    expect(screen.getByRole("link", { name: "Write the quote: waiting for you" })).toBeInTheDocument();
    rerender(<StepStrip d={d({ failure: { step: "narrate", error: "x", ref: "r" } })} />);
    expect(screen.getByRole("link", { name: /Narrate the quote .*: failed/ })).toBeInTheDocument();
  });
  it("says all done and shows nothing without steps", () => {
    const { container, rerender } = render(<StepStrip d={d({ next: { type: "done" }, steps: [step("quote", { done: true, status: "done" })] })} />);
    expect(screen.getByText(/1 of 1 steps done · all done/)).toBeInTheDocument();
    rerender(<StepStrip d={d({ steps: [] })} />); expect(container).toBeEmptyDOMElement();
  });
});
