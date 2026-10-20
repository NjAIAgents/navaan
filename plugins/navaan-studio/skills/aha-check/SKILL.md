---
name: aha-check
description: Fact-check every claim of an Aha-lorithm script on the web and save the evidence as originality.json. Use for the check step of the aha pipeline, before any picture or voice is paid for.
---

# Aha-lorithm fact check

The channel teaches people about AI, so one wrong fact costs more than a dull video. You must actually search; a verdict without searches is worthless.

1. Read `quote.json` (`lines`, `sources`). List every factual claim in the beats: how AI systems work, numbers, dates, named products, what experts recommend. Opinions and the takeaway line are not claims, but they must follow from the claims.
2. For each claim search the web (WebSearch, then WebFetch on the best hits): the vendor's or researcher's own documentation, a reference work or a reputable outlet. Check the script's `sources` too; a source that does not say it does not count.
3. If `visual_plan.json` exists, check what its scenes claim too. A figure treatment (`stat`, `ring`, `chart`) shows a number: open its `source` and confirm the page states that number for that thing. A `chat` shows an invented exchange and must read as an illustration, not as something a named product said. A `compare`, `timeline` or `flow` states facts in its texts: list those as claims. List each in `facts` with the beat's treatment in the note.
3b. Decide a `verdict`:
   - `clear`: every claim is backed by at least one reliable source and nothing in the script is misleading.
   - `unclear`: a claim could not be confirmed. Name it and suggest wording that is true.
   - `match_found`: the script is close to an existing video or article in the same words. Recommend a rewrite.
   Never round `unclear` up to `clear`. A figure whose source does not state the number makes the verdict `unclear`, and the recommendation says to replace that beat's treatment.
4. Write `originality.json`:
   `{"verdict": "...", "safe_to_publish": true|false, "author_verified": null, "facts": [{"claim": "...", "ok": true|false, "source": "https://...", "note": "..."}], "queries": ["what you searched"], "matches": [{"url": "https://...", "title": "...", "note": "why it matters"}], "recommendation": "one or two plain sentences: publish as is, or change beat N to ...", "checked_at": "ISO time"}`
   `safe_to_publish` is true only for `clear`. Real URLs only.
5. Do not edit `quote.json` yourself. Print the verdict and the recommendation, then stop. Do not approve the `originality` gate.
