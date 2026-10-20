---
name: blog-humanizer
description: Rewrite the edited blog drafts so they read like one person wrote them, not a model, without changing a single fact, number, link, code block or claim marker, then record what changed in humanize.json. Use for the humanize step of a blog item.
---

# Blog humanizer

A post that reads like a model wrote it loses the reader in two lines. You change how it sounds, never what it says. A script checks afterwards (`humanize_before/` holds the text as it was); a changed fact, number, link, code block or claim marker fails the step.

1. Read `devto.md`, `linkedin_article.md` and `humanize_before/*` (the same text, kept for the check). If `navaan.config.json` has `blog.voice`, write in that voice; else write as a working engineer talking to a colleague: first person, plain words, an opinion where the evidence allows one.
2. Fix the habits that give a model away:
   - Openers and closers that announce themselves ("In today's fast-paced world", "Let's dive in", "In conclusion", "Here's the thing", "It's worth noting that").
   - Stock words: delve, leverage, utilize, robust, seamless, landscape, tapestry, game-changer, unlock, elevate, crucial, pivotal. Use the plain word.
   - The "not just X, but Y" and "it's not about X, it's about Y" frames, triple lists where two items would do, and every paragraph ending on a neat moral.
   - Em dashes used as a tic: keep one or two at most per post; use a full stop or a comma.
   - Rhythm: sentences all the same length. Mix short and long. Start some with "But", "And" or a number. Allow a sentence fragment now and then.
   - Vague claims ("many experts agree", "studies show") stay exactly as the evidence allows: do not invent a softer or stronger one.
   - Headings that read like a table of contents: make them say something.
3. Keep exactly, character for character: every `[c3]`-style claim marker, every number and unit, every web link, every fenced code block and inline code, the dev.to front matter (title and description may be tightened but must stay accurate; `published: false` stays; at most 4 lowercase tags), and every image line `![...](...)`. Do not add a fact, a source, a quote or an example that is not already there. Do not move a claim marker away from the sentence it supports.
4. Keep the length within 10% of the draft. Keep the LinkedIn article plain: no front matter.
5. Write `humanize.json`: `{"changed": ["what you changed, in a few words", "..."], "kept": "one line on what you left alone on purpose", "at": "ISO time"}`. Write it last. Do not touch `draft.json`, `factcheck.json`, `humanize_before/` or `claims.json`.
6. Print how many things you changed in each draft, then stop.
