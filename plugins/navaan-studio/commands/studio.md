---
description: "Open the local web UI."
argument-hint: "[port]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Tell the user to run `navaan.py serve` from the workspace folder and open http://127.0.0.1:8765 (or the port given). Do not start long running servers for them unless they ask.

Arguments: $ARGUMENTS
