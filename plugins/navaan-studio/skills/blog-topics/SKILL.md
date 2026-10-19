---
name: blog-topics
description: Suggest 5 trending blog topics for the owner's keyword, field or area, from trend_sources.json plus your own web search, and save them as topics.json. Use for the topics step of a blog item, before any research or writing.
---

# Blog topics

The owner writes under their own name for developers and tech readers on dev.to and LinkedIn. A topic is only worth suggesting if something real is happening now and the owner can add a view of their own.

1. Read the keyword, field or area under `## Idea` in `brief.md` and the audience under `## Options` (`auto` means you choose it). Read `trend_sources.json`: what Hacker News, dev.to and Google Trends show for the keyword in the last two weeks. Note which sources failed; do not invent their data.
2. Search the web yourself (WebSearch, then WebFetch on the best hits) for what changed recently in this area: releases, announcements, papers, incidents, debates. Prefer primary sources: the vendor's own post, the paper, the changelog, the official docs. You must actually search.
3. Pick exactly 5 distinct topics. Each must be:
   - timely: tied to something from the last few weeks, with a date you can show,
   - specific: one clear question or claim, not a whole field ("what X's new Y means for Z", not "AI in 2026"),
   - backed: at least one real source URL you opened, ideally one primary,
   - writable: enough substance for a 1,200 to 2,000 word post.
   Do not suggest two angles on the same news.
4. Write `topics.json`:
   `{"keyword": "...", "candidates": [{"title": "working title", "why_now": "what happened and when, one or two sentences", "angle": "the owner's take or the question the post answers", "audience": "who it is for", "signals": ["HN 412 points", "rising query 'x' +250%"], "sources": ["https://..."]}], "sources_failed": ["google_trends"], "chosen": null, "made_at": "ISO time"}`
   Exactly 5 candidates, best first. Real URLs only. Leave `chosen` as null: the owner picks.
5. Print the 5 titles, one line each, then stop. Do not approve the `topic` gate and do not start research.
