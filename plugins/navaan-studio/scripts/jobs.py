"""jobs.py  the job queue in Postgres (schema studio): enqueue, claim, heartbeat, finish, cancel, and the portal's view of a run.

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: replaces the in-process JOBS dictionary. The web server enqueues and reads; a worker process claims and runs. NAV-4 stage 2.

Rules
  one active job per item      a second enqueue for an item that is queued or running returns None (the old "a run is in progress")
  claim                        UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1): two workers never get the same job
  lease                        a running job has locked_until; the worker's heartbeat extends it. When it runs out the worker is presumed dead:
                               reap() puts the job back in the queue, or fails it when attempts reached max_attempts (default 2: one retry, SC-013)
  a step that fails            is a finished job with rc != 0, not a retry: the pipeline has its own bounded retries, and the person sees the failure
  cancel                       a queued job is canceled at once; a running one gets cancel_requested, and its worker stops it at the next heartbeat
"""
import json
import navaan_log as L
import studio_store as S
LOG = L.get("jobs")

KINDS = ("pipeline", "step", "redo", "scheduled")


def _c():
    return S._conn()


def _row(r):
    return dict(r) if r else None


def enqueue(slug, kind, payload=None, max_attempts=2):
    """Queue a job. Returns its id, or None when the item already has a queued or running job."""
    if kind not in KINDS: raise ValueError(f"bad job kind {kind!r}")
    S._check(slug)
    c = _c()
    try:
        r = c.execute("INSERT INTO jobs (slug, kind, payload, max_attempts) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING RETURNING id", (slug, kind, S._jsonb(payload or {}), max_attempts)).fetchone()
        c.commit()
    except Exception:
        c.rollback(); raise
    if r: L.event(LOG, "info", "job_queued", item=slug, kind=kind, job_id=str(r["id"]))
    return str(r["id"]) if r else None


def start_now(slug, kind, payload, worker, lease_s=120):
    """Record a job that this worker starts itself (the scheduler's steps): inserted as running. None when the item already has one."""
    S._check(slug)
    c = _c()
    try:
        r = c.execute("INSERT INTO jobs (slug, kind, payload, status, attempts, locked_by, locked_until, started_at) "
                      "VALUES (?, ?, ?, 'running', 1, ?, now() + (? * interval '1 second'), now()) ON CONFLICT DO NOTHING RETURNING id",
                      (slug, kind, S._jsonb(payload or {}), worker, lease_s)).fetchone()
        c.commit()
    except Exception:
        c.rollback(); raise
    return str(r["id"]) if r else None


def claim(worker, lease_s=120):
    """The oldest due queued job, now running under this worker's lease. None when there is nothing to do."""
    c = _c()
    try:
        r = c.execute("UPDATE jobs SET status = 'running', locked_by = ?, locked_until = now() + (? * interval '1 second'), attempts = attempts + 1, started_at = COALESCE(started_at, now()) "
                      "WHERE id = (SELECT id FROM jobs WHERE status = 'queued' AND run_at <= now() ORDER BY run_at, created_at FOR UPDATE SKIP LOCKED LIMIT 1) "
                      "RETURNING id, slug, kind, payload, attempts, max_attempts", (worker, lease_s)).fetchone()
        c.commit()
    except Exception:
        c.rollback(); raise
    if not r: return None
    j = _row(r); j["id"] = str(j["id"])
    L.event(LOG, "info", "job_claimed", item=j["slug"], kind=j["kind"], job_id=j["id"], worker=worker, attempt=j["attempts"])
    return j


def heartbeat(job_id, worker, progress=None, status_text=None, lease_s=120):
    """Extend the lease and publish progress. Returns "cancel" when a stop was requested, "lost" when the lease is no longer ours, else "ok"."""
    c = _c()
    try:
        r = c.execute("UPDATE jobs SET locked_until = now() + (? * interval '1 second'), progress = ?, status_text = ? "
                      "WHERE id = ? AND status = 'running' AND locked_by = ? RETURNING cancel_requested",
                      (lease_s, S._jsonb(progress or {}), status_text, job_id, worker)).fetchone()
        c.commit()
    except Exception:
        c.rollback(); raise
    return "lost" if not r else ("cancel" if r["cancel_requested"] else "ok")


def finish(job_id, worker, rc, error=None, status_text=None):
    c = _c()
    try:
        c.execute("UPDATE jobs SET status = CASE WHEN cancel_requested AND ? <> 0 THEN 'canceled' WHEN ? = 0 THEN 'done' ELSE 'failed' END, rc = ?, error = ?, "
                  "status_text = COALESCE(?, status_text), finished_at = now(), locked_until = NULL WHERE id = ? AND locked_by = ? AND status = 'running'",
                  (rc, rc, rc, (error or None) and str(error)[:500], status_text, job_id, worker))
        c.commit()
    except Exception:
        c.rollback(); raise


def reap():
    """Jobs whose lease ran out: back in the queue while they have attempts left, otherwise failed. Returns how many."""
    c = _c()
    try:
        rows = c.execute("UPDATE jobs SET status = CASE WHEN attempts < max_attempts THEN 'queued' ELSE 'failed' END, locked_by = NULL, locked_until = NULL, "
                         "error = 'the worker stopped before the job finished', rc = CASE WHEN attempts < max_attempts THEN NULL ELSE 1 END, "
                         "finished_at = CASE WHEN attempts < max_attempts THEN NULL ELSE now() END "
                         "WHERE status = 'running' AND locked_until < now() RETURNING id, slug, status, attempts").fetchall()
        c.commit()
    except Exception:
        c.rollback(); raise
    for r in rows: L.event(LOG, "warning", "job_lease_expired", item=r["slug"], job_id=str(r["id"]), now=r["status"], attempts=r["attempts"])
    return len(rows)


def release(worker):
    """A worker shutting down gives its leases back, so reap() retries its jobs immediately."""
    c = _c()
    try:
        n = c.execute("UPDATE jobs SET locked_until = now() - interval '1 second' WHERE locked_by = ? AND status = 'running'", (worker,)).rowcount
        c.commit(); return n
    except Exception:
        c.rollback(); raise


def request_cancel(slug):
    """The Stop button. True when there was an active job to stop."""
    c = _c()
    try:
        q = c.execute("UPDATE jobs SET status = 'canceled', finished_at = now(), status_text = 'stopped by you' WHERE slug = ? AND status = 'queued' RETURNING id", (slug,)).fetchone()
        r = c.execute("UPDATE jobs SET cancel_requested = true WHERE slug = ? AND status = 'running' RETURNING id", (slug,)).fetchone()
        c.commit()
    except Exception:
        c.rollback(); raise
    return bool(q or r)


def view(slug):
    """What the portal needs for an item: {"running": bool, "rc": int|None, "queued": bool, "progress": {...}, "status_text": str}. The latest job decides."""
    c = _c()
    try:
        r = c.run("SELECT id, status, rc, progress, status_text, error, locked_by FROM jobs WHERE slug = ? ORDER BY created_at DESC LIMIT 1", (slug,)).fetchone()
        c.commit()
    except Exception:
        c.rollback(); raise
    if not r: return {"running": False, "rc": None, "queued": False, "progress": {}, "status_text": ""}
    active = r["status"] in ("queued", "running")
    return {"running": active, "queued": r["status"] == "queued", "rc": r["rc"] if not active else None, "progress": r["progress"] or {},
            "status_text": r["status_text"] or "", "error": r["error"] or ""}


def active(slug):
    c = _c()
    try: r = c.run("SELECT 1 AS x FROM jobs WHERE slug = ? AND status IN ('queued', 'running')", (slug,)).fetchone(); c.commit(); return r is not None
    except Exception: c.rollback(); raise


def beat(worker, info=None):
    c = _c()
    try:
        c.execute("INSERT INTO workers (id, seen_at, info) VALUES (?, now(), ?) ON CONFLICT (id) DO UPDATE SET seen_at = now(), info = excluded.info", (worker, S._jsonb(info or {})))
        c.commit()
    except Exception:
        c.rollback(); raise


def workers_alive(max_age_s=90):
    c = _c()
    try:
        r = c.run("SELECT COUNT(*) AS n FROM workers WHERE seen_at > now() - (? * interval '1 second')", (max_age_s,)).fetchone(); c.commit()
        return r["n"]
    except Exception:
        c.rollback(); raise


def prune(days=30):
    """Finished jobs and stale worker rows older than `days` days."""
    c = _c()
    try:
        a = c.execute("DELETE FROM jobs WHERE status IN ('done', 'failed', 'canceled') AND finished_at < now() - (? * interval '1 day')", (days,)).rowcount
        c.execute("DELETE FROM workers WHERE seen_at < now() - interval '7 days'")
        c.commit()
        return a
    except Exception:
        c.rollback(); raise
