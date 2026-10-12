---
description: "Upload a finished song to the cloud bucket."
argument-hint: "<slug>"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Run `upload_cloud.py <slug>` (dry run) and show the source, destination and command. Add `--yes` only if the cloud_upload gate is approved and the user says yes in chat.

Arguments: $ARGUMENTS
