---
name: navaan-pipeline
description: Orchestrate a NAVAAN song from idea to published, with human approval gates. Use when the user starts a new song, asks what is next, or says continue the pipeline.
---

# NAVAAN pipeline

You are the orchestrator. Everything about a song lives in `songs/<slug>/`. The orchestrator script derives progress from the files plus the approvals recorded in `meta.json`, so ask it instead of guessing.

## Start every session

1. If `navaan.config.json` is missing or `python scripts/setup_profile.py --check` reports missing answers, run the artist-setup skill first.
2. Run `python scripts/navaan.py status` to see all songs, then `python scripts/navaan.py next <slug>` for the next action.
3. Read `navaan.config.json` and `songs/<slug>/meta.json` before doing the step.

## End to end run

The whole pipeline is one command: `python scripts/navaan.py start <slug> <idea words>` creates the song, writes the brief, and runs every step in order. At each gate it waits until the user approves (in the web UI or with `navaan.py approve`), then continues by itself. `navaan.py pipeline <slug> --wait` does the same for an existing song, and without `--wait` it stops at the first gate. `--until <step>` stops after a step.

When you are the agent in a chat session (no long running process), loop like this:

1. Run `navaan.py next <slug>`.
2. If it says run, do the step (delegate to the specialist agent, or run `navaan.py run <slug>`), then go back to 1.
3. If it says gate, show the user what to review (lyrics text, the take, the videos, the publish payload), name the gate, tell them how to approve it, and stop. When the user says they approved, run `navaan.py next <slug>` again and confirm the approval is really recorded before continuing. Never treat a chat message as the recorded approval.
4. Stop when next says done, or when a step fails (show the log path).

## Song already on Suno

If the song was already generated on Suno, use the suno-import skill instead of the lyrics and suno steps: `navaan.py import <suno-link> [slug]`. It pulls title, lyrics, style, model, audio and cover from the Suno page, spends no credits, and the pipeline continues from the listen gate.

## Steps and gates

| step | skill | specialist agent | gate |
|---|---|---|---|
| suno_import (instead of lyrics and suno) | suno-import | suno-operator | after: listen (user confirms the imported song) |
| lyrics | lyrics | lyricist | after: lyrics (user approves the words) |
| suno | suno-generate | suno-operator | before: credits, after: listen (user accepts the take) |
| visuals | flow-visuals | visual-director | before: credits |
| captions | caption-sync | caption-aligner | none |
| video | video-build, shorts, tagging | visual-director | after: media (user approves the videos) |
| publish_youtube | youtube-publish | publisher | before: publish_youtube |
| youtube_short | youtube-short | publisher | before: publish_short |
| archive | upload_cloud.py | publisher | before: cloud_upload |
| instagram_caption | instagram-caption | publisher | after: instagram_caption (caption printed for approval; edits clear the approval) |
| publish_instagram | instagram-publish | publisher | before: publish_instagram |
| later | analytics-loop | analyst | none |

## Rules you must keep

1. Songs live in the local folder from the profile (`storage.local_dir`), never inside the plugin or its repository. While a song is in progress everything stays local. Only a finished song is uploaded to the cloud bucket, and only after the user approves the cloud_upload gate. Dry run first: `python scripts/upload_cloud.py <slug>`.
2. Gates are human only. `meta.json` approvals are written by the user through `python scripts/navaan.py approve <slug> <gate>` or the web UI (`python scripts/navaan.py serve`). Never write an approval yourself, never edit the approvals object, and never claim an approval you did not see.
3. A step that needs a gate waits. Tell the user which gate and how to approve it, then stop.
4. Publishing, deleting a public video, spending Suno or Flow credits, and sending any message for the user each need their explicit yes in chat as well as the recorded gate.
5. Delegate to the specialist agent for the step when the tool supports subagents. Give it the slug, the step, and the files it may touch. Otherwise do the step yourself with the skill.
6. After each step the orchestrator or you append a short history line to `meta.json`. Keep `state` honest: draft, lyrics_ok, generated, accepted, media_ready, approved, published.
7. Never put secrets in the project. The user logs in to Suno, Flow, Google and Meta themselves. Stop at any login, CAPTCHA or file picker: in a headless step write `question.json` (see AGENTS.md) so the user can answer in the web portal.
8. Report plainly: what changed, which file, what you need next.
