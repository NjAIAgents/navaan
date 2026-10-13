---
name: growth-advice
description: Turn Instagram or YouTube analytics findings plus current market trends into a few sourced, organic growth recommendations. Use after a collect, weekly, or when the user asks what to improve.
---

# Growth advice

All commands run from the workspace folder. `ig_reco.py` is the only way recommendations are stored.

**Platform.** Instagram by default. For YouTube add `--platform youtube` before the sub command of every `ig_reco.py` call (for example `python3 scripts/ig_reco.py --platform youtube analyze`), give notes `--note-platform youtube`, collect with `python3 scripts/yt_collect.py collect`, and use account `music` (the channel label). YouTube categories also include `retention` and `packaging`. Research YouTube questions such as Shorts versus full length for Hindi or Maithili music, title and description wording for search, and how YouTube describes ranking (watch time, satisfaction). The evidence pack says CTR and impressions are unavailable: do not guess them.

1. **Refresh the facts.** If the data is more than a day old or `--collect` was given, run `python3 scripts/ig_collect.py collect` (YouTube: `python3 scripts/yt_collect.py collect`). Then `python3 scripts/ig_reco.py analyze`. This runs the rules, stores findings and writes plain rule based recommendations, so the portal always has something.
2. **Read the evidence.** `python3 scripts/ig_reco.py pack --account music --out "${TMPDIR:-/tmp}/navaan_pack.json"`, then read the file. Check `findings`, `top_posts`, `bottom_posts`, `recommendations_so_far` (including outcomes of anything marked done) and `market.notes`. Repeat for `--account inspiration` if it has posts.
3. **Research the market** (skip with `--no-web`). Use WebSearch and WebFetch for 3 to 5 narrow questions, picked from the findings. Examples: current Reels length and hook patterns for Hindi or Maithili indie music, how Instagram currently describes ranking of Reels (watch time, sends, saves), what peers in the same genre are posting. Prefer official Instagram and Meta pages, creator education pages, and dated articles. Ignore anything undated or from sellers of growth services.
4. **Store each useful fact as a note with its source.** `python3 scripts/ig_reco.py note --topic "..." --summary "one or two sentences" --url "https://..." --title "..." --confidence low|medium|high [--region IN] [--language Hindi]`. A note without a URL is rejected. Keep the summary to what the page says, not what you hope it implies.
5. **Write at most 6 recommendations** as a JSON list and store them: `python3 scripts/ig_reco.py add --account music --file "${TMPDIR:-/tmp}/recs.json"`. Each item:
   `{"title": "...", "why": "what the numbers show", "action": "one concrete thing to do next week", "expected_effect": "what should move and roughly why", "category": "data|hook|content|timing|cadence|hashtags|caption|engagement|audience|format|market|growth", "priority": 1|2|3, "confidence": "low|medium|high", "finding_ids": ["..."], "note_ids": ["..."]}`.
   Priority 1 is do first. Every item must cite at least one finding id or note id. Fix rejected items and add again.
6. **Check what worked.** `python3 scripts/ig_reco.py outcomes` updates verdicts on recommendations marked done. If one says worse or flat after 3 or more posts, say so in your summary and do not recommend the same thing again.

Rules:
- Organic growth only: content, hooks, timing, captions, hashtags, replies and habits. No paid boosts, bought followers, engagement pods, or automated likes and comments.
- Read only towards Instagram and YouTube. This skill never posts, replies, comments, likes or deletes.
- Prefer the few changes that matter over a long list. Say what the data supports and what it does not. Under 5 measured posts, say confidence is low.
- Rules of thumb in findings (marked `basis: rule_of_thumb`) are not industry benchmarks. Do not present them as such.
- Do not ask questions. This runs on a schedule. State your assumption and continue.
