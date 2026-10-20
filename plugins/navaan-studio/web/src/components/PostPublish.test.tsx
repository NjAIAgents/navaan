import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PostPublish } from "./PostPublish";
import type { BlogPublish, SongDetail } from "../lib/api";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const base: BlogPublish = { devto: { key: true, posted: false, published: false, url: "" }, linkedin: { key: true, posted: false, url: "", ready: false, text: true } };
const d = (o: Partial<BlogPublish> = {}) => ({ slug: "blog-001", blog_publish: { ...base, ...o } }) as unknown as SongDetail;
function mount(target: "devto" | "linkedin_article" | "linkedin_post", det: SongDetail, reply: unknown = { ok: true, url: "https://dev.to/me/x", published: false }, dirty = false) {
  const posts: Record<string, unknown>[] = []; const onDone = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => { posts.push(JSON.parse(String(init?.body))); return new Response(JSON.stringify(reply), { status: reply && (reply as { error?: string }).error ? 502 : 200, headers: { "Content-Type": "application/json", "X-Request-Id": "r" } }); }));
  render(<MemoryRouter><PostPublish d={det} target={target} dirty={dirty} onDone={onDone} /></MemoryRouter>);
  return { posts, onDone };
}

describe("Posting from the Posts tab", () => {
  it("saves a draft on dev.to first, and going live needs a second deliberate press", async () => {
    const { posts, onDone } = mount("devto", d());
    fireEvent.click(screen.getByRole("button", { name: "Save as a draft on dev.to" })); await waitFor(() => expect(posts).toEqual([{ slug: "blog-001", target: "devto", publish: false }]));
    expect(await screen.findByText("Saved on dev.to as a draft.")).toBeInTheDocument(); await waitFor(() => expect(onDone).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "Publish on dev.to" })); expect(screen.getByText(/makes the article public on dev.to under your name/)).toBeInTheDocument(); expect(posts).toHaveLength(1);   // nothing yet
    fireEvent.click(screen.getByRole("button", { name: "Not yet" })); expect(screen.queryByRole("group", { name: "Confirm publishing" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Publish on dev.to" })); fireEvent.click(screen.getByRole("button", { name: "Yes, publish" })); await waitFor(() => expect(posts[1]).toEqual({ slug: "blog-001", target: "devto", publish: true }));
  });

  it("shows where it is, updates what is live without a publish button, and says when there is no key", () => {
    mount("devto", d({ devto: { key: true, posted: true, published: true, url: "https://dev.to/me/live" } }));
    expect(screen.getByRole("link", { name: "https://dev.to/me/live" })).toHaveAttribute("href", "https://dev.to/me/live"); expect(screen.getByText(/Live on dev.to/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Update the live article" })).toBeInTheDocument(); expect(screen.queryByRole("button", { name: "Publish on dev.to" })).toBeNull(); cleanup();
    mount("devto", d({ devto: { key: false, posted: false, published: false, url: "" } }));
    expect(screen.getByText(/Add your dev.to key in/)).toBeInTheDocument(); expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/studio/settings"); expect(screen.getByRole("button", { name: "Save as a draft on dev.to" })).toBeDisabled();
  });

  it("does not post unsaved edits, and shows the site's refusal", async () => {
    mount("devto", d(), { error: "dev.to refused the key (401). Paste it again in Settings." }, true);
    expect(screen.getByText(/You have unsaved changes: save them first/)).toBeInTheDocument(); expect(screen.getByRole("button", { name: "Save as a draft on dev.to" })).toBeDisabled(); cleanup();
    mount("devto", d(), { error: "dev.to refused the key (401). Paste it again in Settings." });
    fireEvent.click(screen.getByRole("button", { name: "Save as a draft on dev.to" })); expect(await screen.findByRole("alert")).toHaveTextContent("refused the key (401)");
  });

  it("posts to LinkedIn only once the dev.to article is live, after a confirmation, and once", async () => {
    mount("linkedin_post", d()); expect(screen.getByText("Publish the dev.to article first: the post links to it.")).toBeInTheDocument(); expect(screen.getByRole("button", { name: "Post to LinkedIn" })).toBeDisabled(); cleanup();
    const { posts } = mount("linkedin_post", d({ devto: { key: true, posted: true, published: true, url: "https://dev.to/me/live" }, linkedin: { key: true, posted: false, url: "", ready: true, text: true } }), { ok: true, url: "https://www.linkedin.com/feed/update/urn:li:share:1/" });
    fireEvent.click(screen.getByRole("button", { name: "Post to LinkedIn" })); expect(posts).toHaveLength(0); expect(screen.getByText(/posts to your LinkedIn profile, with the dev.to article as a link card/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Yes, post" })); await waitFor(() => expect(posts).toEqual([{ slug: "blog-001", target: "linkedin", publish: false }])); expect(await screen.findByText("Posted on LinkedIn.")).toBeInTheDocument(); cleanup();
    mount("linkedin_post", d({ devto: { key: true, posted: true, published: true, url: "u" }, linkedin: { key: true, posted: true, url: "https://www.linkedin.com/feed/update/urn:li:share:1/", ready: true, text: true } }));
    expect(screen.getByRole("link", { name: /linkedin.com\/feed\/update/ })).toBeInTheDocument(); expect(screen.queryByRole("button", { name: "Post to LinkedIn" })).toBeNull();
  });

  it("says plainly that a LinkedIn article cannot be posted from outside, and shows nothing for another kind of item", () => {
    mount("linkedin_article", d()); expect(screen.getByRole("note")).toHaveTextContent("LinkedIn has no way to post a long article from outside"); cleanup();
    const { container } = render(<MemoryRouter><PostPublish d={{ slug: "x" } as unknown as SongDetail} target="devto" onDone={vi.fn()} /></MemoryRouter>); expect(container).toBeEmptyDOMElement();
  });
});
