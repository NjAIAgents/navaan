---
description: "Show every song and where each one stands."
argument-hint: "[slug]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Run `navaan.py status` (or `status <slug>` for one song). Summarize states, which step is next, and which approvals are waiting for the user.

Arguments: $ARGUMENTS
