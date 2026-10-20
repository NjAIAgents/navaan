import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Editor } from "@tiptap/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PostEditor } from "./PostEditor";

const RAW = '---\ntitle: "Why answers sound sure"\ndescription: "Confidence is not evidence"\ntags: ai, llm\npublished: false\ncover_image: https://x.test/c.png\n---\n\n## Why\n\nA claim [c1] with **weight**.\n\n- one\n- two\n';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const mount = (over: Partial<Parameters<typeof PostEditor>[0]> = {}) => {
  const posts: { path: string; body: Record<string, unknown> }[] = []; let editor: Editor | undefined;
  vi.stubGlobal("fetch", vi.fn(async (u: string, init?: RequestInit) => { posts.push({ path: u, body: JSON.parse(String(init?.body)) }); return new Response("{}", { status: 200, headers: { "Content-Type": "application/json", "X-Request-Id": "r" } }); }));
  const onSaved = vi.fn();
  render(<PostEditor slug="blog-001" file="devto.md" raw={RAW} devto label="dev.to" onSaved={onSaved} onReady={(e) => { editor = e; }} {...over} />);
  return { posts, onSaved, ed: () => editor! };
};

describe("The post editor", () => {
  it("shows the post formatted on a white page with the markers hidden, and the front matter as fields", async () => {
    mount(); await waitFor(() => expect(document.querySelector(".ProseMirror h2")).toHaveTextContent("Why"));
    const page = document.querySelector(".ProseMirror")!; expect(page).toHaveTextContent("A claim with weight."); expect(page).not.toHaveTextContent("[c1]"); expect(page.querySelector("strong")).toHaveTextContent("weight"); expect(page.querySelectorAll("li")).toHaveLength(2);
    expect(document.querySelector(".paper")).not.toBeNull(); expect(screen.getByLabelText("Title")).toHaveValue("Why answers sound sure"); expect(screen.getByLabelText(/^Description/)).toHaveValue("Confidence is not evidence");
    expect(screen.getByRole("button", { name: "Save dev.to" })).toBeDisabled();   // nothing has changed
  });

  it("saves an edit of the body back to the file, keeps the front matter lines it does not show, and drops the markers", async () => {
    const { posts, onSaved, ed } = mount(); await waitFor(() => expect(ed()).toBeDefined());
    ed().commands.focus("end"); ed().commands.insertContent("<p>Added sentence.</p>"); await waitFor(() => expect(screen.getByText("Unsaved changes")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Save dev.to" }));
    await waitFor(() => expect(posts).toHaveLength(1)); expect(posts[0].path).toBe("/api/save"); expect(posts[0].body).toMatchObject({ slug: "blog-001", file: "devto.md" });
    const text = String(posts[0].body.content); expect(text.startsWith('---\ntitle: "Why answers sound sure"\n')).toBe(true);
    for (const keep of ["published: false", "cover_image: https://x.test/c.png", "tags: ai, llm"]) expect(text).toContain(keep);
    expect(text).toContain("## Why\n"); expect(text).toContain("**weight**"); expect(text).toContain("- one\n- two"); expect(text).toContain("Added sentence."); expect(text).not.toContain("[c1]");
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
  });

  it("saves a changed title, description and tags into the front matter, and lowercases the tags", async () => {
    const { posts } = mount(); await screen.findByLabelText("Title");
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: 'Evidence, not "confidence"' } }); fireEvent.change(screen.getByLabelText(/^Tags/), { target: { value: "AI, Testing, " } });
    fireEvent.click(screen.getByRole("button", { name: "Save dev.to" })); await waitFor(() => expect(posts).toHaveLength(1));
    const text = String(posts[0].body.content); expect(text).toContain('title: "Evidence, not \\"confidence\\""'); expect(text).toContain("tags: ai, testing"); expect(text).toContain("published: false");
  });

  it("previews the post as readers will see it, and a LinkedIn article has no front matter fields", async () => {
    mount({ file: "linkedin_article.md", raw: "## Why it matters\n\nA claim [c1] with a [source](https://example.org).", devto: false, label: "LinkedIn article" });
    await waitFor(() => expect(document.querySelector(".ProseMirror h2")).toHaveTextContent("Why it matters")); expect(screen.queryByLabelText("Title")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    const pv = screen.getByLabelText("LinkedIn article, as it will look"); expect(pv.querySelector("a")).toHaveAttribute("href", "https://example.org"); expect(pv).not.toHaveTextContent("[c1]");
    expect(screen.queryByRole("button", { name: "Bold" })).toBeNull();   // the toolbar belongs to editing
  });

  it("formats with the toolbar, and a link or image needs a web address", async () => {
    const { ed } = mount(); await waitFor(() => expect(ed()).toBeDefined());
    ed().commands.selectAll(); fireEvent.click(screen.getByRole("button", { name: "Bold" })); expect(ed().isActive("bold")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Image" })); fireEvent.change(screen.getByLabelText("Image address"), { target: { value: "ftp://nope" } }); fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByRole("alert")).toHaveTextContent("https://");
    fireEvent.change(screen.getByLabelText("Image address"), { target: { value: "https://x.test/a.png" } }); fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(ed().getMarkdown()).toContain("![](https://x.test/a.png)");
  });

  it("shows the server's refusal and stays unsaved", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: "The dev.to title cannot be empty." }), { status: 400, headers: { "Content-Type": "application/json", "X-Request-Id": "r" } })));
    render(<PostEditor slug="blog-001" file="devto.md" raw={RAW} devto label="dev.to" onSaved={vi.fn()} />); await screen.findByLabelText("Title");
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "" } }); fireEvent.click(screen.getByRole("button", { name: "Save dev.to" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("title cannot be empty"); expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });
});
