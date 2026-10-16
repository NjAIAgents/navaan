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
  it("lists archived songs with their verification and opens a file through a link", async () => {
    const open = vi.fn(); vi.stubGlobal("open", open);
    const f = stub({ configured: true, provider: "oci", bucket: "navaan", region: "ap-mumbai-1", songs: [{ slug: "song-001", title: "Tere", files: [{ name: "final.mp3", size: 5242880, key: "navaan/song-001/final.mp3" }], bytes: 5242880, local: false, cleaned: true, uploaded_at: "2026-10-01", verified: true, youtube: [], instagram: "" }] });
    at(); expect(await screen.findByText("Tere")).toBeInTheDocument(); expect(screen.getByText(/Verified/)).toBeInTheDocument(); expect(screen.getByText(/Local copy cleaned/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Tere")); fireEvent.click(screen.getByRole("button", { name: "Open final.mp3 of song-001" }));
    await waitFor(() => expect(open).toHaveBeenCalledWith("https://bucket.example/x?sig=1", "_blank", "noopener")); expect(JSON.parse(String(f.mock.calls.find(([u]) => u === "/api/cloud/link")![1]?.body)).key).toBe("navaan/song-001/final.mp3");
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
