---
description: "Collect Instagram analytics into the local database (read only). Can be scheduled."
argument-hint: "[music|inspiration|all]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Use the data-collector role and the analytics-loop skill. Run `python3 scripts/ig_collect.py collect --account <arg>` (default all), then `python3 scripts/ig_collect.py status`. Read only towards Instagram. Do not ask questions: this command also runs on a schedule. On an auth error, report it and stop.

Finish with a short summary: what was collected, anything partial or failed, what the user must do.

Arguments: $ARGUMENTS
