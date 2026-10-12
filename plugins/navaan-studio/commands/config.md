---
description: "Show the current artist profile and what is still missing."
argument-hint: ""
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Run `setup_profile.py --show` and `--check`. Summarize the profile in a few lines (artist, languages, genres, local folder, cloud location, handles). Name any missing required answers and offer the setup command.

Arguments: $ARGUMENTS
