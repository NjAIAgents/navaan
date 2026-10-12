---
description: "Write or revise the lyrics, title and Suno style prompt for a song."
argument-hint: "<slug> [notes]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Follow the lyrics skill for the song in the arguments using the lyricist role. Show the result and ask for approval in chat. The user records the lyrics gate themselves.

Arguments: $ARGUMENTS
