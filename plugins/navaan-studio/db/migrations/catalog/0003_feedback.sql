-- Feedback on songs from the free public site: anonymous reactions counted per song and day, and messages people choose to send. Two new tables: works with the previous release (expand only).
CREATE TABLE song_reactions (
  track_id  uuid    NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
  day       date    NOT NULL,
  reaction  text    NOT NULL CHECK (reaction IN ('up', 'down', 'love')),
  n         integer NOT NULL DEFAULT 0 CHECK (n >= 0),
  PRIMARY KEY (track_id, day, reaction)
);

-- A message from a visitor. The email is optional and only for a reply; the song is optional (feedback about the site).
CREATE TABLE site_feedback (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  track_id    uuid REFERENCES tracks(id) ON DELETE SET NULL,
  message     text NOT NULL CHECK (length(message) BETWEEN 1 AND 2000),
  email       text CHECK (email IS NULL OR length(email) <= 254),
  created_at  timestamptz NOT NULL DEFAULT now(),
  handled_at  timestamptz
);
CREATE INDEX site_feedback_created_idx ON site_feedback (created_at DESC);
CREATE INDEX site_feedback_track_idx ON site_feedback (track_id);
