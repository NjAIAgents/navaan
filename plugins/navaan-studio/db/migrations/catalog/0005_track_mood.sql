-- The mood of a song, chosen in the studio: it picks the background of the full screen player. Nullable column, no rewrite: works with the previous release (expand only).
ALTER TABLE tracks ADD COLUMN mood text CHECK (mood IS NULL OR mood IN ('dawn', 'dusk', 'night', 'quiet'));
