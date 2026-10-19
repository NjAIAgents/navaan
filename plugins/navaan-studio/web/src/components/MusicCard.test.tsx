import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SongDetail } from "../lib/api";
import { MusicCard } from "./SongEditors";

const d = (music: SongDetail["music"] = null) => ({ slug: "insp-001", files: {}, meta: { type: "inspiration" }, music }) as unknown as SongDetail;
const ok = (b: unknown = {}) => vi.fn(() => Promise.resolve(new Response(JSON.stringify(b), { headers: { "Content-Type": "application/json" } })));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("MusicCard", () => {
  it("says there is no music, and sends the picked track with its own name", async () => {
    const f = ok({ ok: true, music: { file: "music_src.mp3" } }); vi.stubGlobal("fetch", f); const done = vi.fn();
    render(<MusicCard d={d()} done={done} />);
    expect(screen.getByText(/No background music: the short has the voice and the text only/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add the music" })).toBeDisabled();   // nothing picked yet
    fireEvent.change(screen.getByLabelText(/Music file/), { target: { files: [new File(["abc"], "Calm Piano.mp3", { type: "audio/mpeg" })] } });
    fireEvent.click(screen.getByRole("button", { name: "Add the music" }));
    await waitFor(() => expect(f).toHaveBeenCalled());
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit]; const body = JSON.parse(String(init.body));
    expect(url).toBe("/api/music/upload"); expect(body.slug).toBe("insp-001"); expect(body.name).toBe("Calm Piano.mp3"); expect(typeof body.audio).toBe("string");
    await waitFor(() => expect(done).toHaveBeenCalled());
  });
  it("shows the track in use, removes it, and tells an approved video what to redo", async () => {
    const f = ok({ ok: true, redo: "Plan the typography" }); vi.stubGlobal("fetch", f);
    render(<MusicCard d={d({ file: "music_src.mp3", name: "Calm Piano.mp3", added: "", seconds: 62 })} done={vi.fn()} />);
    expect(screen.getByText("Calm Piano.mp3")).toBeInTheDocument(); expect(screen.getByRole("button", { name: "Replace the music" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Remove the music" }));
    expect(await screen.findByText(/The video is approved, so it keeps its old sound. To use this, Redo "Plan the typography"/)).toBeInTheDocument();
    expect((f.mock.calls[0] as unknown as [string])[0]).toBe("/api/music/remove");
  });
  it("sets how loud the music sits under the voice on an Aha-lorithm short, and is not offered on inspiration", async () => {
    const f = ok({ ok: true, level: 35, redo: "" }); vi.stubGlobal("fetch", f);
    const aha = { slug: "aha-001", files: {}, meta: { type: "aha" }, music: null, music_level: 25 } as unknown as SongDetail;
    render(<MusicCard d={aha} done={async () => undefined} />);
    const s = screen.getByLabelText("Music volume under the voice: 25%"); expect(s).toHaveAttribute("aria-valuetext", "25 percent, about 12 dB under the voice");
    expect(screen.getByRole("button", { name: "Save the music volume" })).toBeDisabled();
    fireEvent.change(s, { target: { value: "35" } }); fireEvent.click(screen.getByRole("button", { name: "Save the music volume" }));
    await waitFor(() => expect(f).toHaveBeenCalledWith("/api/music/level", expect.objectContaining({ body: JSON.stringify({ slug: "aha-001", level: 35 }) })));
    cleanup(); render(<MusicCard d={{ ...d(), music_level: 35 } as SongDetail} done={async () => undefined} />); expect(screen.queryByLabelText(/Music volume under the voice/)).toBeNull();
  });
  it("shows the server's refusal", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({ error: "that file is not audio that can be played" }), { status: 400, headers: { "Content-Type": "application/json" } }))));
    render(<MusicCard d={d()} done={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Music file/), { target: { files: [new File(["x"], "a.mp3")] } }); fireEvent.click(screen.getByRole("button", { name: "Add the music" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not audio that can be played");
  });
});
