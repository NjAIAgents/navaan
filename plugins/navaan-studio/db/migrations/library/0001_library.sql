-- NAVAAN library, schema "library": what a listener keeps and plays (NAV-7). Every row carries user_id and every query is scoped by it (constitution XII, SC-005).
-- Users (core), tracks, albums and artists (catalog) are referenced by id without a foreign key: the schemas are migrated and tested separately, and the app checks that a track exists when it is added.
-- Released: never edit, add 0002.

CREATE TABLE playlists (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL,
  name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
  description text NOT NULL DEFAULT '' CHECK (length(description) <= 500),
  visibility  text NOT NULL DEFAULT 'private' CHECK (visibility IN ('private', 'unlisted', 'public')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX playlists_user_idx ON playlists (user_id);

-- Order is a fractional text key (positions.between), so two people moving things at once do not renumber each other's rows.
CREATE TABLE playlist_tracks (
  playlist_id  uuid NOT NULL REFERENCES playlists (id) ON DELETE CASCADE,
  track_id     uuid NOT NULL,
  position     text NOT NULL COLLATE "C",
  added_at     timestamptz NOT NULL DEFAULT now(),
  added_by     uuid,
  PRIMARY KEY (playlist_id, track_id),
  UNIQUE (playlist_id, position)
);

CREATE TABLE saved_tracks (user_id uuid NOT NULL, track_id uuid NOT NULL, saved_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (user_id, track_id));
CREATE TABLE saved_albums (user_id uuid NOT NULL, album_id uuid NOT NULL, saved_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (user_id, album_id));
CREATE TABLE follows (user_id uuid NOT NULL, artist_id uuid NOT NULL, followed_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (user_id, artist_id));

-- A play, for history and statistics (FR-019). Monthly partitions: old detail is removed by dropping a partition (library_store.drop_old_partitions), never row by row.
CREATE TABLE play_events (
  id           bigint GENERATED ALWAYS AS IDENTITY,
  user_id      uuid NOT NULL,
  track_id     uuid NOT NULL,
  started_at   timestamptz NOT NULL DEFAULT now(),
  ms_played    integer,
  source_kind  text,
  source_id    text,
  device       text,
  country      text,
  PRIMARY KEY (id, started_at)
) PARTITION BY RANGE (started_at);
CREATE INDEX play_events_user_idx ON play_events (user_id, started_at);
CREATE INDEX play_events_track_idx ON play_events (track_id, started_at);
CREATE TABLE play_events_default PARTITION OF play_events DEFAULT;
CREATE TABLE play_events_2026_10 PARTITION OF play_events FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE play_events_2026_11 PARTITION OF play_events FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE play_events_2026_12 PARTITION OF play_events FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');
CREATE TABLE play_events_2027_01 PARTITION OF play_events FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');
CREATE TABLE play_events_2027_02 PARTITION OF play_events FOR VALUES FROM ('2027-02-01') TO ('2027-03-01');
CREATE TABLE play_events_2027_03 PARTITION OF play_events FOR VALUES FROM ('2027-03-01') TO ('2027-04-01');
CREATE TABLE play_events_2027_04 PARTITION OF play_events FOR VALUES FROM ('2027-04-01') TO ('2027-05-01');
CREATE TABLE play_events_2027_05 PARTITION OF play_events FOR VALUES FROM ('2027-05-01') TO ('2027-06-01');
CREATE TABLE play_events_2027_06 PARTITION OF play_events FOR VALUES FROM ('2027-06-01') TO ('2027-07-01');
CREATE TABLE play_events_2027_07 PARTITION OF play_events FOR VALUES FROM ('2027-07-01') TO ('2027-08-01');
CREATE TABLE play_events_2027_08 PARTITION OF play_events FOR VALUES FROM ('2027-08-01') TO ('2027-09-01');
CREATE TABLE play_events_2027_09 PARTITION OF play_events FOR VALUES FROM ('2027-09-01') TO ('2027-10-01');
CREATE TABLE play_events_2027_10 PARTITION OF play_events FOR VALUES FROM ('2027-10-01') TO ('2027-11-01');
CREATE TABLE play_events_2027_11 PARTITION OF play_events FOR VALUES FROM ('2027-11-01') TO ('2027-12-01');
CREATE TABLE play_events_2027_12 PARTITION OF play_events FOR VALUES FROM ('2027-12-01') TO ('2028-01-01');

-- Rebuilt from the events (library_store.rebuild_daily_stats).
CREATE TABLE play_stats_daily (
  artist_id  uuid,
  track_id   uuid NOT NULL,
  day        date NOT NULL,
  plays      integer NOT NULL,
  listeners  integer NOT NULL,
  ms_played  bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (track_id, day)
);
