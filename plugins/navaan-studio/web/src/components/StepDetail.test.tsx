import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SongDetail } from "../lib/api";
import { StepDetail } from "./StepDetail";

const step = (id: string, o: object = {}) => ({ id, label: id, kind: "script", done: false, redo: true, restart: false, spends: false, status: "ready", needs_gate: null, scheduled_for: null, made: [], texts: [], ...o });
const d = (o: object = {}) => ({ slug: "insp-004", next: { type: "run", step: "render" }, failure: null, logs: {}, steps: [
  step("background_prompt", { done: true, status: "done", texts: [{ name: "scenes/background.txt", text: "A quiet harbour at dusk, warm light." }] }),
  step("background", { done: true, status: "done", spends: true, spends_what: "OpenAI: the background picture", gate_before: "credits", made: [{ name: "background.png", size: 99 }, { name: "images~a.png", size: 5 }] }),
  step("narrate", { done: true, status: "done", made: [{ name: "voiceover.mp3", size: 7 }] }),
  step("render", { made: [] }),
], ...o }) as unknown as SongDetail;
afterEach(cleanup);

describe("StepDetail", () => {
  it("shows the prompt a finished step wrote, so it can be read after it ran", () => {
    render(<StepDetail d={d()} id="background_prompt" events={[]} onBack={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Write the background prompt" })).toBeInTheDocument(); expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByLabelText("scenes/background.txt")).toHaveTextContent("A quiet harbour at dusk, warm light.");
  });
  it("shows what a step made (pictures, audio) with the size in the address, what it spends, its log and its history", () => {
    const events = [{ at: "10/17/2026, 5:56 AM", text: "step background done (attempt 1)" }];
    render(<StepDetail d={d({ logs: { background: "wrote background.png" } })} id="background" events={events} onBack={vi.fn()} />);
    expect(screen.getByText("Spends: OpenAI: the background picture")).toBeInTheDocument(); expect(screen.getByText(/Needs your approval before it runs: Spending credits/)).toBeInTheDocument();
    expect(screen.getByAltText("background.png")).toHaveAttribute("src", "/media/insp-004/background.png?v=99"); expect(screen.getByAltText("images~a.png")).toHaveAttribute("src", "/media/insp-004/images~a.png?v=5");
    expect(screen.getByLabelText("Log of Make the background")).toHaveTextContent("wrote background.png"); expect(screen.getByText("step background done (attempt 1)")).toBeInTheDocument();
    cleanup(); render(<StepDetail d={d()} id="narrate" events={[]} onBack={vi.fn()} />);
    expect(screen.getByLabelText("voiceover.mp3").tagName).toBe("AUDIO");
  });
  it("says a step that has not run yet has nothing to show, and goes back", () => {
    const back = vi.fn(); render(<StepDetail d={d()} id="render" events={[]} onBack={back} />);
    expect(screen.getByText("Next")).toBeInTheDocument(); expect(screen.getByText(/has not run yet, so there is nothing to show/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Back to what needs you/ })); expect(back).toHaveBeenCalled();
  });
});
