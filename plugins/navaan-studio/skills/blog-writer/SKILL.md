---
name: blog-writer
description: Write the dev.to post (devto.md) and the LinkedIn article adapted from it (linkedin_article.md) from outline.md and claims.json, or fix the claims listed in fix_notes.md. Use for the write step of a blog item.
---

# Blog writer

1. Read `outline.md`, `claims.json` and `topics.json` (`chosen`). If `fix_notes.md` is newer than `draft.json`, this is a fix round: change only the sentences with the claims it lists (correct each against its source in `claims.json`, or remove it) and leave the rest as it is.
2. State facts only from `claims.json`. After each sentence that uses a claim, put its marker `[c3]` (the fact check reads these; the editor removes them later). No facts from memory: if the post needs one that is not in `claims.json`, leave it out.
3. Write `devto.md`, the full post for developers, 1,200 to 2,000 words:
   - front matter first:
     ```
     ---
     title: "..."
     description: "one sentence, under 160 characters"
     tags: tag1, tag2, tag3, tag4
     published: false
     ---
     ```
     4 tags at most, lowercase, letters and digits only.
   - the hook, then the outline's sections as `##` headings, short paragraphs, code in fenced blocks with a language, links to the sources inline.
   - end with the takeaway and the outline's question.
4. Write `linkedin_article.md`, adapted from the post for LinkedIn readers (engineers, leads, managers): 800 to 1,200 words, the same claims and markers, plain headings, at most one short code block, the why before the how, no front matter.
5. Write `draft.json`: `{"round": 0 for the first draft or the fix round number, "claims_used": ["c1", ...], "at": "ISO time"}`. Write it last: it tells the pipeline the drafts are finished.
6. Print the word count of each draft, then stop.
