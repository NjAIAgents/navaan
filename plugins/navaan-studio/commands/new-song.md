---
description: "Start a new song and run the whole pipeline end to end, pausing at each approval gate."
argument-hint: "<slug> [idea]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Create the folder with `new_song.py <slug>` (the first word of the arguments is the slug, ask for one if missing). Write brief.md from the user's idea and answers. Then:

Run the whole pipeline end to end with the navaan-pipeline skill's chat loop: `navaan.py next <slug>`, do the step, repeat. At every gate show what to review, name the gate, tell the user to approve it themselves (web UI or `navaan.py approve <slug> <gate>`), then stop. When the user says they approved, run `next` again and confirm the approval is recorded before continuing. Never approve a gate, never publish or spend credits without the recorded gate and an explicit yes in chat. Stop when next says done or a step fails.

If the user prefers to run it unattended in a terminal, give them `navaan.py start <slug> <idea>` or the web UI Run end to end button.

Arguments: $ARGUMENTS
