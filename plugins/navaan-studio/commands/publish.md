---
description: "Prepare publishing for a song. Dry run first and send only with the gate and an explicit yes."
argument-hint: "<slug>"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Follow youtube-publish and instagram-publish for the song in the arguments. Dry run and show the payloads. Do not send until the gates are approved in meta.json and the user says yes in chat.

Arguments: $ARGUMENTS
