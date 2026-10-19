-- NAV-68: sentiment of the audience's comments, scored by Claude. comments and yt_comments already keep sentiment, category (the themes),
-- language and tagged_at, and the collectors leave them alone; this adds the confidence and a log of scoring runs. Expand only.
ALTER TABLE comments ADD COLUMN IF NOT EXISTS sentiment_conf DOUBLE PRECISION;
ALTER TABLE yt_comments ADD COLUMN IF NOT EXISTS sentiment_conf DOUBLE PRECISION;
CREATE TABLE IF NOT EXISTS sentiment_runs (
  id          BIGSERIAL PRIMARY KEY,
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  scored      BIGINT NOT NULL DEFAULT 0,
  chars       BIGINT NOT NULL DEFAULT 0,
  error       TEXT
);
