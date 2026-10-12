---
description: "Import a song already made on Suno, then continue the pipeline from there."
argument-hint: "<suno-link-or-id> [slug]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Use the suno-import skill. The first word of the arguments is the Suno link or id, the optional second word is the slug. Create the song with `suno_import.py init`, collect title, lyrics, style, model, audio and cover from the Suno page with the browser tool, run `suno_import.py ingest`, then loop with the navaan-pipeline skill: `navaan.py next <slug>`, do the step, repeat. The first gate is `listen`. Tell the user to approve it themselves. Never approve a gate, never spend credits, never publish without the recorded gate and an explicit yes in chat.

Arguments: $ARGUMENTS
