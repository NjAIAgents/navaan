---
description: "Run or resume the whole pipeline for a song, pausing at each approval gate."
argument-hint: "<slug>"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Run the whole pipeline end to end with the navaan-pipeline skill's chat loop: `navaan.py next <slug>`, do the step, repeat. At every gate show what to review, name the gate, tell the user to approve it themselves (web UI or `navaan.py approve <slug> <gate>`), then stop. When the user says they approved, run `next` again and confirm the approval is recorded before continuing. Never approve a gate, never publish or spend credits without the recorded gate and an explicit yes in chat. Stop when next says done or a step fails.

Arguments: $ARGUMENTS
