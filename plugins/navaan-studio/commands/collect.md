---
description: "Collect Instagram and YouTube analytics into the local database (read only). Can be scheduled."
argument-hint: "[instagram|youtube|all] [music|inspiration|all]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Use the data-collector role and the analytics-loop skill. Platform is the first argument: `instagram`, `youtube` or `all` (default all). Account is `music`, `inspiration` or `all`. For Instagram run `python3 scripts/ig_collect.py collect --account <account>` then `python3 scripts/ig_collect.py status`. For YouTube run `python3 scripts/yt_collect.py collect --account <account>` then `python3 scripts/yt_collect.py status`; if analytics are unavailable, say the user needs `python3 scripts/yt_collect.py auth` once. Read only towards both platforms. Do not ask questions: this command also runs on a schedule. On an auth error, report it and stop.

Finish with a short summary: what was collected, anything partial or failed, what the user must do.

Arguments: $ARGUMENTS
