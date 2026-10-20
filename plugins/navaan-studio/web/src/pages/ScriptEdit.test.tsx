import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { OWNER } from "../components/Shell.test";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json", "X-Request-Id": "req-15" } });
function route(routes: Record<string, (init?: RequestInit) => unknown>) {
  const f = vi.fn((u: string, init?: RequestInit) => {
    if (u.startsWith("/api/me")) return Promise.resolve(json(OWNER));
    const k = Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => u === r || u.startsWith(r)); const v = k ? routes[k](init) : [];
    return Promise.resolve(v instanceof Response ? v : json(v));
  });
  vi.stubGlobal("fetch", f); return f;
}
const posts = (f: ReturnType<typeof route>, path: string) => f.mock.calls.filter(([u]) => u === path).map(([, i]) => JSON.parse(String(i?.body)));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const QUOTE = JSON.stringify({ text: "One. Two.", lines: ["One.", "Two."], captions: ["One", "*Two*"], pictures: ["p", "q"] });
const aha = (o: object = {}) => ({ slug: "aha-001", steps: [], next: { type: "gate", step: "quote", gate: "quote" }, gates: ["quote"], text: { "title.txt": "Confidence", "quote.json": QUOTE }, files: {}, meta: { type: "aha", state: "draft", history: [] }, approvals: {},
  job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "", ...o });
const at = () => render(<MemoryRouter initialEntries={["/studio/aha/aha-001"]}><App /></MemoryRouter>);

describe("Changing an Aha-lorithm script at its approval", () => {
  it("edits the words of each beat and saves them", async () => {
    const f = route({ "/api/aha/edit-script": () => ({ ok: true, started: false }), "/api/songs": () => [], "/api/song/": () => aha() });
    at(); fireEvent.click(await screen.findByText("Edit the words"));
    expect(screen.getByLabelText("Beat 1, spoken")).toHaveValue("One."); expect(screen.getByLabelText(/Beat 2, caption/)).toHaveValue("*Two*");
    expect(screen.getByRole("button", { name: "Save the words" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Beat 1, spoken"), { target: { value: "Uno." } }); fireEvent.change(screen.getByLabelText(/Beat 2, caption/), { target: { value: "*Dos*" } });
    fireEvent.click(screen.getByRole("button", { name: "Save the words" }));
    await waitFor(() => expect(posts(f, "/api/aha/edit-script")).toEqual([{ slug: "aha-001", lines: ["Uno.", "Two."], captions: ["One", "*Dos*"] }]));
    expect(await screen.findByRole("status")).toHaveTextContent("Saved. Approve the script");
  });

  it("replaces the script with the owner's own words, and says what happens", async () => {
    const f = route({ "/api/aha/replace-script": () => ({ ok: true, started: true }), "/api/songs": () => [], "/api/song/": () => aha() });
    at(); fireEvent.click(await screen.findByText("Use my own words")); expect(screen.getByText(/kept exactly as you write it/)).toBeInTheDocument();
    const btn = screen.getByRole("button", { name: "Make the script from my words" }); expect(btn).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Your words"), { target: { value: "My own first sentence.\nMy own second sentence." } }); expect(btn).toBeEnabled(); fireEvent.click(btn);
    await waitFor(() => expect(posts(f, "/api/aha/replace-script")).toEqual([{ slug: "aha-001", text: "My own first sentence.\nMy own second sentence." }]));
  });

  it("shows the refusal from the server and is not offered while a run is going, nor for other types", async () => {
    route({ "/api/aha/edit-script": () => json({ error: "Beat 2 has no caption." }, 400), "/api/songs": () => [], "/api/song/": () => aha() });
    at(); fireEvent.click(await screen.findByText("Edit the words")); fireEvent.change(screen.getByLabelText("Beat 1, spoken"), { target: { value: "Uno." } }); fireEvent.click(screen.getByRole("button", { name: "Save the words" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Beat 2 has no caption."); cleanup();
    route({ "/api/songs": () => [], "/api/song/": () => aha({ job: { running: true, queued: false, rc: null } }) });
    at(); expect(await screen.findByRole("heading", { name: "Confidence", level: 1 })).toBeInTheDocument(); expect(screen.queryByText("Edit the words")).toBeNull(); cleanup();
    route({ "/api/songs": () => [], "/api/song/": () => aha({ slug: "insp-001", meta: { type: "inspiration", state: "draft", history: [] } }) });
    render(<MemoryRouter initialEntries={["/studio/inspiration/insp-001"]}><App /></MemoryRouter>); expect(await screen.findByRole("heading", { name: "Confidence", level: 1 })).toBeInTheDocument(); expect(screen.queryByText("Edit the words")).toBeNull();
  });
});
