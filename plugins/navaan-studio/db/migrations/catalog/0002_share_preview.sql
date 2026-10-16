-- NAV-6 stage 2: share links, and a short preview rendition of a track's audio. Adding a role value and a table work with the previous release (expand only).
ALTER TABLE assets DROP CONSTRAINT assets_role_check;
ALTER TABLE assets ADD CONSTRAINT assets_role_check CHECK (role IN ('audio', 'audio_preview', 'cover', 'video', 'reel', 'lyrics_timed'));

-- A link anyone can open; the token is the only secret (random, never guessable), so it is stored as given. Only published tracks with a confirmed licence resolve.
CREATE TABLE share_links (
  token         text PRIMARY KEY,
  subject_kind  text NOT NULL CHECK (subject_kind IN ('track', 'album')),
  subject_id    uuid NOT NULL,
  created_by    text NOT NULL,
  start_ms      integer NOT NULL DEFAULT 0 CHECK (start_ms >= 0),
  created_at    timestamptz NOT NULL DEFAULT now(),
  expires_at    timestamptz,
  revoked_at    timestamptz,
  opens         integer NOT NULL DEFAULT 0
);
CREATE INDEX share_links_subject_idx ON share_links (subject_kind, subject_id);
