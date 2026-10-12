---
description: "Show the next action for a song and do it if no approval is blocking it."
argument-hint: "[slug]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Run `navaan.py next <slug>` for the song in the arguments (or the most recent song). Explain the result in one or two sentences. Run the step only when no gate is waiting. If a gate is waiting, tell the user how to approve it themselves.

Arguments: $ARGUMENTS
