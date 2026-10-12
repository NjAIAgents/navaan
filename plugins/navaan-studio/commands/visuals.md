---
description: "Make cover art and Flow clips for a song."
argument-hint: "<slug>"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Follow the flow-visuals skill using the visual-director role. Generate only if the credits gate is approved and the user says yes in chat.

Arguments: $ARGUMENTS
