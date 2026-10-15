"""NAV-4 stage 2: the job queue (jobs.py). One active job per item, claims that never double up, leases, a retry after a lost worker, cancel."""
import os, sys, tempfile, threading, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import navaan_common as C
import studio_store as S
import jobs as J


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "songs"); os.makedirs(self.root)
        p = mock.patch.object(C, "songs_root", lambda: self.root); p.start(); self.addCleanup(p.stop)
        S._LOCAL.conn = None
        self.addCleanup(lambda: getattr(S._LOCAL, "conn", None) and S._LOCAL.conn.close())

    def sql(self, q, params=()):
        c = S._conn()
        try: r = c.execute(q, params).fetchall() if q.lstrip().upper().startswith("SELECT") else c.execute(q, params).rowcount; c.commit(); return r
        except Exception: c.rollback(); raise

    def expire(self, slug):
        self.sql("UPDATE jobs SET locked_until = now() - interval '1 minute' WHERE slug = ? AND status = 'running'", (slug,))


class Queue(Base):
    def test_one_active_job_per_item(self):
        a = J.enqueue("song-001", "pipeline", {"all": True})
        self.assertTrue(a); self.assertIsNone(J.enqueue("song-001", "step", {"step": "x"}))
        self.assertTrue(J.enqueue("song-002", "pipeline"))
        j = J.claim("w1"); J.finish(j["id"], "w1", 0)
        self.assertTrue(J.enqueue(j["slug"], "pipeline"), "free again once the job has finished")

    def test_bad_kind_and_slug_are_refused(self):
        self.assertRaises(ValueError, J.enqueue, "song-001", "rm -rf")
        self.assertRaises(ValueError, J.enqueue, "../x", "pipeline")

    def test_start_now_takes_the_slot_or_says_it_is_taken(self):
        self.assertTrue(J.start_now("song-001", "scheduled", {"step": "go_public"}, "w1"))
        self.assertIsNone(J.start_now("song-001", "scheduled", {"step": "go_public"}, "w2"))
        self.assertIsNone(J.enqueue("song-001", "pipeline"))


class Claims(Base):
    def test_parallel_workers_never_get_the_same_job(self):
        for i in range(24): J.enqueue(f"song-{i:03d}", "pipeline")
        got, lock = [], threading.Lock()
        def work(name):
            while True:
                j = J.claim(name)
                if not j: return
                with lock: got.append(j["slug"])
        ts = [threading.Thread(target=work, args=(f"w{i}",)) for i in range(4)]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertEqual(sorted(got), [f"song-{i:03d}" for i in range(24)])

    def test_a_job_scheduled_later_is_not_claimed_yet(self):
        J.enqueue("song-001", "pipeline"); self.sql("UPDATE jobs SET run_at = now() + interval '1 hour'")
        self.assertIsNone(J.claim("w1"))


class Lease(Base):
    def test_a_lost_worker_gets_one_retry_then_the_job_fails(self):
        J.enqueue("song-001", "pipeline")
        j = J.claim("w1"); self.assertEqual(j["attempts"], 1)
        self.expire("song-001"); self.assertEqual(J.reap(), 1)
        self.assertTrue(J.view("song-001")["queued"])
        j = J.claim("w2"); self.assertEqual(j["attempts"], 2)
        self.expire("song-001"); self.assertEqual(J.reap(), 1)
        v = J.view("song-001"); self.assertEqual((v["running"], v["rc"]), (False, 1))
        self.assertIn("worker stopped", v["error"])

    def test_a_live_lease_is_not_reaped_and_a_heartbeat_extends_it(self):
        J.enqueue("song-001", "pipeline"); j = J.claim("w1")
        self.assertEqual(J.reap(), 0)
        self.assertEqual(J.heartbeat(j["id"], "w1", {"step": "lyrics", "attempt": 1}, "running lyrics"), "ok")
        v = J.view("song-001"); self.assertEqual((v["running"], v["progress"]["step"], v["status_text"]), (True, "lyrics", "running lyrics"))

    def test_a_worker_that_lost_its_lease_is_told(self):
        J.enqueue("song-001", "pipeline"); j = J.claim("w1")
        self.expire("song-001"); J.reap(); J.claim("w2")
        self.assertEqual(J.heartbeat(j["id"], "w1", {}, ""), "lost")
        J.finish(j["id"], "w1", 0)   # a stale finish must not close the job w2 is running
        self.assertTrue(J.view("song-001")["running"])


class Finish(Base):
    def test_done_failed_and_the_view(self):
        J.enqueue("song-001", "pipeline"); j = J.claim("w1"); J.finish(j["id"], "w1", 0, status_text="all steps done")
        v = J.view("song-001"); self.assertEqual((v["running"], v["rc"], v["status_text"]), (False, 0, "all steps done"))
        J.enqueue("song-001", "pipeline"); j = J.claim("w1"); J.finish(j["id"], "w1", 3, error="step lyrics failed")
        v = J.view("song-001"); self.assertEqual((v["rc"], v["error"]), (3, "step lyrics failed"))
        self.assertEqual(J.view("song-404"), {"running": False, "rc": None, "queued": False, "progress": {}, "status_text": ""})

    def test_cancel_a_queued_job_is_immediate_and_a_running_one_is_flagged(self):
        J.enqueue("song-001", "pipeline"); self.assertTrue(J.request_cancel("song-001")); self.assertFalse(J.view("song-001")["running"])
        J.enqueue("song-002", "pipeline"); j = J.claim("w1")
        self.assertTrue(J.request_cancel("song-002")); self.assertEqual(J.heartbeat(j["id"], "w1", {}, ""), "cancel")
        J.finish(j["id"], "w1", 130)
        self.assertEqual(self.sql("SELECT status FROM jobs WHERE slug = 'song-002'")[0]["status"], "canceled")
        self.assertFalse(J.request_cancel("song-003"))


class Workers(Base):
    def test_alive_counts_recent_beats_only(self):
        self.assertEqual(J.workers_alive(), 0)
        J.beat("w1", {"slots": 2}); self.assertEqual(J.workers_alive(), 1)
        self.sql("UPDATE workers SET seen_at = now() - interval '10 minutes'"); self.assertEqual(J.workers_alive(), 0)

    def test_prune_removes_old_finished_jobs_only(self):
        J.enqueue("song-001", "pipeline"); j = J.claim("w1"); J.finish(j["id"], "w1", 0)
        J.enqueue("song-002", "pipeline")
        self.sql("UPDATE jobs SET finished_at = now() - interval '40 days' WHERE status = 'done'")
        self.assertEqual(J.prune(30), 1); self.assertTrue(J.view("song-002")["queued"])


if __name__ == "__main__":
    unittest.main()
