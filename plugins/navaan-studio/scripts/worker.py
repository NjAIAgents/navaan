"""worker.py  runs the jobs the web server queues, and the publishing schedule.

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: NAV-4 stage 2. A separate process (the `worker` service in compose.yml, or `navaan.py worker`) so that a deploy or a crash of the web server no longer
kills a running step, and a job interrupted by a restart is retried once instead of vanishing.

The worker claims jobs from studio.jobs (jobs.py) up to NAVAAN_WORKER_SLOTS at a time (default 2, different items in parallel), runs each in a thread exactly the way the web server
used to (navaan.pipeline / run / redo_run), and every few seconds extends the job's lease and publishes its progress (the old RUN and STATUS dictionaries) for the portal. A Stop
request arrives through the same heartbeat. The publishing schedule (publish_schedule.loop) runs here too, its steps recorded as jobs, unless NAVAAN_SCHEDULER=off.

Embedded mode: `navaan.py serve` starts this same worker in threads of the web process when NAVAAN_WORKER is not "external" (a development machine needs one process).
"""
import os, sys, time, socket, signal, threading
import navaan_log as L
import jobs as J
LOG = L.get("worker")

HEARTBEAT_S = 5
LEASE_S = 120          # a worker that stops beating for this long is presumed dead and its job is retried
ALIVE_FILE = os.environ.get("NAVAAN_WORKER_ALIVE_FILE", "/tmp/navaan-worker.alive")


def scheduler_wanted():
    return os.environ.get("NAVAAN_SCHEDULER", "on").lower() != "off"


def external():
    return os.environ.get("NAVAAN_WORKER", "embedded").lower() == "external"


class Worker:
    def __init__(self, slots=None, scheduler=None, name=None):
        self.id = name or f"{socket.gethostname()}-{os.getpid()}"
        self.slots = int(slots or os.environ.get("NAVAAN_WORKER_SLOTS", "2"))
        self.scheduler = scheduler_wanted() if scheduler is None else scheduler
        self.running = {}            # job id -> thread
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._housekeeping_at = 0.0

    # ---- running one job ---------------------------------------------------------------------------------------------------
    def _call(self, slug, kind, payload):
        import navaan as N
        if kind == "pipeline": return N.pipeline(slug, wait=True)
        if kind == "redo": return N.redo_run(slug, payload.get("step"))
        return N.run(slug, step=payload.get("step"))           # "step" and "scheduled"

    def run_job(self, job_id, slug, kind, payload):
        """Run one job to the end and record how it went. Returns the exit code. Never raises."""
        import navaan as N
        done = threading.Event(); flags = {"cancel": False, "lost": False}
        N.RUN.pop(slug, None); N.STOP.discard(slug)
        def beat():
            while not done.wait(HEARTBEAT_S):
                try: r = J.heartbeat(job_id, self.id, dict(N.RUN.get(slug) or {}), N.STATUS.get(slug, ""), LEASE_S)
                except Exception: L.exc(LOG, "heartbeat_failed"); continue
                if r == "cancel" and not flags["cancel"]: flags["cancel"] = True; L.event(LOG, "info", "job_cancel_requested"); N.stop(slug)
                if r == "lost" and not flags["lost"]: flags["lost"] = True; L.event(LOG, "error", "job_lease_lost", note="another worker may now run this item")
        hb = threading.Thread(target=beat, daemon=True); hb.start()
        err = None
        with L.ctx(item=slug, job_id=job_id, step=payload.get("step") or ""):
            L.event(LOG, "info", "job_started", kind=kind, worker=self.id)
            try: rc = self._call(slug, kind, payload)
            except SystemExit as e: rc = 1; err = str(e.code)[:300]; L.event(LOG, "warning", "job_stopped", exit=err)   # sys.exit("message") from a step: the message is the reason
            except Exception as e: rc = 1; err = f"{type(e).__name__}: {e}"[:300]; L.exc(LOG, "job_crashed")
            finally: done.set(); hb.join(HEARTBEAT_S + 2)
            rc = 1 if rc is None else int(rc)
            L.event(LOG, "info" if rc == 0 else "warning", "job_finished", rc=rc)
        try:
            J.heartbeat(job_id, self.id, dict(N.RUN.get(slug) or {}), N.STATUS.get(slug, ""), LEASE_S)   # the last progress (which step failed, its log) stays visible
            J.finish(job_id, self.id, rc, err, status_text="" if rc == 0 else None)
        except Exception:
            L.exc(LOG, "job_finish_failed", job_id=job_id)
        if rc == 0: N.STATUS.pop(slug, None)
        try:
            import catalog_store; catalog_store.sync_item(slug)   # a run may have published or archived the song: the catalog follows
        except Exception: L.exc(LOG, "catalog_sync_failed", item=slug)
        return rc

    # ---- the scheduler's steps ---------------------------------------------------------------------------------------------
    def fire(self, slug, sid):
        jid = J.start_now(slug, "scheduled", {"step": sid}, self.id, LEASE_S)
        if not jid: L.event(LOG, "warning", "scheduled_step_skipped", item=slug, step=sid, reason="the item already has an active job"); return 75
        return self.run_job(jid, slug, "scheduled", {"step": sid})

    def skip(self, slug):
        try:
            import navaan_ui
            return J.active(slug) or navaan_ui.scheduler_state() == "paused"
        except Exception:
            L.exc(LOG, "scheduler_skip_check_failed"); return True

    # ---- the loop ----------------------------------------------------------------------------------------------------------
    def _spawn(self, job):
        def go():
            try: self.run_job(job["id"], job["slug"], job["kind"], job["payload"] or {})
            finally:
                with self._lock: self.running.pop(job["id"], None)
        t = threading.Thread(target=go, name=f"job-{job['slug']}", daemon=True)
        with self._lock: self.running[job["id"]] = t
        t.start()

    def step(self):
        """One pass: beat, housekeeping, claim while there is a free slot. Returns how many jobs it started."""
        J.beat(self.id, {"slots": self.slots, "running": len(self.running), "scheduler": self.scheduler})
        try: open(ALIVE_FILE, "w").write(str(time.time()))
        except OSError as e: L.ignored(LOG, "cannot touch the alive file", e)
        now = time.time()
        if now - self._housekeeping_at > 15:
            self._housekeeping_at = now
            J.reap()
        started = 0
        while len(self.running) < self.slots and not self.stop_event.is_set():
            job = J.claim(self.id, LEASE_S)
            if not job: break
            self._spawn(job); started += 1
        return started

    def run_forever(self):
        L.event(LOG, "info", "worker_started", worker=self.id, slots=self.slots, scheduler=self.scheduler)
        if self.scheduler:
            import publish_schedule as PS
            threading.Thread(target=PS.loop, args=(self.fire, self.skip), name="scheduler", daemon=True).start()
        last_prune = 0.0
        while not self.stop_event.is_set():
            try: self.step()
            except Exception: L.exc(LOG, "worker_pass_failed")
            if time.time() - last_prune > 3600:
                last_prune = time.time()
                try: J.prune()
                except Exception: L.exc(LOG, "prune_failed")
            self.stop_event.wait(2)
        L.event(LOG, "info", "worker_stopping", worker=self.id, running=len(self.running))

    def release(self):
        """On a clean shutdown: give our leases back so the next worker retries those jobs at once instead of after the lease runs out."""
        try: J.release(self.id)
        except Exception: L.exc(LOG, "release_failed")


def start_background(slots=None):
    """Embedded mode: the worker in threads of this process. Returns the Worker."""
    w = Worker(slots=slots)
    threading.Thread(target=w.run_forever, name="worker", daemon=True).start()
    return w


def main(argv=None):
    a = argv or []
    slots = a[a.index("--slots") + 1] if "--slots" in a else None
    w = Worker(slots=slots)
    def bye(sig, frm): w.stop_event.set(); w.release()
    signal.signal(signal.SIGTERM, bye); signal.signal(signal.SIGINT, bye)
    w.run_forever()
    return 0
