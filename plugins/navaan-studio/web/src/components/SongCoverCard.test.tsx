import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SongDetail } from "../lib/api";
import { SongCoverCard } from "./SongCoverCard";

const d = (cover: Partial<NonNullable<SongDetail["cover"]>> = {}) => ({ slug: "song-001", files: {}, cover: { prompt: "Modern cover art for Tere Hone Se, one strong form.", default: "Modern cover art for Tere Hone Se, one strong form.", has: false, v: 0, art: false, in_bucket: false, published: false, usd: 0.04, quality: "low", key: true, ...cover } }) as unknown as SongDetail;
const ok = () => Promise.resolve(new Response("{}", { headers: { "Content-Type": "application/json" } }));
const body = (f: ReturnType<typeof vi.fn>, i = 0) => JSON.parse(String((f.mock.calls[i] as unknown as [string, RequestInit])[1].body));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("SongCoverCard", () => {
  it("shows the prompt and the cost, sends the edited prompt, and offers a free title redraw only once there is art", async () => {
    const f = vi.fn(ok); vi.stubGlobal("fetch", f); const done = vi.fn();
    const { rerender } = render(<SongCoverCard d={d()} done={done} />);
    const box = screen.getByLabelText(/Prompt for the cover art/) as HTMLTextAreaElement; expect(box.value).toContain("Tere Hone Se");
    fireEvent.change(box, { target: { value: "A lantern on a quiet river, square cover art." } });
    fireEvent.click(screen.getByRole("button", { name: "Make cover (about $0.04)" }));
    await waitFor(() => expect(f).toHaveBeenCalled());
    expect((f.mock.calls[0] as unknown as [string])[0]).toBe("/api/cover/generate"); expect(body(f)).toEqual({ slug: "song-001", prompt: "A lantern on a quiet river, square cover art." });
    await waitFor(() => expect(done).toHaveBeenCalled()); expect(screen.queryByRole("button", { name: /Redraw the title/ })).toBeNull();
    rerender(<SongCoverCard d={d({ has: true, art: true, v: 5 })} done={done} />);
    expect(screen.getByRole("button", { name: "Redraw the title (free)" })).toBeInTheDocument(); expect(screen.getByAltText("Cover")).toBeInTheDocument(); expect(screen.getByRole("button", { name: "Make a new cover (about $0.04)" })).toBeInTheDocument();
  });
  it("says when the cover is not on the site and saves it with one free button; nothing to save once it is", async () => {
    const f = vi.fn(ok); vi.stubGlobal("fetch", f); const done = vi.fn();
    const { rerender } = render(<SongCoverCard d={d({ has: true, art: true, in_bucket: true, published: false })} done={done} />);
    expect(screen.getByText(/not on the site yet/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save for the site" }));
    await waitFor(() => expect(f).toHaveBeenCalled()); expect((f.mock.calls[0] as unknown as [string])[0]).toBe("/api/cover/publish"); expect(body(f)).toEqual({ slug: "song-001" });
    rerender(<SongCoverCard d={d({ has: true, art: true, in_bucket: true, published: true })} done={done} />);
    expect(screen.queryByRole("button", { name: "Save for the site" })).toBeNull(); expect(screen.queryByText(/not on the site yet/)).toBeNull();
  });
  it("needs an OpenAI key and a real prompt to spend, and is quiet when the server sends no cover state", () => {
    const { rerender } = render(<SongCoverCard d={d({ key: false })} done={vi.fn()} />);
    expect(screen.getByText(/Paste an OpenAI key/)).toBeInTheDocument(); expect(screen.getByRole("button", { name: /Make cover/ })).toBeDisabled();
    rerender(<SongCoverCard d={{ slug: "song-001", files: {} } as unknown as SongDetail} done={vi.fn()} />); expect(screen.queryByRole("heading", { name: "Cover" })).toBeNull();
  });
});
