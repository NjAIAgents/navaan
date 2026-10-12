---
description: "Create or edit the artist profile, including local and cloud locations."
argument-hint: "[--edit]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Run the artist-setup skill. Ask every question (local folder and cloud location first, both verified), write navaan.config.json, and confirm what was saved. Never ask for passwords, tokens or keys.

Arguments: $ARGUMENTS
