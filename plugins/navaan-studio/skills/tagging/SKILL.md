---
name: tagging
description: Tag the final mp3 with ID3 metadata and cover art, and prepare title, description and tags JSON. Use before publishing.
---

# Tagging and metadata

1. `python scripts/new_song.py <slug>` already fills `tags.json` from the artist profile (artist, album artist, copyright, credit text, year, default language). Fill in `title`, `genre`, `description` and `tags` for the song.
2. Use the native script title first and a romanized alias in the description for search. Add the profile's default hashtags.
3. `python scripts/tag_mp3.py <slug>` writes `final_tagged.mp3` with ID3v2.3 tags and `cover_1x1.png` embedded. Missing keys fall back to the profile.
