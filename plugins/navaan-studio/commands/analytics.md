---
description: "Pull stats for published videos and propose re-edits."
argument-hint: "<slug>"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Follow the analytics-loop skill using the analyst role. Say what the numbers support and what they do not. Anything that touches a public video waits for the user's explicit yes.

Arguments: $ARGUMENTS
