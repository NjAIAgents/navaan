import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SongDetail } from "../lib/api";
import { PosterCard } from "./PosterCard";

const d = (poster: Partial<NonNullable<SongDetail["poster"]>> = {}) => ({ slug: "song-001", files: {}, poster: { style: "bold", styles: ["bold", "brush", "hand"], prompt: "A rainy window at dusk, warm light, portrait poster.", has: false, v: 0, usd: 0.07, quality: "high", key: true, ...poster } }) as unknown as SongDetail;
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("PosterCard", () => {
  it("shows the prompt and the cost, sends the edited prompt, and offers a free title redraw once a poster exists", async () => {
    const f = vi.fn(() => Promise.resolve(new Response("{}", { headers: { "Content-Type": "application/json" } }))); vi.stubGlobal("fetch", f);
    const done = vi.fn();
    const { rerender } = render(<PosterCard d={d()} done={done} />);
    const box = screen.getByLabelText(/Prompt for the art/) as HTMLTextAreaElement; expect(box.value).toContain("rainy window");
    fireEvent.change(box, { target: { value: "A lantern on a quiet river, portrait poster." } });
    fireEvent.click(screen.getByRole("button", { name: "Make poster (about $0.07)" }));
    await waitFor(() => expect(f).toHaveBeenCalled());
    expect(JSON.parse(String((f.mock.calls[0] as unknown as [string, RequestInit])[1].body))).toMatchObject({ slug: "song-001", style: "bold", prompt: "A lantern on a quiet river, portrait poster." });
    expect(screen.queryByRole("button", { name: /Redraw the title/ })).toBeNull();
    rerender(<PosterCard d={d({ has: true, v: 5 })} done={done} />);
    expect(screen.getByRole("button", { name: "Redraw the title (free)" })).toBeInTheDocument(); expect(screen.getByAltText("Poster")).toBeInTheDocument();
  });
  it("puts the poster on share links with one button, and says what is shown, stale, or not possible yet", async () => {
    const f = vi.fn(() => Promise.resolve(new Response("{}", { headers: { "Content-Type": "application/json" } }))); vi.stubGlobal("fetch", f); const done = vi.fn();
    const { rerender } = render(<PosterCard d={d({ has: true, v: 2, can_publish: true, published: false })} done={done} />);
    expect(screen.getByText(/shows the cover in its preview/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Use this poster for share links" }));
    await waitFor(() => expect(f).toHaveBeenCalled()); const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit]; expect(url).toBe("/api/poster/publish"); expect(JSON.parse(String(init.body))).toEqual({ slug: "song-001" });
    await waitFor(() => expect(done).toHaveBeenCalled());
    rerender(<PosterCard d={d({ has: true, v: 2, can_publish: true, published: true, stale: false })} done={done} />);
    expect(screen.getByRole("status")).toHaveTextContent("show this poster"); expect(screen.queryByRole("button", { name: /share links/ })).toBeNull();   // nothing to do
    rerender(<PosterCard d={d({ has: true, v: 3, can_publish: true, published: true, stale: true })} done={done} />);
    expect(screen.getByRole("button", { name: "Update the poster on share links" })).toBeEnabled(); expect(screen.getByRole("status")).toHaveTextContent("earlier one");
    rerender(<PosterCard d={d({ has: true, v: 3, can_publish: false, published: false })} done={done} />);
    expect(screen.getByRole("status")).toHaveTextContent("Put the song in the bucket first"); expect(screen.queryByRole("button", { name: /share links/ })).toBeNull();
    rerender(<PosterCard d={d()} done={done} />); expect(screen.queryByText("Share links")).toBeNull();   // no poster, nothing to publish
  });
  it("cannot generate without an OpenAI key", () => {
    render(<PosterCard d={d({ key: false })} done={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Make poster/ })).toBeDisabled(); expect(screen.getByRole("status")).toHaveTextContent("OpenAI key");
  });
  it("lets you return to the current suggested prompt even when an older prompt was saved, and the poster opens large", () => {
    const old = "An old saved prompt with a woman by a window, portrait poster."; const fresh = "A lone man seen from behind in silhouette, portrait poster.";
    render(<PosterCard d={d({ prompt: old, default: fresh, has: true, v: 3 })} done={vi.fn()} />);
    const box = screen.getByLabelText(/Prompt for the art/) as HTMLTextAreaElement; expect(box.value).toBe(old);   // what was saved is kept
    fireEvent.click(screen.getByRole("button", { name: "Reset to the suggested prompt" })); expect(box.value).toBe(fresh);
    expect(screen.queryByRole("button", { name: "Reset to the suggested prompt" })).toBeNull();   // already the suggestion
    fireEvent.click(screen.getByRole("button", { name: "Enlarge: Poster" })); expect(screen.getByRole("dialog", { name: "Poster" }).querySelector("img")).toHaveAttribute("src", "/media/song-001/poster_2x3.png?v=3");   // the full poster, not the 360 px copy
  });
});
