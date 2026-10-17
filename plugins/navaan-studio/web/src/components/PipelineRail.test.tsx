import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SongDetail } from "../lib/api";
import { PipelineRail } from "./PipelineRail";

const step = (id: string, o: object = {}) => ({ id, label: id, kind: "script", done: false, redo: true, restart: false, spends: false, status: "ready", needs_gate: null, scheduled_for: null, ...o });
const d = (o: object = {}) => ({ slug: "insp-004", steps: [step("quote", { done: true, status: "done" }), step("narrate", { spends: true }), step("render", { status: "waiting for approval", done: true }), step("youtube_meta")], next: { type: "run", step: "narrate" }, failure: null, ...o }) as unknown as SongDetail;
afterEach(cleanup);

describe("PipelineRail", () => {
  it("lists every step in order with its state in words, the one you are at, and what waits for you", () => {
    render(<PipelineRail d={d()} act={vi.fn()} busy={false} />);
    const rows = screen.getAllByRole("listitem");
    expect(rows.map((r) => r.id)).toEqual(["step-quote", "step-narrate", "step-render", "step-youtube_meta"]);
    expect(rows[0]).toHaveTextContent("done: Write the quote"); expect(rows[1]).toHaveTextContent("now: Narrate the quote (ElevenLabs)"); expect(rows[1]).toHaveTextContent("spends credits");
    expect(rows[2]).toHaveTextContent("waiting for you: Render the video"); expect(rows[3]).toHaveTextContent("later: Write the YouTube text");
    expect(screen.getByText("2/4")).toBeInTheDocument();
  });
  it("marks the failed step and asks before redoing one", async () => {
    const act = vi.fn(() => Promise.resolve(true));
    render(<PipelineRail d={d({ failure: { step: "narrate", error: "x", ref: "r" } })} act={act} busy={false} />);
    expect(document.getElementById("step-narrate")).toHaveTextContent("failed: Narrate the quote");
    fireEvent.click(screen.getByRole("button", { name: "Redo Write the quote" })); expect(act).not.toHaveBeenCalled();   // a confirmation first
    fireEvent.click(screen.getByRole("button", { name: "Yes, redo it" })); await waitFor(() => expect(act).toHaveBeenCalledWith("/api/redo", { step: "quote" }));
  });
});
