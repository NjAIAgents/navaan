import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { OWNER } from "../components/Shell.test";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
const at = () => render(<MemoryRouter initialEntries={["/studio/cloud"]}><App /></MemoryRouter>);
const stub = (cloud: unknown, link?: () => Response) => { const f = vi.fn((u: string, _init?: RequestInit) => Promise.resolve(u.startsWith("/api/me") ? json(OWNER) : u.startsWith("/api/cloud/link") ? (link ? link() : json({ url: "https://bucket.example/x?sig=1" })) : u.startsWith("/api/cloud") ? json(cloud) : json([]))); vi.stubGlobal("fetch", f); return f; };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Cloud (NAV-27)", () => {
  it("lists archived songs, plays audio and shows pictures inside the app, edits words in the song editor, and downloads on request", async () => {
    const open = vi.fn(); vi.stubGlobal("open", open);
    const files = [{ name: "final.mp3", size: 5242880, key: "navaan/song-001/final.mp3" }, { name: "cover_1x1.png", size: 2048, key: "navaan/song-001/cover_1x1.png" }, { name: "lyrics.txt", size: 100, key: "navaan/song-001/lyrics.txt" }, { name: "meta.json", size: 100, key: "navaan/song-001/meta.json" }];
    const f = stub({ configured: true, provider: "oci", bucket: "navaan", region: "ap-mumbai-1", songs: [{ slug: "song-001", title: "Tere", files, bytes: 5242880, local: false, cleaned: true, uploaded_at: "2026-10-01", verified: true, youtube: [], instagram: "" }] });
    at(); expect(await screen.findByText("Tere")).toBeInTheDocument(); expect(screen.getByText(/Verified/)).toBeInTheDocument(); expect(screen.getByText(/Local copy cleaned/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Tere"));
    fireEvent.click(screen.getByRole("button", { name: "Play final.mp3 of song-001" })); const player = await screen.findByLabelText("final.mp3"); expect(player.tagName).toBe("AUDIO"); expect(player).toHaveAttribute("src", "https://bucket.example/x?sig=1"); expect(open).not.toHaveBeenCalled();   // inside the app, not a new tab
    fireEvent.click(screen.getByRole("button", { name: "Close final.mp3 of song-001" })); await waitFor(() => expect(screen.queryByLabelText("final.mp3")).toBeNull());
    fireEvent.click(screen.getByRole("button", { name: "View cover_1x1.png of song-001" })); expect((await screen.findByAltText("cover_1x1.png")).tagName).toBe("IMG");
    expect(screen.getByRole("link", { name: "Edit lyrics.txt of song-001" })).toHaveAttribute("href", "/studio/songs/song-001");   // words open in the editor
    expect(screen.queryByRole("button", { name: /^(Play|View|Watch) meta.json/ })).toBeNull(); expect(screen.queryByRole("button", { name: /^Open /i })).toBeNull();   // nothing is called Open when it only downloads
    fireEvent.click(screen.getByRole("button", { name: "Download meta.json of song-001" })); await waitFor(() => expect(open).toHaveBeenCalledWith("https://bucket.example/x?sig=1", "_blank", "noopener"));
    expect(JSON.parse(String(f.mock.calls.filter(([u]) => u === "/api/cloud/link").pop()![1]?.body)).key).toBe("navaan/song-001/meta.json");
  });
  it("says plainly when the cloud is not set up or not reachable", async () => {
    stub({ configured: false }); const { unmount } = at(); expect(await screen.findByText(/No cloud storage is set up/)).toBeInTheDocument(); unmount(); cleanup();
    stub({ configured: true, provider: "oci", bucket: "navaan", error: "oci: timed out" }); at(); expect(await screen.findByRole("alert")).toHaveTextContent("oci: timed out");
  });
  it("has no serious accessibility violations", async () => {
    stub({ configured: true, provider: "oci", bucket: "navaan", songs: [{ slug: "song-001", title: "Tere", files: [{ name: "a.mp3", size: 10, key: "k" }], bytes: 10, local: true, cleaned: false, verified: false, uploaded_at: "x", youtube: [], instagram: "" }] });
    const { container } = at(); await screen.findByText("Tere");
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } }); expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  });
});
