---
description: "Check the local folder and the cloud bucket from the profile."
argument-hint: "[--write]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Run `setup_profile.py --verify`. Only add `--write` (puts and deletes a tiny test object in the bucket) if the user agrees. Report each check in plain words and what to fix.

Arguments: $ARGUMENTS
