import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { OWNER } from "../components/Shell.test";

const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { "Content-Type": "application/json", "X-Request-Id": "req-14" } });
function route(routes: Record<string, (init?: RequestInit) => unknown>) {
  const f = vi.fn((u: string, init?: RequestInit) => {
    if (u.startsWith("/api/me")) return Promise.resolve(json(OWNER));
    const k = Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => u === r || u.startsWith(r));
    return Promise.resolve(json(k ? routes[k](init) : []));
  });
  vi.stubGlobal("fetch", f); return f;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const base = { steps: [], files: {}, approvals: {}, job: { running: false, queued: false, rc: null }, status_text: "", failure: null, question: null, needs_you: "" };
const DEVTO = '---\ntitle: "Why answers sound sure"\ndescription: "Confidence is not evidence"\ntags: ai, llm\npublished: false\n---\n\n## Why\n\nA claim [c1] with **weight**.';
const LI = "## Why it matters\n\nA claim [c1] with a [source](https://example.org).";
const blog = (text: Record<string, string> = {}, steps: unknown[] = [{ id: "edit", done: true }]) => ({ ...base, slug: "blog-001", steps, next: { type: "run", step: "archive" }, text: { "title.txt": "Why answers sound sure", ...text }, meta: { type: "blog", state: "draft", history: [] } });
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

describe("The finished blog post, one tab per destination", () => {
  it("opens on the posts once they are edited, with a tab for each destination whose file exists", async () => {
    route({ "/api/songs": () => [], "/api/song/": () => blog({ "devto.md": DEVTO, "linkedin_article.md": LI }) });
    at("/studio/blog/blog-001");
    expect(await screen.findByRole("tab", { name: "dev.to" })).toBeInTheDocument(); expect(screen.getByRole("tab", { name: "LinkedIn article" })).toBeInTheDocument(); expect(screen.queryByRole("tab", { name: "LinkedIn post" })).toBeNull();
    expect(screen.getByRole("tab", { name: "Posts" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByLabelText("Title")).toHaveValue("Why answers sound sure"); expect(screen.getByLabelText(/^Tags/)).toHaveValue("ai, llm");   // the front matter is three fields above the page
    await waitFor(() => expect(document.querySelector(".ProseMirror")).toHaveTextContent("A claim with weight."));   // the white page is the editor, markers hidden
    expect(document.querySelector(".ProseMirror")).not.toHaveTextContent("[c1]");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(screen.getByLabelText("dev.to, as it will look")).toHaveTextContent("A claim with weight."); expect(screen.getByLabelText("dev.to, as it will look")).not.toHaveTextContent("[c1]");
  });

  it("copies the markdown for dev.to (front matter kept, markers removed) and says it worked", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined); Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    route({ "/api/songs": () => [], "/api/song/": () => blog({ "devto.md": DEVTO }) });
    at("/studio/blog/blog-001");
    fireEvent.click(await screen.findByRole("button", { name: "Copy markdown" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1)); const sent = String(writeText.mock.calls[0][0]);
    expect(sent.startsWith("---\ntitle:")).toBe(true); expect(sent).toContain("A claim with **weight**."); expect(sent).not.toContain("[c1]");
    expect(await screen.findByRole("button", { name: "Copied" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Copy title" })); await waitFor(() => expect(writeText).toHaveBeenLastCalledWith("Why answers sound sure"));
    fireEvent.click(screen.getByRole("button", { name: "Copy tags" })); await waitFor(() => expect(writeText).toHaveBeenLastCalledWith("ai, llm"));
  });

  it("copies the LinkedIn article as rich text with a plain-text twin, or plain text alone", async () => {
    const write = vi.fn().mockResolvedValue(undefined), writeText = vi.fn().mockResolvedValue(undefined);
    class Item { constructor(public parts: Record<string, Blob>) {} }
    vi.stubGlobal("ClipboardItem", Item); Object.defineProperty(navigator, "clipboard", { value: { write, writeText }, configurable: true });
    route({ "/api/songs": () => [], "/api/song/": () => blog({ "devto.md": DEVTO, "linkedin_article.md": LI }) });
    at("/studio/blog/blog-001");
    fireEvent.click(await screen.findByRole("tab", { name: "LinkedIn article" }));
    fireEvent.click(await screen.findByRole("button", { name: "Copy formatted text" })); await waitFor(() => expect(write).toHaveBeenCalledTimes(1));
    const parts = (write.mock.calls[0][0][0] as Item).parts; expect(Object.keys(parts).sort()).toEqual(["text/html", "text/plain"]);
    expect(await parts["text/html"].text()).toContain('<h2>Why it matters</h2>'); expect(await parts["text/plain"].text()).toBe("Why it matters\n\nA claim with a source (https://example.org).");
    fireEvent.click(screen.getByRole("button", { name: "Copy plain text" })); await waitFor(() => expect(writeText).toHaveBeenCalledWith("Why it matters\n\nA claim with a source (https://example.org)."));
  });

  it("shows the text selected when the browser refuses to copy", async () => {
    Object.defineProperty(navigator, "clipboard", { value: { writeText: vi.fn().mockRejectedValue(new Error("no")) }, configurable: true });
    route({ "/api/songs": () => [], "/api/song/": () => blog({ "devto.md": DEVTO }) });
    at("/studio/blog/blog-001");
    fireEvent.click(await screen.findByRole("button", { name: "Copy markdown" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("did not allow copying"); expect((screen.getByLabelText("The text to copy") as HTMLTextAreaElement).value).toContain("A claim with **weight**.");
  });

  it("has no Posts tab until a draft exists, and a LinkedIn post tab appears when its file does", async () => {
    route({ "/api/songs": () => [], "/api/song/": () => blog({}) });
    at("/studio/blog/blog-001"); expect(await screen.findByRole("heading", { name: "Why answers sound sure", level: 1 })).toBeInTheDocument(); expect(screen.queryByRole("tab", { name: "Posts" })).toBeNull();
    cleanup();
    route({ "/api/songs": () => [], "/api/song/": () => blog({ "devto.md": DEVTO, "linkedin_post.md": "Short **post** text" }) });
    at("/studio/blog/blog-001"); fireEvent.click(await screen.findByRole("tab", { name: "LinkedIn post" }));
    expect(await screen.findByRole("button", { name: "Copy post" })).toBeInTheDocument();
  });
});
