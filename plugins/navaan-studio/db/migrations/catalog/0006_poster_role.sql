-- A track's poster (the portrait picture made for it) can be registered as a picture of the track, so a shared link's preview can show it in place of the cover. Adding a role value works with the previous release (expand only).
ALTER TABLE assets DROP CONSTRAINT assets_role_check;
ALTER TABLE assets ADD CONSTRAINT assets_role_check CHECK (role IN ('audio', 'audio_preview', 'cover', 'poster', 'video', 'reel', 'lyrics_timed'));
