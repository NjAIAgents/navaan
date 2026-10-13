---
name: inspiration-check
description: Check an inspiration quote for originality and correct attribution by searching the web, and save the evidence as originality.json. Use for the originality step, before anything is made or published.
---

# Originality and attribution check

You must actually search. A verdict without searches is worthless, so run them and keep the evidence.

1. Read `quote.json`. If `kind` is `original`, the risk is that the line already exists. If it is `attributed`, the risks are a wrong author, altered wording and a copyright claim.
2. Search the web (WebSearch, then WebFetch on the best hits) for:
   - the exact text in quotation marks, then two or three distinctive fragments, in the quote's own language and script, plus a romanized form for Hindi;
   - for an attributed quote, the quote with the author's name, and `misattributed` or `quote investigator` style checks.
3. Decide a `verdict`:
   - `clear`: an original line and no earlier use found.
   - `attributed_verified`: author and wording confirmed by at least two independent sources, one of them primary or a quote-research source (a book, the speech, a reference work).
   - `public_domain`: the work is old enough that no copyright applies, with the source.
   - `match_found`: an original line that already exists elsewhere in the same or near wording. Recommend a rewrite.
   - `misattributed`: the named author did not say it, or the wording is wrong. Give the likely true author or the corrected wording.
   - `copyright_risk`: a recent, protected work. Short quotes with attribution are usually fine, long ones are not. Say which.
   - `unclear`: not enough evidence. Never round this up to a safe verdict.
4. Write `originality.json`:
   `{"verdict": "...", "safe_to_publish": true|false, "author_verified": true|false|null, "queries": ["what you searched"], "matches": [{"url": "https://...", "title": "...", "note": "why it matters"}], "recommendation": "one or two plain sentences: publish as is, change the credit line to X, or rewrite", "checked_at": "ISO time"}`
   `safe_to_publish` is true only for `clear`, `attributed_verified` and `public_domain`. Keep `matches` to the five most relevant, real URLs only.
5. If the credit line must change (a corrected author), do not edit `quote.json` yourself. Say it in `recommendation`, and the user fixes the quote at the gate.
6. Print the verdict and the recommendation, then stop. Do not approve the `originality` gate. The user decides, and can approve even a risky verdict on purpose.
