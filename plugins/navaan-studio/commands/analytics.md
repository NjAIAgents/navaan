---
description: "Pull stats for published videos and propose re-edits."
argument-hint: "<slug>"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Follow the analytics-loop skill using the analyst role. Say what the numbers support and what they do not. Anything that touches a public video waits for the user's explicit yes.

Arguments: $ARGUMENTS

Growth advice: `/navaan-studio:recommend instagram|youtube` (rules, market research, sourced recommendations). Collection alone: `/navaan-studio:collect instagram|youtube|all`. Both can be scheduled.

YouTube collector (read only): `python3 scripts/yt_collect.py collect [--account music] [--only channel,videos,comments,analytics,retention]`, `status`, `link`, and `auth` once for the read only analytics sign-in (watch time, retention, traffic, audience). Tables: `yt_videos`, `yt_snapshots`, `yt_daily`, `yt_traffic`, `yt_audience`, `yt_retention`, `yt_comments`, `yt_runs`. Recommendations use `ig_reco.py --platform youtube`.

Instagram data collector (read only, fills a local SQLite database that the portal's Analytics page reads):

- Collect: `python3 scripts/ig_collect.py collect [--account music|inspiration|all] [--only account,media,comments,audience,mentions]`
- Status: `python3 scripts/ig_collect.py status`
- Database: env `NAVAAN_DB`, or `analytics.db_path` in `navaan.config.json`, or `~/.local/share/navaan/analytics.db`.
- Query it for per-post insights (`media_snapshots`), comments and tag columns (`comments.category`, `language`, `sentiment`), audience, and collector runs. Never write to Instagram from the analytics flow.
