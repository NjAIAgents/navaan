import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ClipCard } from "./ClipCard";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); Object.defineProperty(navigator, "share", { configurable: true, value: undefined }); Object.defineProperty(navigator, "canShare", { configurable: true, value: undefined }); });

describe("ClipCard", () => {
  it("makes a clip from where you start, with the length you pick, and shows it", async () => {
    const f = vi.fn(() => Promise.resolve(json({ token: "song-001-42-30", url: "/c/song-001-42-30.mp4", page: "https://navaan.online/c/song-001-42-30" }))); vi.stubGlobal("fetch", f);
    render(<ClipCard slug="song-001" title="Tere Hone Se" position={41.6} duration={200} />);
    fireEvent.click(screen.getByRole("button", { name: /Use where it is now \(0:41\)/ })); expect((screen.getByLabelText("Start at (seconds)") as HTMLInputElement).value).toBe("41");
    fireEvent.change(screen.getByLabelText("Start at (seconds)"), { target: { value: "42" } });
    fireEvent.click(screen.getByRole("button", { name: "30 seconds" })); expect(screen.getByRole("button", { name: "30 seconds" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Make the clip" }));
    expect(await screen.findByLabelText("Clip of Tere Hone Se")).toHaveAttribute("src", "/c/song-001-42-30.mp4");
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit]; expect(url).toBe("/api/clip"); expect(JSON.parse(String(init.body))).toEqual({ slug: "song-001", start: 42, length: 30 });
  });
  it("shares the video file through the phone's share sheet when it can, else the link, and shows the server's refusal", async () => {
    const share = vi.fn(() => Promise.resolve()); Object.defineProperty(navigator, "share", { configurable: true, value: share }); Object.defineProperty(navigator, "canShare", { configurable: true, value: () => true });
    const f = vi.fn((u: string) => Promise.resolve(u === "/api/clip" ? json({ token: "t", url: "/c/t.mp4", page: "https://navaan.online/c/t" }) : ({ blob: () => Promise.resolve(new Blob(["mp4"], { type: "video/mp4" })) } as unknown as Response)));   // not a real Response: node 22's undici hangs on .blob() of a jsdom Blob
    vi.stubGlobal("fetch", f);
    render(<ClipCard slug="song-001" title="Tere Hone Se" position={null} duration={0} />);
    expect(screen.queryByRole("button", { name: /Use where it is now/ })).toBeNull();   // nothing is playing, so no position to use
    fireEvent.click(screen.getByRole("button", { name: "Make the clip" })); fireEvent.click(await screen.findByRole("button", { name: "Share the clip" }));
    await waitFor(() => expect(share).toHaveBeenCalled(), { timeout: 5000 });   // the blob fetch and File build can cross 1 s on a slow CI runner
    const arg = (share.mock.calls[0] as unknown as [{ files: File[]; text: string }])[0]; expect(arg.files[0].type).toBe("video/mp4"); expect(arg.text).toContain("https://navaan.online/c/t");   // the way back to the song travels with it
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
});
