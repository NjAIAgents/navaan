---
name: suno-generate
description: Generate, download and accept a Suno song through Claude in Chrome on the user's own logged in account. Use after lyrics are approved.
---

# Suno generation

There is no official Suno API. Drive the Suno web app with a browser tool on the user's own logged in Pro account, at a human pace. The user handles login and CAPTCHA.

0. Read `navaan.config.json` (languages, genres, moods, voice, things to avoid, palette, motifs, Suno model, credit policy) and follow it. Run artist-setup if it is missing.
1. Open Suno in a tab. If a Suno tab is already open, reuse it: do not open a second one or go back to the Suno home address, because the signed in account is tied to that tab. If a login or CAPTCHA appears, stop and ask the user.
2. Open Create in custom mode. Paste `lyrics.txt` and `style.txt`, set the model recorded in `meta.json` (default v6), and set the title. Pressing Create spends credits: only do it when the credits gate is approved and, in chat, the user said yes. Each Create spends credits.
3. Wait for both takes. Record the Suno URL and take lengths in `meta.json`. Share both with the user. This is gate two: the user listens and picks one take or asks for another run.
4. Download the chosen take. MP3 downloads sometimes hang on a spinner. Use M4A and convert with ffmpeg: `ffmpeg -i in.m4a -codec:a libmp3lame -q:a 2 final.mp3`. Downloads land in the user's Downloads folder on their computer.
5. Move the file to `songs/<slug>/final.mp3`, keep rejected takes in `takes/`, and set `state` to `accepted` only after the user says so.

Limit retries. If the same lyrics fail twice, change the style prompt, not the lyrics, and tell the user.
