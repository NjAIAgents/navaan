---
name: blog-images
description: Plan the cover and two to four images for a finished blog post around its idea, as images.json (a cover, figures drawn from the post's own data, and at most one picture), costing nothing to plan. Use for the images_plan step of a blog item.
---

# Blog images

The cover and the figures are drawn by the studio (Remotion), not by an image model: the words in them are always right and they cost nothing. Only a `picture` is made by the OpenAI image API and costs money, behind an approval, so plan one only when a figure cannot do the job.

1. Read `outline.md` (the takeaway), `devto.md` and `linkedin_article.md` (as they are now: edited and humanized), and `claims.json`. Look at the `images.json` of the other `blog-*` items and pick a palette and motif that is not the same as the last two.
2. The cover: `{"title": "...", "kicker": "...", "chips": ["...", "..."], "palette": "...", "motif": "..."}`
   - `title`: the post's title as it will appear (at most 90 characters; shorter reads better on a small card).
   - `kicker`: the area in one to three words ("AI engineering", "Platform", "Data"). `chips`: two to four keywords from the post (at most 18 characters each), usually its own tags.
   - `palette` (the mood): `midnight` (serious, technical), `indigo` (AI and models), `forest` (growth, systems, calm), `ember` (incidents, risk, urgency), `ocean` (data, streams, cloud), `slate` (tooling, plain engineering), `paper` (opinion, essay, light), `mono` (stark, minimal).
   - `motif` (the idea as a shape): `nodes` (networks, agents, relationships), `grid` (data, infrastructure, platforms), `waves` (streams, signals, time series), `rings` (loops, cycles, retries, feedback), `blocks` (pipelines, stacks, layers), `stripes` (speed, migration, direction), `none` (a pure typographic cover).
3. Inline images, two to four, each helping one section: `"inline": [{"id": "i1", "kind": "figure", "treatment": "flow", "data": {...}, "title": "short caption", "alt": "what the image shows", "after": "exact heading text"}, ...]`
   - Prefer `kind: "figure"`: a treatment drawn as a still from data you write now. Use `flow` for a process, `compare` for a contrast, `checklist` or `timeline` for steps, `strike` for a word swapped for a better one, `chat` for an illustrative exchange, `bars` for more and less (no numbers in labels), and `stat`, `ring` or `chart` only for a number the post states: it needs `"source": "<the claim's source_url>"` and the number must be the one in `claims.json`. Never a made-up number and never the sample label. The data shapes and the length limits are the ones of the aha-script skill's visual plan (step 7); `blog_images.py check` tells you what does not fit.
   - `kind: "picture"` only when the section is better with an atmospheric or real-world image no figure can give, at most one per post: `{"id": "i3", "kind": "picture", "prompt": "20 to 80 words, a concrete scene from that section", "alt": "...", "after": "..."}`. It costs money.
   - `after`: the exact text of a heading in the post (without the `#`); the image goes after the first paragraph under it. `alt`: what the image shows, for a reader who cannot see it (5 to 160 characters). `id`: `i1`, `i2`, ...
   - Spread the images through the post; no two figures of the same treatment unless the content needs it. State only what `claims.json` supports.
4. If any `picture` is planned, add `"look"`: one art direction for them (15 to 40 words; a modern contemporary look, not painterly, no clip-art), different from other blog items.
5. Write `images.json`, then run `python3 <plugin>/scripts/blog_images.py check <slug>` and fix every problem it prints. Print the plan in a few lines (cover, each image and where it goes, whether anything costs money), then stop. Do not edit the drafts: the studio puts the images in.
