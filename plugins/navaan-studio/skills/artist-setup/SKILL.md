---
name: artist-setup
description: Create or edit the artist profile (navaan.config.json) by asking the user every setup question. Use on first run, when navaan.config.json is missing or incomplete, or when the user wants to change channel defaults.
---

# Artist setup

The artist profile is the single source of channel defaults: where songs live locally and in the cloud, name, copyright owner, languages, genres, moods, voice, things to avoid, visual palette and motifs, caption font, YouTube and Instagram handles, playlists, hashtags, AI disclosure, Short length, and credit text. It is stored in `navaan.config.json` at the project root. `style-notes.md` is generated from it.

## Storage locations (asked first, always verified)

- Local folder: where songs are created and exported while the user works. Default is the folder the session started in. It must be outside the plugin folder and outside the repository that ships the plugin. Setup rejects anything inside them.
- Cloud: provider (none, oci, s3 or gcs), bucket, prefix (default navaan/songs) and optional region. Finished songs are uploaded here only after the user approves the cloud_upload gate.
- Verification: the local folder is checked for existence, write access and free space. The cloud bucket is checked with the user's own oci, aws or gcloud login. `python scripts/setup_profile.py --verify` re-checks, and `--verify --write` also puts and deletes a tiny test object (do that only when the user agrees). If a check fails, show the message and ask again. Do not save a profile that fails verification unless the user insists, then pass `--skip-verify` and say what is unverified.

## In a terminal

Run `python scripts/setup_profile.py` (or `python scripts/navaan.py init`). It asks every question, shows a default in brackets, and writes the file. Use `--edit` to change answers later. Enter keeps the current value, a dash clears an optional one.

## In chat (when you cannot use a terminal prompt)

1. Run `python scripts/setup_profile.py --questions` to get the question list as JSON.
2. If `navaan.config.json` exists, run `--show` and treat its values as defaults.
3. Ask the user the questions in small groups of up to four, using the host's question tool when it has one (AskUserQuestion in Claude Code). Offer the default as the first option. Required questions are marked.
4. Write the answers to a temporary JSON file as a flat object keyed by the question key, for example `{"artist.name": "NAVAAN", "music.languages": "Hindi, Maithili"}`.
5. Run `python scripts/setup_profile.py --from answers.json`. It verifies the local folder and the cloud location and refuses to save on errors. Then run `--check`. Delete the temporary file.
6. Read the result back to the user in two or three sentences.

## Rules

- Never ask for or store passwords, cookies, API keys, tokens or OAuth secrets. Those stay on the user's computer, outside the project.
- Do not guess required answers. If the user skips one, say it is still missing.
- The approval rules (explicit approval to publish, delete or spend credits) are written into the profile as locked values and cannot be changed through setup.
