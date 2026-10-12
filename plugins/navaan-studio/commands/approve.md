---
description: "Explain how to approve a gate. Agents cannot approve for you."
argument-hint: "<slug> <gate>"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Do not approve anything. Tell the user to run `navaan.py approve <slug> <gate>` in a terminal or click Approve in the web UI. Gates are lyrics, listen, credits, media, publish_youtube, publish_instagram and cloud_upload. State which gate the song is waiting on (from `navaan.py next <slug>`) and what it unlocks.

Arguments: $ARGUMENTS
