import { describe, expect, it } from "vitest";
import { frontMatter, stripMarkers, toHtml, toPlain } from "./markdown";

describe("The blog markdown reader", () => {
  it("escapes any markup in a draft and keeps only http(s) links", () => {
    const h = toHtml("Hello <script>alert(1)</script> & [bad](javascript:alert(1)) and [good](https://example.org/a?b=1&c=2) and ![pic](https://x.test/p.png)");
    expect(h).not.toContain("<script"); expect(h).toContain("&lt;script&gt;"); expect(h).toContain("&amp;");
    expect(h).not.toContain("javascript:"); expect(h).toContain("bad"); expect(h).toContain('<a href="https://example.org/a?b=1&amp;c=2">good</a>'); expect(h).not.toContain("<img");
  });

  it("reads headings, emphasis, code, lists, quotes and paragraphs", () => {
    const h = toHtml("# Title\n\nSome **bold** and *soft* and `code` text.\n\n- one\n- two\n\n1. first\n2. second\n\n> quoted\n\n```js\nconst a = 1 < 2;\n```\n---\nEnd");
    expect(h).toContain("<h1>Title</h1>"); expect(h).toContain("<strong>bold</strong>"); expect(h).toContain("<em>soft</em>"); expect(h).toContain("<code>code</code>");
    expect(h).toContain("<ul><li>one</li><li>two</li></ul>"); expect(h).toContain("<ol><li>first</li><li>second</li></ol>"); expect(h).toContain("<blockquote><p>quoted</p></blockquote>");
    expect(h).toContain("<pre><code>const a = 1 &lt; 2;</code></pre>"); expect(h).toContain("<hr>"); expect(h).toContain("<p>End</p>");
  });

  it("splits dev.to front matter from the body and removes claim markers", () => {
    const fm = frontMatter('---\ntitle: "Why it is wrong"\ndescription: "One line"\ntags: ai, llm, testing\npublished: false\n---\n\nBody [c3] here.');
    expect(fm).toMatchObject({ title: "Why it is wrong", description: "One line", tags: ["ai", "llm", "testing"] }); expect(fm.body.trim()).toBe("Body [c3] here.");
    expect(stripMarkers("A fact [c3]. Another [c12], done.")).toBe("A fact. Another, done."); expect(frontMatter("no front matter").body).toBe("no front matter");
  });

  it("makes plain text for a site with no formatting", () => {
    expect(toPlain("## Heading\n\nText with **bold** and a [link](https://example.org).\n\n- item\n\n```\ncode\n```")).toBe("Heading\n\nText with bold and a link (https://example.org).\n\n• item\n\ncode");
  });
});
