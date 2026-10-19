---
name: blog-factcheck
description: Check every factual statement in devto.md and linkedin_article.md against its source and save the verdict as factcheck.json. Use for the fact-check step of a blog item, and again after the humanizer.
---

# Blog fact check

Nothing false goes out under the owner's name. You must open the sources; a verdict without reading them is worthless. Never round a doubt up to verified.

1. Read `claims.json`, `devto.md` and `linkedin_article.md`.
2. List every factual statement in both drafts: numbers, dates, versions, names, how something works, quotes. Each should carry a claim marker such as `[c3]`.
3. For each one:
   - a statement with no marker, or a marker not in `claims.json`: `unsourced`.
   - otherwise open the claim's `source_url` (WebFetch) and compare. The draft must say what the source says: no stronger wording, no changed number, no detail the source lacks. Then `verified`, or `contradicted` (the source says otherwise) or `unsupported` (the source does not say it). If the page will not load, search for the same source elsewhere; if you still cannot read it, `unsupported`.
4. Write `factcheck.json`:
   `{"verdict": "pass" | "fail", "claims": [{"id": "c3", "text": "the statement as the draft says it", "draft": "devto.md", "status": "verified|contradicted|unsupported|unsourced", "source": "https://...", "note": "what the source actually says"}], "checked_at": "ISO time"}`
   `verdict` is `pass` only when every statement is `verified`.
5. Do not edit the drafts. Print the verdict and the statements that failed, then stop.
