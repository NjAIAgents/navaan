---
description: "Prepare or send an Instagram Reel through the official API."
argument-hint: "<slug>"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Follow the instagram-publish skill. Dry run first and show the plan. Send with `--yes` only if the publish_instagram gate is approved and the user said yes in chat for this exact reel.

Arguments: $ARGUMENTS
