---
name: blog-linkedin-post
description: Write the short LinkedIn post that announces a finished blog post and links to its dev.to article, as plain text in linkedin_post.md. Use for the linkedin_post step of a blog item.
---

# LinkedIn post

The post goes out on the owner's own profile, with the dev.to article as a link card under it. It is not the article: it is the reason to click.

1. Read `outline.md` (the takeaway), `devto.md` and `linkedin_article.md` (final), `claims.json`, and `navaan.config.json` (`blog.voice`, if set: write in that voice; else a working engineer talking to colleagues, first person, plain words).
2. Write `linkedin_post.md`, plain text only (LinkedIn shows no markdown: no `#` headings, no `**bold**`, no backticks):
   - Line 1: the hook, under 140 characters, so it shows before "see more". One surprising or useful claim, never a greeting and never "I'm excited to share".
   - Then three to five short lines or a short list (a dash or a number at the start of a line is fine), each one a thing the reader gets from the article. One idea per line, a blank line between blocks.
   - A closing question that invites a reply.
   - On its own line: `[ARTICLE_URL]` exactly. The studio puts the dev.to address there when it posts, so write no address yourself.
   - Last: three to five hashtags, `#CamelCase`, relevant to the post (not `#AI` alone).
3. 600 to 1,300 characters (the limit is 3,000). State only what `claims.json` supports: no number or study that is not in it, and none of the `[c3]` claim markers.
4. Print the post, then stop. Do not post anything: the owner posts it from the Posts tab, after the dev.to article is live.
