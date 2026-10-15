-- NAVAAN studio, schema "studio": the job queue and the workers (NAV-4 stage 2). Replaces the in-process JOBS dictionary and the scheduler thread of the web server.
-- One active job per item (queued or running): a duplicate trigger finds the slot taken. A worker claims with FOR UPDATE SKIP LOCKED and holds a lease
-- (locked_until) that its heartbeat extends; a lease that runs out means the worker died, and the job is retried until max_attempts. Released: never edit, add 0003.

CREATE TABLE jobs (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug              text NOT NULL,
  kind              text NOT NULL CHECK (kind IN ('pipeline', 'step', 'redo', 'scheduled')),
  payload           jsonb NOT NULL DEFAULT '{}'::jsonb,
  status            text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'done', 'failed', 'canceled')),
  run_at            timestamptz NOT NULL DEFAULT now(),
  attempts          integer NOT NULL DEFAULT 0,
  max_attempts      integer NOT NULL DEFAULT 2,
  locked_by         text,
  locked_until      timestamptz,
  cancel_requested  boolean NOT NULL DEFAULT false,
  progress          jsonb NOT NULL DEFAULT '{}'::jsonb,   -- what the portal shows for a running job: step, attempt, failed, log (the old RUN dictionary)
  status_text       text,                                  -- the old STATUS text
  rc                integer,
  error             text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  started_at        timestamptz,
  finished_at       timestamptz
);

CREATE UNIQUE INDEX jobs_one_active_per_item ON jobs (slug) WHERE status IN ('queued', 'running');
CREATE INDEX jobs_claim_idx ON jobs (run_at) WHERE status = 'queued';
CREATE INDEX jobs_latest_idx ON jobs (slug, created_at DESC);

CREATE TABLE workers (
  id       text PRIMARY KEY,
  seen_at  timestamptz NOT NULL DEFAULT now(),
  info     jsonb NOT NULL DEFAULT '{}'::jsonb
);
