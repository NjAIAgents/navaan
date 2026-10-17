import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NewAlbum } from "./NewAlbum";
import { AlbumCoverCard } from "./AlbumCoverCard";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
const SONGS = [{ slug: "song-001", type: "music", title: "Tere Hone Se", published: true }, { slug: "song-002", type: "music", title: "Pata Hi Na Chala", published: false }, { slug: "insp-001", type: "inspiration", title: "A quote" }];
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("NewAlbum: pick songs, get names, create", () => {
  it("needs two songs for names and for create, suggests names, and creates the album with the songs in the picked order", async () => {
    const f = vi.fn((u: string, init?: RequestInit) => Promise.resolve(
      u === "/api/songs" ? json(SONGS) : u === "/api/albums/suggest" ? json({ names: [{ name: "Raat Ke Baad", why: "after the night" }, { name: "Dhoop", why: "light" }] })
      : u === "/api/albums/save" ? json({ slug: "raat-ke-baad" }) : u === "/api/albums/reorder" ? json({ tracks: [] }) : json({ ok: true, _: init?.method })));
    vi.stubGlobal("fetch", f);
    render(<MemoryRouter initialEntries={["/albums"]}><Routes><Route path="/albums" element={<NewAlbum onClose={vi.fn()} />} /><Route path="/albums/:slug" element={<p>album page</p>} /></Routes></MemoryRouter>);
    expect(await screen.findByLabelText(/Pata Hi Na Chala/)).toBeInTheDocument(); expect(screen.queryByLabelText(/A quote/)).toBeNull();   // songs only, not inspirations
    const names = screen.getByRole("button", { name: /Suggest names/ }); expect(names).toBeDisabled(); expect(screen.getByRole("button", { name: "Create album" })).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/Pata Hi Na Chala/)); fireEvent.click(screen.getByLabelText(/Tere Hone Se/)); expect(names).toBeEnabled();
    fireEvent.click(names); fireEvent.click(await screen.findByRole("button", { name: "Use the name Raat Ke Baad" }));
    expect((screen.getByLabelText("Album name") as HTMLInputElement).value).toBe("Raat Ke Baad");
    fireEvent.click(screen.getByRole("button", { name: "Create album" }));
    expect(await screen.findByText("album page")).toBeInTheDocument();
    const call = (u: string) => (f.mock.calls as unknown as [string, RequestInit][]).find(([x]) => x === u)![1];
    expect(JSON.parse(String(call("/api/albums/suggest").body))).toEqual({ tracks: ["song-002", "song-001"] });
    expect(JSON.parse(String(call("/api/albums/save").body))).toEqual({ title: "Raat Ke Baad", kind: "album" });
    expect(JSON.parse(String(call("/api/albums/reorder").body))).toEqual({ album: "raat-ke-baad", tracks: ["song-002", "song-001"] });
  });
});

describe("AlbumCoverCard", () => {
  it("shows the prompt and the cost, sends the edited prompt, and offers a free title redraw once a cover exists", async () => {
    const state = (has: boolean) => ({ prompt: "Professional square album cover for Raat Ke Baad.", has, v: 3, style: "bold", styles: ["bold", "brush", "hand"], usd: 0.04, key: true });
    let has = false;
    const f = vi.fn((u: string) => Promise.resolve(u.startsWith("/api/albums/cover?") ? json(state(has)) : json({ ok: true })));
    vi.stubGlobal("fetch", f);
    render(<AlbumCoverCard slug="raat-ke-baad" />);
    const box = (await screen.findByLabelText(/Prompt for the art/)) as HTMLTextAreaElement; expect(box.value).toContain("Raat Ke Baad");
    fireEvent.change(box, { target: { value: "A lantern on a quiet river, square cover art." } });
    fireEvent.click(screen.getByRole("button", { name: "Make cover (about $0.04)" }));
    await waitFor(() => expect((f.mock.calls as unknown as [string, RequestInit][]).some(([u, i]) => u === "/api/albums/cover" && JSON.parse(String(i.body)).prompt === "A lantern on a quiet river, square cover art.")).toBe(true));
    expect(screen.queryByAltText("Album cover")).toBeNull(); has = true;
    cleanup(); render(<AlbumCoverCard slug="raat-ke-baad" />);
    expect(await screen.findByAltText("Album cover")).toBeInTheDocument();
  });
});
