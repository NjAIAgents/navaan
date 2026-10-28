---
name: blog-research
description: Research the blog topic the owner picked from primary sources and save the notes as research.md and every checkable claim as claims.json. Use for the research step of a blog item, after the topic approval.
---

# Blog research

Everything later rests on this step: the writer may only state what is in `claims.json`, and the fact check tests each claim against its source. You must actually search and open the pages.

1. Read `topics.json`: `chosen` is the topic (title, why_now, angle, audience, sources). Start from its sources.
2. Search the web (WebSearch, then WebFetch on the best hits). Prefer primary sources: the vendor's or project's own post, release notes, documentation, the paper, the standard, official statistics. Use a reputable outlet only for what has no primary source. Never cite an aggregator, a forum post or an AI summary as if it were primary.
3. Write `research.md`: what happened and when, how it works, what is new compared to before, the trade-offs and open questions, and who is affected. Under 1,500 words, with the source link after each point.
4. Write `claims.json`: every fact the post may state (numbers, dates, versions, names, how something works, what someone said).
   `{"claims": [{"id": "c1", "text": "the claim in one sentence", "source_url": "https://...", "evidence": "the sentence on that page that supports it, quoted", "primary": true}], "made_at": "ISO time"}`
   - `primary` is true only when the source is the original (the vendor, the project, the paper, the official body). A claim with only a secondary source keeps `primary: false`; a claim you could not source at all is left out.
   - Ids are unique (c1, c2, ...). Real URLs only, ones you opened.
5. Print how many claims you saved and how many are primary, then stop.

## A loop back from the fact check

If `research_more.md` is newer than `claims.json`, the fact check failed the statements it lists. Do only this, for each:
- `unsourced` (no marker): search for a primary source that says it. Found: add a claim with the next free id, worded as the source says it (not stronger than the draft's sentence allows). Not found: add nothing.
- `contradicted` or `unsupported` (it names its claim id): open the primary source and correct that claim (same id) to what the source actually says, or find a better primary source for it. If no source supports it, remove that claim.
- Keep every other claim and id as it is. Do not rewrite `research.md` (that would redo the outline).
- Save `claims.json` even when you found nothing, then print which statements now have a claim and which do not.
