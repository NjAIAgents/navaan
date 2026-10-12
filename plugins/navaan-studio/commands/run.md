---
description: "Run the next ready step through the orchestrator, with retries and logs."
argument-hint: "<slug> [--dry]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Run `navaan.py run <slug>` (add `--dry` to only print what would run). Report the outcome and the log path under the song folder. Do not approve gates.

Arguments: $ARGUMENTS
