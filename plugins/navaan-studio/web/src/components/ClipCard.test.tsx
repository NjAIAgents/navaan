import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ClipCard } from "./ClipCard";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); Object.defineProperty(navigator, "share", { configurable: true, value: undefined }); Object.defineProperty(navigator, "canShare", { configurable: true, value: undefined }); });

describe("ClipCard", () => {
  it("makes a clip between the two points you choose, and shows it", async () => {
    const f = vi.fn(() => Promise.resolve(json({ token: "song-001-41-15", url: "/c/song-001-41-15.mp4", page: "https://navaan.online/c/song-001-41-15" }))); vi.stubGlobal("fetch", f);
    render(<ClipCard slug="song-001" title="Tere Hone Se" position={41.6} duration={200} />);
    fireEvent.click(screen.getByRole("button", { name: /Start where it is now \(0:41\)/ })); expect((screen.getByLabelText("Start at (seconds)") as HTMLInputElement).value).toBe("41");
    expect(screen.getByText("Clip from 0:41 to 1:11, 30 seconds of 3:20")).toBeInTheDocument();   // the length it had is kept
    fireEvent.change(screen.getByLabelText("End at (seconds)"), { target: { value: "56" } });
    fireEvent.click(screen.getByRole("button", { name: "Make the clip" }));
    expect(await screen.findByLabelText("Clip of Tere Hone Se")).toHaveAttribute("src", "/c/song-001-41-15.mp4");
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit]; expect(url).toBe("/api/clip"); expect(JSON.parse(String(init.body))).toEqual({ slug: "song-001", start: 41, length: 15 });
  });
  it("shares the video file through the phone's share sheet when it can, else the link, and shows the server's refusal", async () => {
    const share = vi.fn(() => Promise.resolve()); Object.defineProperty(navigator, "share", { configurable: true, value: share }); Object.defineProperty(navigator, "canShare", { configurable: true, value: () => true });
    const f = vi.fn((u: string) => Promise.resolve(u === "/api/clip" ? json({ token: "t", url: "/c/t.mp4", page: "https://navaan.online/c/t" }) : ({ blob: () => Promise.resolve(new Blob(["mp4"], { type: "video/mp4" })) } as unknown as Response)));   // not a real Response: node 22's undici hangs on .blob() of a jsdom Blob
    vi.stubGlobal("fetch", f);
    render(<ClipCard slug="song-001" title="Tere Hone Se" position={null} duration={0} />);
    expect(screen.queryByRole("button", { name: /Use where it is now/ })).toBeNull();   // nothing is playing, so no position to use
    fireEvent.click(screen.getByRole("button", { name: "Make the clip" }));
    const btn = await screen.findByRole("button", { name: "Share the clip" });
    await waitFor(() => expect(btn).toBeEnabled(), { timeout: 5000 });   // the blob fetch and File build can cross 1 s on a slow CI runner
    fireEvent.click(btn); expect(share).toHaveBeenCalledTimes(1);   // called inside the tap, nothing awaited first: an iPhone opens the sheet only then
    const arg = (share.mock.calls[0] as unknown as [{ files: File[]; text: string }])[0]; expect(arg.files[0].type).toBe("video/mp4"); expect(arg.text).toContain("https://navaan.online/c/t");   // the way back to the song travels with it
  });
  it("keeps Share off, and says why, until the clip has been fetched; if the fetch fails it shares the link", async () => {
    const share = vi.fn(() => Promise.resolve()); Object.defineProperty(navigator, "share", { configurable: true, value: share }); Object.defineProperty(navigator, "canShare", { configurable: true, value: () => true });
    let fail: () => void = () => {};
    vi.stubGlobal("fetch", vi.fn((u: string) => (u === "/api/clip" ? Promise.resolve(json({ token: "t", url: "/c/t.mp4", page: "https://navaan.online/c/t" })) : new Promise((_, rej) => { fail = () => rej(new Error("offline")); }))));
    render(<ClipCard slug="song-001" title="Tere Hone Se" position={null} duration={0} />);
    fireEvent.click(screen.getByRole("button", { name: "Make the clip" }));
    const btn = await screen.findByRole("button", { name: "Share the clip" }); expect(btn).toBeDisabled(); expect(screen.getByText(/Getting the clip ready/)).toBeInTheDocument();
    fail(); await waitFor(() => expect(btn).toBeEnabled()); fireEvent.click(btn);
    expect(share).toHaveBeenCalledTimes(1); expect((share.mock.calls[0] as unknown as [{ url?: string; files?: File[] }])[0]).toMatchObject({ url: "https://navaan.online/c/t" });   // no file: the link goes
  });
  it("tells the person why when the clip cannot be made", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(json({ error: "the clip must start before the end of the song (200 seconds long)" }, 400))));
    render(<ClipCard slug="song-001" title="Tere Hone Se" position={null} duration={0} />);
    fireEvent.click(screen.getByRole("button", { name: "Make the clip" })); expect(await screen.findByRole("alert")).toHaveTextContent("before the end of the song");
  });
  it("lets a visitor download the clip, copy a caption with the link and the tag, and says what to do on a computer", async () => {
    const write = vi.fn(() => Promise.resolve()); Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: write } });
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(json({ token: "t", url: "/c/t.mp4", page: "https://navaan.online/c/t" }))));
    render(<ClipCard slug="song-001" title="Tere Hone Se" position={null} duration={0} />);
    fireEvent.click(screen.getByRole("button", { name: "Make the clip" }));
    const dl = await screen.findByRole("link", { name: "Download the clip" }); expect(dl).toHaveAttribute("href", "/c/t.mp4"); expect(dl).toHaveAttribute("download", "song-001-clip.mp4");
    expect(screen.getByText(/On a computer: download the clip, then post it from the Instagram app/)).toBeInTheDocument();   // no share sheet here
    fireEvent.click(screen.getByRole("button", { name: "Copy caption" })); await waitFor(() => expect(write).toHaveBeenCalledWith("Tere Hone Se on NAVAAN. Hear the full song: https://navaan.online/c/t #NAVAAN #NewMusic"));
    expect(await screen.findByText("Caption copied.")).toBeInTheDocument();
  });
  it("does not show the computer hint where the phone's share sheet can take the video", async () => {
    Object.defineProperty(navigator, "canShare", { configurable: true, value: () => true });
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(json({ token: "t", url: "/c/t.mp4", page: "https://navaan.online/c/t" }))));
    render(<ClipCard slug="song-001" title="Tere Hone Se" position={null} duration={0} />);
    fireEvent.click(screen.getByRole("button", { name: "Make the clip" })); await screen.findByRole("button", { name: "Share the clip" });
    expect(screen.queryByText(/On a computer/)).toBeNull();
  });
  it("has two sliders that keep the clip between 5 and 90 seconds inside the song, one pushing the other, and number boxes when the length is not known", async () => {
    const f = vi.fn(() => Promise.resolve(json({ token: "song-001-90-90", url: "/c/song-001-90-90.mp4", page: "https://navaan.online/c/song-001-90-90" }))); vi.stubGlobal("fetch", f);
    const { unmount } = render(<ClipCard slug="song-001" title="Tere Hone Se" position={null} duration={200} />);
    const s = screen.getByRole("slider", { name: "Start at (seconds)" }) as HTMLInputElement; const e = screen.getByRole("slider", { name: "End at (seconds)" }) as HTMLInputElement;
    expect([s.max, e.min, e.max]).toEqual(["195", "5", "200"]);   // a clip is at least 5 seconds and ends inside the song
    fireEvent.change(s, { target: { value: "90" } }); expect(screen.getByText("Clip from 1:30 to 1:35, 5 seconds of 3:20")).toBeInTheDocument();   // the start passed the end: the end is pushed just ahead of it
    fireEvent.change(e, { target: { value: "190" } }); expect(screen.getByText("Clip from 1:40 to 3:10, 90 seconds of 3:20")).toBeInTheDocument();   // 90 seconds at most: the start is pushed
    fireEvent.change(s, { target: { value: "10" } }); expect(screen.getByText("Clip from 0:10 to 1:40, 90 seconds of 3:20")).toBeInTheDocument();   // and the end is pulled in
    fireEvent.change(e, { target: { value: "12" } }); expect(screen.getByText("Clip from 0:07 to 0:12, 5 seconds of 3:20")).toBeInTheDocument();   // never shorter than 5
    fireEvent.change(s, { target: { value: "90" } }); fireEvent.change(e, { target: { value: "180" } }); fireEvent.click(screen.getByRole("button", { name: "Make the clip" }));
    await waitFor(() => expect(f).toHaveBeenCalled()); expect(JSON.parse(String((f.mock.calls[0] as unknown as [string, RequestInit])[1].body))).toEqual({ slug: "song-001", start: 90, length: 90 });
    unmount(); render(<ClipCard slug="song-001" title="Tere Hone Se" position={null} duration={0} />);
    expect(screen.queryByRole("slider")).toBeNull(); expect(screen.getByRole("spinbutton", { name: "Start at (seconds)" })).toBeInTheDocument(); expect(screen.getByRole("spinbutton", { name: "End at (seconds)" })).toBeInTheDocument();
  });
});
