---
name: blog-editor
description: Apply review_notes.md to both blog drafts, tighten the prose and keep every fact as checked, then record the edit in edit.json. Use for the edit step of a blog item.
---

# Blog editor

1. Read `review_notes.md`, `devto.md`, `linkedin_article.md` and `claims.json`.
2. Apply each note to its draft. Cut what does not serve the takeaway; shorten long sentences; keep code blocks working.
3. Facts do not change. Keep every claim's meaning and number exactly; do not add a fact that is not in `claims.json`, even if a note asks for one. Keep the `[c3]` claim markers: the humanizer's re-check still reads them.
4. Keep the dev.to front matter valid (title, description under 160 characters, at most 4 lowercase tags, `published: false`).
5. Write `edit.json`: `{"applied": ["note, in a few words"], "skipped": [{"note": "...", "why": "..."}], "at": "ISO time"}`. Write it last.
6. Do not touch `draft.json` or `factcheck.json`. Print how many notes you applied and skipped, then stop.
