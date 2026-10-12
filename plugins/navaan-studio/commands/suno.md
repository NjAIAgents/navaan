---
description: "Generate the song on Suno in the browser."
argument-hint: "<slug>"
---

Scripts live in the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code, otherwise the plugin folder). Run them from the workspace folder. Read `navaan.config.json` first; if it is missing, do the setup command first.

Follow the suno-generate skill using the suno-operator role. Create only if the credits gate is approved in meta.json and the user says yes in chat. Stop at any login or CAPTCHA.

Arguments: $ARGUMENTS
