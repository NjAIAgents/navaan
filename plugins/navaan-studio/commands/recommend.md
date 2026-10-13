---
description: "Find what is going wrong on Instagram or YouTube and what will help followers, views and reach. Can be scheduled."
argument-hint: "[instagram|youtube] [music|inspiration|all] [--collect] [--no-web]"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Use the growth-advisor role and the growth-advice skill. Do not ask questions: this command also runs on a schedule. Make a reasonable choice, say it, and continue.

- Platform is the first argument, `instagram` (default) or `youtube`. For YouTube pass `--platform youtube` to every `ig_reco.py` call and `--note-platform youtube` when storing notes.
- `--collect`: run the data-collector steps first (`ig_collect.py collect` or `yt_collect.py collect`). Without it, use the data already stored and say how old it is.
- `--no-web`: skip web research. Use stored market notes only.
- Organic growth only. Never write to Instagram or YouTube.

Finish with a short summary: findings read, notes stored, recommendations stored, the one thing to do first. The portal Analytics page (Instagram or YouTube tab) shows the recommendations with Implement, Done and Dismiss.

Arguments: $ARGUMENTS
