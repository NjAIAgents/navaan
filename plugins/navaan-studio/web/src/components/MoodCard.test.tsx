import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SongDetail } from "../lib/api";
import { MoodCard } from "./MoodCard";

const d = (mood?: string) => ({ slug: "song-001", meta: { type: "music", mood } }) as unknown as SongDetail;
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("MoodCard", () => {
  it("shows the current mood with its picture and saves a new one", async () => {
    const f = vi.fn(() => Promise.resolve(new Response("{}", { headers: { "Content-Type": "application/json" } }))); vi.stubGlobal("fetch", f); const done = vi.fn();
    render(<MoodCard d={d("dawn")} done={done} />);
    expect((screen.getByLabelText(/Picture behind the lyrics/) as HTMLSelectElement).value).toBe("dawn"); expect(screen.getByAltText("The dawn picture")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Picture behind the lyrics/), { target: { value: "dusk" } });
    await waitFor(() => expect(f).toHaveBeenCalled());
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit]; expect(url).toBe("/api/mood"); expect(JSON.parse(String(init.body))).toEqual({ slug: "song-001", mood: "dusk" });
    await waitFor(() => expect(done).toHaveBeenCalled());
  });
  it("starts with none chosen and no picture", () => {
    render(<MoodCard d={d()} done={vi.fn()} />);
    expect((screen.getByLabelText(/Picture behind the lyrics/) as HTMLSelectElement).value).toBe(""); expect(screen.queryByRole("img")).toBeNull();
  });
});
