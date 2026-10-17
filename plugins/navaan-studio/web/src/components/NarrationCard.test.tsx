import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SongDetail } from "../lib/api";
import { NarrationCard } from "./SongEditors";

const d = (n: Partial<NonNullable<SongDetail["narrate"]>> = {}) => ({ slug: "insp-001", files: {}, meta: { type: "inspiration" }, narrate: { on: false, voice: "frank", voices: { frank: "Frank (deep, wise)", nj: "NJ (my own voice)" }, estimate_s: 14.6, used_s: 12, cap_s: 1500, key: true, ...n } }) as unknown as SongDetail;
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("NarrationCard: narrate the quote with ElevenLabs", () => {
  it("offers both voices with Frank first, shows the estimate and the month, and turns the step on with the chosen voice", async () => {
    const f = vi.fn(() => Promise.resolve(new Response("{}", { headers: { "Content-Type": "application/json" } }))); vi.stubGlobal("fetch", f); const done = vi.fn();
    render(<NarrationCard d={d()} done={done} />);
    const v = screen.getByLabelText("Voice") as HTMLSelectElement; expect(v.value).toBe("frank"); expect(Array.from(v.options).map((o) => o.textContent)).toEqual(["Frank (deep, wise)", "NJ (my own voice)"]);
    expect(screen.getByText(/About 15 seconds of narration. This month 12 of 1500 seconds used/)).toBeInTheDocument();
    fireEvent.change(v, { target: { value: "nj" } }); fireEvent.click(screen.getByRole("button", { name: "Turn narration on" }));
    await waitFor(() => expect(f).toHaveBeenCalled());
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit]; expect(url).toBe("/api/narration/eleven"); expect(JSON.parse(String(init.body))).toEqual({ slug: "insp-001", on: true, voice: "nj" });
    await waitFor(() => expect(done).toHaveBeenCalled());
  });
  it("cannot be turned on without an ElevenLabs key, and can be turned off once on", () => {
    const { rerender } = render(<NarrationCard d={d({ key: false })} done={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Turn narration on" })).toBeDisabled(); expect(screen.getByText(/Paste an ElevenLabs key in Settings first/)).toBeInTheDocument();
    rerender(<NarrationCard d={d({ on: true })} done={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Skip narration for this short" })).toBeEnabled(); expect(screen.getByRole("status")).toHaveTextContent("Frank (deep, wise)");
  });
});
