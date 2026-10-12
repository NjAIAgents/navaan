---
name: suno-import
description: Import a song that already exists on the user's Suno account (title, lyrics, style prompt, model, audio, cover) into a NAVAAN song folder, then continue the pipeline from there. Use when the user gives a Suno link or says the song is already made.
---

# Suno import

Use this when the song was already generated on Suno. It spends no credits and skips the lyrics and generate steps. The pipeline continues with the listen gate, then visuals, captions, video and publishing.

## Start

1. Get the Suno song link or id from the user. A link looks like `https://suno.com/song/<id>` or a short share link `https://suno.com/s/<code>`. If they only say "my latest song", open their Suno library and ask which one.
2. Run `python scripts/suno_import.py init <link-or-id> [slug]`. The last line printed is the slug. It creates the song folder in the profile's local folder and marks the song as an import. Or run `python scripts/navaan.py import <link-or-id> [slug]`, which does this and then runs the whole pipeline.

A short share link is resolved to the song id when Suno allows it. If `meta.json` has no `suno.id`, open the link in the browser, read the song id from the address it lands on (`/song/<id>`), and pass it to ingest with `--suno-id`.

## Collect from Suno (browser, user's own logged in account)

Open the song page in a new tab. Stop at any login or CAPTCHA and ask the user. Work at a human pace and only read and download. Do not press Create, Remix, Extend or anything that spends credits.

Collect, in a scratch folder outside the song folder:

1. Title.
2. Lyrics exactly as shown on the song page. If the page shows both the entered lyrics and the sung text, keep the sung text. Save as `lyrics.txt`.
3. Style prompt and the model version (v4.5, v5, v6 and so on). Save the style as `style.txt`.
4. Audio. Use the song menu, Download, and prefer M4A, because the MP3 download sometimes hangs on a spinner. The file lands in the user's Downloads folder on their computer.
5. Cover image if the user wants it kept.

## Ingest

Run `python scripts/suno_import.py ingest <slug> --audio <file> --title "<title>" --lyrics-file <lyrics.txt> --style-file <style.txt> --model <vX> [--cover <image>]`. It converts the audio to `final.mp3`, keeps the original in `takes/`, writes the text files and updates `meta.json`. It rejects audio shorter than 10 seconds. If it prints a warning about an empty file, collect that piece and run ingest again.

## Then

Show the user the title, lyrics, style, length and the first lines of `final.mp3` to listen to. The next gate is `listen`. The user approves it themselves in the web UI or with `navaan.py approve <slug> listen`. Never record it for them. After that run `navaan.py next <slug>` and continue the normal pipeline.

Lyrics may be in another language than the profile default. Keep the text as Suno has it. Do not translate or rewrite it. Captions need the sung text, so if the page lyrics differ from what is sung, tell the user and ask for the sung version.
