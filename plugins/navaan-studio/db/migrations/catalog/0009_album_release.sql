-- Album release (spec 003): only an album is released, and its songs with it. Expand only, works with the previous release: the status check gains 'missed' (a superset),
-- new columns are nullable or have a default. release_at is when it was or will be released; announced shows the coming-soon page; release records who confirmed which songs.
-- Released: never edit, add 0010.
ALTER TABLE albums DROP CONSTRAINT albums_status_check;
ALTER TABLE albums ADD CONSTRAINT albums_status_check CHECK (status IN ('draft', 'scheduled', 'published', 'missed'));
ALTER TABLE albums ADD COLUMN release_at timestamptz;
ALTER TABLE albums ADD COLUMN announced boolean NOT NULL DEFAULT false;
ALTER TABLE albums ADD COLUMN release jsonb NOT NULL DEFAULT '{}'::jsonb;
-- Songs listed before album releases existed stay listed: sync_item lets such a track stay published without an album release.
ALTER TABLE tracks ADD COLUMN public_before_albums boolean NOT NULL DEFAULT false;
UPDATE tracks SET public_before_albums = true WHERE status = 'published';
