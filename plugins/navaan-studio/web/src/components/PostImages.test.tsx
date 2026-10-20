import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PostImages } from "./PostImages";
import type { SongDetail } from "../lib/api";

afterEach(cleanup);
const MANIFEST = { cover: { devto: { file: "post_cover_devto.png", url: "https://navaan.online/img/blog/blog-001/post_cover_devto-1a2b3c4d.png" }, linkedin: { file: "post_cover_linkedin.png" } },
  inline: [{ id: "i1", kind: "figure", file: "post_fig_i1.png", alt: "How an answer is made", after: "Why it sounds sure" }, { id: "i2", kind: "picture", file: "post_pic_i2.jpg", alt: "A crossed-out answer", after: "What to do" }], notes: ["figure i3 was skipped: Remotion could not draw it"] };
const d = (text: Record<string, string>) => ({ slug: "blog-001", text, files: { "post_cover_devto.png": 11, "post_cover_linkedin.png": 12, "post_fig_i1.png": 13, "post_pic_i2.jpg": 14 } }) as unknown as SongDetail;

describe("The images of a blog post", () => {
  it("shows both covers and every image with its place, each with a download", () => {
    render(<PostImages d={d({ "post_images.json": JSON.stringify(MANIFEST) })} />);
    const box = screen.getByLabelText("The images of this post");
    expect(screen.getByAltText("The dev.to cover (1000 × 420)")).toHaveAttribute("src", "/media/blog-001/post_cover_devto.png?v=11"); expect(screen.getByAltText("The LinkedIn cover (1200 × 627)")).toHaveAttribute("src", "/media/blog-001/post_cover_linkedin.png?v=12");
    expect(screen.getByAltText("How an answer is made")).toHaveAttribute("src", "/media/blog-001/post_fig_i1.png?v=13"); expect(box).toHaveTextContent("Figure under “Why it sounds sure”"); expect(box).toHaveTextContent("Picture under “What to do”");
    expect(box.querySelectorAll("a[download]")).toHaveLength(4); expect(box).toHaveTextContent("already in the post's front matter"); expect(box).toHaveTextContent("figure i3 was skipped");
  });
  it("shows nothing before the images exist or when the file is not readable", () => {
    const { container, rerender } = render(<PostImages d={d({})} />); expect(container).toBeEmptyDOMElement();
    rerender(<PostImages d={d({ "post_images.json": "{not json" })} />); expect(container).toBeEmptyDOMElement();
    rerender(<PostImages d={d({ "post_images.json": JSON.stringify({ inline: [] }) })} />); expect(container).toBeEmptyDOMElement();
  });
});
