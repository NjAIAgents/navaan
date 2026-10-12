---
description: "Prepare or send a YouTube upload through the official API."
argument-hint: "<slug> <file> [--privacy private|unlisted|public]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Follow the youtube-publish skill. Always dry run first and show the payload. Send with `--yes` only if the publish_youtube gate is approved in meta.json and the user said yes in chat for this exact file, title and privacy.

Arguments: $ARGUMENTS
