-- NAVAAN catalog, schema "catalog": what listeners find and play (NAV-6 stage 1). Built from the studio's published items by catalog_store.sync_item, never edited by hand.
-- Tracks refer to the studio item by slug (text), not by a foreign key: the studio lives in its own schema and the two are migrated and tested separately.
-- Search uses pg_trgm (typo tolerance, substring) and full text; folding of accents and Devanagari variants and the Roman transliteration are done in Python (search_text),
-- so one function builds the text for both the index and the query. Released: never edit, add 0002.

CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA public;

CREATE TABLE artists (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        text NOT NULL UNIQUE,
  name        text NOT NULL,
  status      text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'hidden')),
  theme       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO artists (slug, name) VALUES ('navaan', 'NAVAAN');

CREATE TABLE tracks (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  artist_id       uuid NOT NULL REFERENCES artists (id),
  slug            text NOT NULL UNIQUE,                  -- song-001: the same slug as the studio item
  studio_slug     text UNIQUE,
  title           text NOT NULL,
  language        text,
  duration_ms     integer,
  explicit        boolean NOT NULL DEFAULT false,
  lyrics_text     text NOT NULL DEFAULT '',
  status          text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'hidden')),
  published_at    timestamptz,
  origin          text NOT NULL DEFAULT 'unknown',       -- the generator: suno, own recording...
  origin_detail   jsonb NOT NULL DEFAULT '{}'::jsonb,    -- model, plan tier at generation time (NAV-11)
  license_status  text NOT NULL DEFAULT 'unconfirmed' CHECK (license_status IN ('unconfirmed', 'confirmed', 'not_allowed')),   -- only the owner sets confirmed (FR-017)
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX tracks_artist_idx ON tracks (artist_id);
CREATE INDEX tracks_status_idx ON tracks (status);

CREATE TABLE albums (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  artist_id     uuid NOT NULL REFERENCES artists (id),
  slug          text NOT NULL UNIQUE,
  title         text NOT NULL,
  kind          text NOT NULL DEFAULT 'album' CHECK (kind IN ('album', 'ep', 'single')),
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'published')),
  release_date  date,
  description   text NOT NULL DEFAULT '',
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX albums_artist_idx ON albums (artist_id);

CREATE TABLE album_tracks (
  album_id  uuid NOT NULL REFERENCES albums (id) ON DELETE CASCADE,
  track_id  uuid NOT NULL REFERENCES tracks (id) ON DELETE CASCADE,
  position  integer NOT NULL CHECK (position >= 1),
  PRIMARY KEY (album_id, track_id),
  UNIQUE (album_id, position) DEFERRABLE INITIALLY DEFERRED   -- a reorder is one transaction that may pass through duplicates
);
CREATE INDEX album_tracks_track_idx ON album_tracks (track_id);

-- Bytes live in object storage; a row says where. Several renditions per owner and role (image sizes, audio bitrates) are separate rows.
CREATE TABLE assets (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_kind      text NOT NULL CHECK (owner_kind IN ('track', 'album')),
  owner_id        uuid NOT NULL,
  role            text NOT NULL CHECK (role IN ('audio', 'cover', 'video', 'reel', 'lyrics_timed')),
  storage_key     text NOT NULL,
  mime            text,
  bytes           bigint,
  sha256          text,
  duration_ms     integer,
  width           integer,
  height          integer,
  dominant_colour text,
  blurhash        text,
  derived_from    uuid REFERENCES assets (id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (owner_kind, owner_id, role, storage_key)
);
CREATE INDEX assets_owner_idx ON assets (owner_kind, owner_id);

ALTER TABLE albums ADD COLUMN cover_asset_id uuid REFERENCES assets (id) ON DELETE SET NULL;

CREATE TABLE genres (
  id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name  text NOT NULL UNIQUE
);
CREATE TABLE track_genres (
  track_id  uuid NOT NULL REFERENCES tracks (id) ON DELETE CASCADE,
  genre_id  uuid NOT NULL REFERENCES genres (id) ON DELETE CASCADE,
  PRIMARY KEY (track_id, genre_id)
);
CREATE INDEX track_genres_genre_idx ON track_genres (genre_id);

CREATE TABLE search_documents (
  kind            text NOT NULL CHECK (kind IN ('track', 'album', 'playlist', 'short')),
  subject_id      uuid NOT NULL,
  artist_id       uuid NOT NULL REFERENCES artists (id),
  title_native    text NOT NULL,
  title_roman     text NOT NULL DEFAULT '',
  tags            text[] NOT NULL DEFAULT '{}',
  lyrics_excerpt  text NOT NULL DEFAULT '',
  search_text     text NOT NULL,                          -- folded native title, Roman transliteration and tags (translit.search_text)
  tsv             tsvector GENERATED ALWAYS AS (to_tsvector('simple', search_text || ' ' || lyrics_excerpt)) STORED,
  updated_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (kind, subject_id)
);
CREATE INDEX search_text_trgm_idx ON search_documents USING gin (search_text gin_trgm_ops);
CREATE INDEX search_tsv_idx ON search_documents USING gin (tsv);
