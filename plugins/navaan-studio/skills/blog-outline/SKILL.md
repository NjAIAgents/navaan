---
name: blog-outline
description: Outline a blog post from research.md and claims.json into outline.md, naming the claim ids each section relies on. Use for the outline step of a blog item.
---

# Blog outline

1. Read `topics.json` (`chosen`: title, angle, audience), `research.md` and `claims.json`.
2. Decide the one takeaway: the sentence a reader should remember. Every section must serve it.
3. Write `outline.md`:
   - `# Title` (the chosen title, sharpened if needed), then `Takeaway:` one sentence and `Audience:` one line.
   - A hook: the opening situation or question, in two lines.
   - 4 to 7 sections, each `## Heading`, two or three bullets on what it says, and `Claims: c1, c4` naming the claim ids it relies on. A section with no claims is opinion or explanation; say so with `Claims: none`.
   - Where a short code sample, command or config would help a developer, note it in the section.
   - An ending: the takeaway restated as advice, and one question that invites comments.
4. Use only claims that exist in `claims.json`. Do not add facts.
5. Print the title and the section headings, then stop.
