-- NAVAAN analytics schema. Portable SQL: TEXT, INTEGER, REAL, composite primary keys, no AUTOINCREMENT, no triggers.
-- SQLite today, Postgres later. analytics_db.migrate runs the statements one by one, so keep a semicolon out of every comment and default value.
-- Timestamps are UTC ISO strings (YYYY-MM-DDTHH:MM:SSZ). Dates are YYYY-MM-DD.

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
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
  like_count INTEGER,
  comments_count INTEGER,
  reach INTEGER,
  views INTEGER,
  saved INTEGER,
  shares INTEGER,
  reposts INTEGER,
  total_interactions INTEGER,
  avg_watch_time_ms REAL,
  total_watch_time_ms REAL,
  skip_rate REAL,
  follows INTEGER,
  profile_visits INTEGER,
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
  like_count INTEGER,
  hidden INTEGER NOT NULL DEFAULT 0,
  is_own INTEGER NOT NULL DEFAULT 0,
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
  value REAL,
  collected_at TEXT NOT NULL,
  PRIMARY KEY (ig_user_id, period_end, metric)
);

CREATE TABLE IF NOT EXISTS audience (
  ig_user_id TEXT NOT NULL,
  captured_on TEXT NOT NULL,
  breakdown TEXT NOT NULL,
  bucket TEXT NOT NULL,
  value INTEGER,
  PRIMARY KEY (ig_user_id, captured_on, breakdown, bucket)
);

CREATE TABLE IF NOT EXISTS online_hours (
  ig_user_id TEXT NOT NULL,
  captured_on TEXT NOT NULL,
  hour INTEGER NOT NULL,
  followers INTEGER,
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
  like_count INTEGER,
  comments_count INTEGER,
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
  followers_count INTEGER,
  media_count INTEGER,
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
  like_count INTEGER,
  comments_count INTEGER,
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
  like_count INTEGER,
  comments_count INTEGER,
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
  priority INTEGER NOT NULL,
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
