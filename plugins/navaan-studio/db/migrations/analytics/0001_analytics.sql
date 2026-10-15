-- NAVAAN analytics, schema "analytics". The tables the SQLite file had, with 64-bit integers and double precision.
-- Timestamps are UTC ISO text (YYYY-MM-DDTHH:MM:SSZ) and dates YYYY-MM-DD for now; flags are 0/1. Typed columns (timestamptz, boolean) come in a later migration.
-- This file is released: never edit it, add 0002_*.sql (the previous release must keep working, so no drops or renames in the same release).
-- NAVAAN analytics schema. Portable SQL: TEXT, BIGINT, DOUBLE PRECISION, composite primary keys, no AUTOINCREMENT, no triggers.
-- SQLite today, Postgres later. analytics_db.migrate runs the statements one by one, so keep a semicolon out of every comment and default value.
-- Timestamps are UTC ISO strings (YYYY-MM-DDTHH:MM:SSZ). Dates are YYYY-MM-DD.

CREATE TABLE IF NOT EXISTS schema_version (
  version BIGINT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
  ig_user_id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  username TEXT,
  name TEXT,
  created_at TEXT NOT NULL,
  last_collected_at TEXT
);

CREATE TABLE IF NOT EXISTS songs (
  slug TEXT PRIMARY KEY,
  item_type TEXT,
  title TEXT,
  album TEXT,
  genre TEXT,
  language TEXT,
  state TEXT,
  tags_json TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS media (
  media_id TEXT PRIMARY KEY,
  ig_user_id TEXT NOT NULL,
  slug TEXT,
  media_type TEXT,
  product_type TEXT,
  permalink TEXT,
  shortcode TEXT,
  caption TEXT,
  posted_at TEXT,
  thumbnail_url TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_media_account ON media (ig_user_id, posted_at);
CREATE INDEX IF NOT EXISTS idx_media_slug ON media (slug);

CREATE TABLE IF NOT EXISTS media_snapshots (
  media_id TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  like_count BIGINT,
  comments_count BIGINT,
  reach BIGINT,
  views BIGINT,
  saved BIGINT,
  shares BIGINT,
  reposts BIGINT,
  total_interactions BIGINT,
  avg_watch_time_ms DOUBLE PRECISION,
  total_watch_time_ms DOUBLE PRECISION,
  skip_rate DOUBLE PRECISION,
  follows BIGINT,
  profile_visits BIGINT,
  raw_json TEXT,
  PRIMARY KEY (media_id, captured_at)
);

CREATE TABLE IF NOT EXISTS comments (
  comment_id TEXT PRIMARY KEY,
  media_id TEXT NOT NULL,
  parent_id TEXT,
  username TEXT,
  text TEXT,
  posted_at TEXT,
  like_count BIGINT,
  hidden BIGINT NOT NULL DEFAULT 0,
  is_own BIGINT NOT NULL DEFAULT 0,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  category TEXT,
  language TEXT,
  sentiment TEXT,
  tagged_at TEXT,
  reply_status TEXT
);

CREATE INDEX IF NOT EXISTS idx_comments_media ON comments (media_id, posted_at);
CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments (parent_id);

CREATE TABLE IF NOT EXISTS account_daily (
  ig_user_id TEXT NOT NULL,
  period_end TEXT NOT NULL,
  metric TEXT NOT NULL,
  value DOUBLE PRECISION,
  collected_at TEXT NOT NULL,
  PRIMARY KEY (ig_user_id, period_end, metric)
);

CREATE TABLE IF NOT EXISTS audience (
  ig_user_id TEXT NOT NULL,
  captured_on TEXT NOT NULL,
  breakdown TEXT NOT NULL,
  bucket TEXT NOT NULL,
  value BIGINT,
  PRIMARY KEY (ig_user_id, captured_on, breakdown, bucket)
);

CREATE TABLE IF NOT EXISTS online_hours (
  ig_user_id TEXT NOT NULL,
  captured_on TEXT NOT NULL,
  hour BIGINT NOT NULL,
  followers BIGINT,
  PRIMARY KEY (ig_user_id, captured_on, hour)
);

CREATE TABLE IF NOT EXISTS mentions (
  mention_id TEXT PRIMARY KEY,
  ig_user_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  media_id TEXT,
  comment_id TEXT,
  username TEXT,
  permalink TEXT,
  text TEXT,
  posted_at TEXT,
  like_count BIGINT,
  comments_count BIGINT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  reply_status TEXT
);

CREATE TABLE IF NOT EXISTS collector_runs (
  run_id TEXT PRIMARY KEY,
  ig_user_id TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  collectors TEXT,
  status TEXT,
  stats_json TEXT,
  errors_json TEXT
);

-- Schema version 2: market data, findings and recommendations.
CREATE TABLE IF NOT EXISTS peers (
  username TEXT PRIMARY KEY,
  label TEXT,
  note TEXT,
  added_at TEXT NOT NULL,
  last_fetched_at TEXT,
  followers_count BIGINT,
  media_count BIGINT,
  last_error TEXT
);

CREATE TABLE IF NOT EXISTS peer_media (
  username TEXT NOT NULL,
  media_id TEXT NOT NULL,
  media_type TEXT,
  product_type TEXT,
  permalink TEXT,
  caption TEXT,
  posted_at TEXT,
  like_count BIGINT,
  comments_count BIGINT,
  captured_at TEXT NOT NULL,
  PRIMARY KEY (username, media_id)
);

CREATE TABLE IF NOT EXISTS hashtag_queries (
  hashtag TEXT PRIMARY KEY,
  hashtag_id TEXT,
  queried_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hashtag_media (
  hashtag TEXT NOT NULL,
  media_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  media_type TEXT,
  permalink TEXT,
  caption TEXT,
  posted_at TEXT,
  like_count BIGINT,
  comments_count BIGINT,
  captured_at TEXT NOT NULL,
  PRIMARY KEY (hashtag, media_id, kind)
);

CREATE TABLE IF NOT EXISTS market_notes (
  note_id TEXT PRIMARY KEY,
  topic TEXT NOT NULL,
  summary TEXT NOT NULL,
  source_url TEXT,
  source_title TEXT,
  region TEXT,
  language TEXT,
  confidence TEXT,
  collected_at TEXT NOT NULL,
  expires_at TEXT
);

CREATE TABLE IF NOT EXISTS findings (
  finding_id TEXT PRIMARY KEY,
  ig_user_id TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  category TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT,
  evidence_json TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS recommendations (
  rec_id TEXT PRIMARY KEY,
  ig_user_id TEXT NOT NULL,
  source TEXT NOT NULL,
  rule_id TEXT,
  finding_ids TEXT,
  note_ids TEXT,
  priority BIGINT NOT NULL,
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  why TEXT,
  action TEXT NOT NULL,
  expected_effect TEXT,
  confidence TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  baseline_json TEXT,
  outcome_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  done_at TEXT,
  dismissed_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_findings_account ON findings (ig_user_id, status);
CREATE INDEX IF NOT EXISTS idx_recs_account ON recommendations (ig_user_id, status);

-- v3: YouTube. findings and recommendations are shared with Instagram: their ig_user_id column holds the account id, which is the channel id for YouTube.
CREATE TABLE IF NOT EXISTS yt_channels (
  channel_id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  title TEXT,
  handle TEXT,
  uploads_playlist TEXT,
  created_at TEXT NOT NULL,
  last_collected_at TEXT,
  analytics_ok BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS yt_videos (
  video_id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  slug TEXT,
  kind TEXT,
  title TEXT,
  published_at TEXT,
  duration_s BIGINT,
  privacy TEXT,
  thumbnail_url TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ytv_channel ON yt_videos (channel_id, published_at);
CREATE INDEX IF NOT EXISTS idx_ytv_slug ON yt_videos (slug);

CREATE TABLE IF NOT EXISTS yt_snapshots (
  video_id TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  views BIGINT,
  likes BIGINT,
  comments BIGINT,
  minutes_watched DOUBLE PRECISION,
  avg_view_s DOUBLE PRECISION,
  avg_view_pct DOUBLE PRECISION,
  subs_gained BIGINT,
  subs_lost BIGINT,
  shares BIGINT,
  PRIMARY KEY (video_id, captured_at)
);

CREATE TABLE IF NOT EXISTS yt_daily (
  channel_id TEXT NOT NULL,
  period_end TEXT NOT NULL,
  metric TEXT NOT NULL,
  value DOUBLE PRECISION,
  collected_at TEXT NOT NULL,
  PRIMARY KEY (channel_id, period_end, metric)
);

CREATE TABLE IF NOT EXISTS yt_traffic (
  channel_id TEXT NOT NULL,
  captured_on TEXT NOT NULL,
  source TEXT NOT NULL,
  views BIGINT,
  minutes DOUBLE PRECISION,
  PRIMARY KEY (channel_id, captured_on, source)
);

CREATE TABLE IF NOT EXISTS yt_audience (
  channel_id TEXT NOT NULL,
  captured_on TEXT NOT NULL,
  breakdown TEXT NOT NULL,
  bucket TEXT NOT NULL,
  value DOUBLE PRECISION,
  PRIMARY KEY (channel_id, captured_on, breakdown, bucket)
);

CREATE TABLE IF NOT EXISTS yt_retention (
  video_id TEXT NOT NULL,
  captured_on TEXT NOT NULL,
  ratio DOUBLE PRECISION NOT NULL,
  watch_ratio DOUBLE PRECISION,
  relative DOUBLE PRECISION,
  PRIMARY KEY (video_id, captured_on, ratio)
);

CREATE TABLE IF NOT EXISTS yt_comments (
  comment_id TEXT PRIMARY KEY,
  video_id TEXT NOT NULL,
  parent_id TEXT,
  username TEXT,
  author_channel_id TEXT,
  text TEXT,
  posted_at TEXT,
  like_count BIGINT,
  is_own BIGINT NOT NULL DEFAULT 0,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  category TEXT,
  language TEXT,
  sentiment TEXT,
  tagged_at TEXT,
  reply_status TEXT
);

CREATE INDEX IF NOT EXISTS idx_ytc_video ON yt_comments (video_id, posted_at);
CREATE INDEX IF NOT EXISTS idx_ytc_parent ON yt_comments (parent_id);

CREATE TABLE IF NOT EXISTS yt_runs (
  run_id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  collectors TEXT,
  status TEXT NOT NULL,
  stats_json TEXT,
  errors_json TEXT
);

-- Also created from code by yt_hashtags.ensure and comment_reply.connect (same text); listed here so the Postgres migration has them.
CREATE TABLE IF NOT EXISTS yt_hashtag_posts (
  video_id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  tag TEXT NOT NULL,
  channel_id TEXT,
  published_at TEXT,
  duration_s BIGINT,
  views BIGINT,
  likes BIGINT,
  comments BIGINT,
  captured_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comment_replies (
  comment_id TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  account TEXT,
  draft TEXT,
  status TEXT NOT NULL,
  sent_id TEXT,
  error TEXT,
  drafted_at TEXT,
  edited_at TEXT,
  approved_at TEXT,
  sent_at TEXT
);

ALTER TABLE market_notes ADD COLUMN IF NOT EXISTS platform TEXT NOT NULL DEFAULT 'any';
