-- NAVAAN studio, schema "studio": the state of every song and inspiration (what songs/<slug>/meta.json held).
-- Stage 1 (NAV-4): items.doc is the canonical, lossless copy of the old meta.json, so moving in cannot lose a key. The other tables are projections of doc,
-- rewritten in the same transaction on every save, so they can be queried, locked and joined (scheduler, analytics foreign keys). Later stages move readers onto
-- the typed tables one field at a time; until a field is moved, doc wins. Released: never edit, add 0002.

CREATE TABLE items (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        text NOT NULL UNIQUE,                     -- song-001, insp-001: unique across all artists (analytics refers to it)
  artist      text NOT NULL DEFAULT 'navaan',           -- becomes artist_id when catalog.artists exists (P4)
  type        text NOT NULL DEFAULT 'music' CHECK (type IN ('music', 'inspiration', 'explainer', 'podcast')),
  state       text,
  doc         jsonb NOT NULL,
  version     bigint NOT NULL DEFAULT 1,
  export_sha  text,                                     -- sha256 of the meta.json text last written from doc; a different file on disk means someone else edited it
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE item_history (
  item_id  uuid NOT NULL REFERENCES items (id) ON DELETE CASCADE,
  seq      integer NOT NULL,
  at       timestamptz,
  text     text NOT NULL,
  PRIMARY KEY (item_id, seq)
);

CREATE TABLE approvals (
  item_id       uuid NOT NULL REFERENCES items (id) ON DELETE CASCADE,
  gate          text NOT NULL,
  approved_at   timestamptz,
  via           text,
  content_hash  text,                                   -- the sha recorded at approval; NULL means legacy-approved
  detail        jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (item_id, gate)
);

CREATE TABLE publications (
  item_id      uuid NOT NULL REFERENCES items (id) ON DELETE CASCADE,
  platform     text NOT NULL CHECK (platform IN ('youtube', 'instagram')),
  kind         text NOT NULL CHECK (kind IN ('video', 'short', 'reel', 'feed')),
  external_id  text NOT NULL DEFAULT '',
  url          text,
  privacy      text,
  detail       jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (item_id, platform, kind, external_id)
);

CREATE TABLE schedules (
  item_id   uuid NOT NULL REFERENCES items (id) ON DELETE CASCADE,
  platform  text NOT NULL CHECK (platform IN ('youtube', 'instagram')),
  run_at    timestamptz,
  status    text NOT NULL CHECK (status IN ('waiting', 'done', 'missed', 'blocked')),
  attempts  integer NOT NULL DEFAULT 0,
  detail    jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (item_id, platform)
);

CREATE INDEX items_state_idx ON items (state);
CREATE INDEX schedules_due_idx ON schedules (run_at) WHERE status = 'waiting';
