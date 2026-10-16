"""NAV-4 stage 2: the worker runs queued jobs the way the web server used to, logs them, retries a lost one once and honours Stop."""
import io, json, os, sys, tempfile, threading, time, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import navaan_common as C, navaan_log as L, studio_store as S, jobs as J, worker as W
import navaan


class Base(unittest.TestCase):
    def setUp(self):
        L.reset_for_tests()
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "songs"); os.makedirs(self.root)
        for p in (mock.patch.object(C, "songs_root", lambda: self.root),
                  mock.patch.dict(os.environ, {"NAVAAN_LOG_DIR": os.path.join(self.tmp.name, "logs"), "NAVAAN_LOG_LEVEL": "DEBUG"}),
                  mock.patch.object(W, "ALIVE_FILE", os.path.join(self.tmp.name, "alive")), mock.patch.object(W, "HEARTBEAT_S", 0.1)):
            p.start(); self.addCleanup(p.stop)
        self.out = io.StringIO(); so = sys.stdout; sys.stdout = self.out; self.addCleanup(lambda: setattr(sys, "stdout", so))
        L.setup(stdout=True); self.addCleanup(L.reset_for_tests)
        S._LOCAL.conn = None
        self.addCleanup(lambda: getattr(S._LOCAL, "conn", None) and S._LOCAL.conn.close())
        navaan.RUN.clear(); navaan.STATUS.clear(); navaan.STOP.clear()
        self.w = W.Worker(slots=2, scheduler=False, name="test-worker")

    def recs(self, event=None):
        rs = [json.loads(x) for x in self.out.getvalue().splitlines() if x.strip().startswith("{")]
        return [r for r in rs if r["event"] == event] if event else rs

    def wait_idle(self, secs=10):
        t0 = time.time()
        while self.w.running and time.time() - t0 < secs: time.sleep(0.05)


class Running(Base):
    def test_a_step_job_runs_and_is_recorded_as_done(self):
        J.enqueue("song-001", "step", {"step": "lyrics"})
        with mock.patch.object(navaan, "run", return_value=0) as run:
            self.assertEqual(self.w.step(), 1); self.wait_idle()
        run.assert_called_once_with("song-001", step="lyrics")
        v = J.view("song-001"); self.assertEqual((v["running"], v["rc"], v["status_text"]), (False, 0, ""))

    def test_the_three_kinds_call_the_right_pipeline_function(self):
        for kind, payload, target, args in (("pipeline", {"all": True}, "pipeline", ("song-001",)), ("redo", {"step": "visuals"}, "redo_run", ("song-002", "visuals"))):
            J.enqueue(args[0], kind, payload)
            with mock.patch.object(navaan, target, return_value=0) as f:
                self.w.step(); self.wait_idle()
            self.assertEqual(f.call_args.args, args)

    def test_a_crash_is_logged_once_with_item_job_id_and_stack_and_the_run_file_has_it(self):
        J.enqueue("song-777", "step", {"step": "video"})
        with mock.patch.object(navaan, "run", side_effect=ValueError("render exploded")):
            self.w.step(); self.wait_idle()
        c = self.recs("job_crashed")[0]
        self.assertEqual((c["item"], c["step"], c["error"]["type"]), ("song-777", "video", "ValueError")); self.assertIn("render exploded", c["error"]["message"])
        evs = [json.loads(x)["event"] for x in open(os.path.join(self.tmp.name, "logs", "runs", c["job_id"] + ".jsonl"), encoding="utf-8").read().splitlines()]
        self.assertEqual([e for e in evs if e.startswith("job_")], ["job_queued", "job_claimed", "job_started", "job_crashed", "job_finished"])
        v = J.view("song-777"); self.assertEqual((v["running"], v["rc"]), (False, 1)); self.assertIn("ValueError", v["error"])

    def test_a_step_that_exits_with_a_message_keeps_the_message(self):
        J.enqueue("song-778", "step", {"step": "quote"})
        with mock.patch.object(navaan, "run", side_effect=SystemExit("quote.json is missing")):
            self.w.step(); self.wait_idle()
        self.assertEqual(self.recs("job_stopped")[0]["exit"], "quote.json is missing"); self.assertEqual(J.view("song-778")["error"], "quote.json is missing")

    def test_progress_and_status_reach_the_portal_while_the_job_runs_and_after_a_failure(self):
        J.enqueue("song-001", "step", {"step": "video"})
        def slow(slug, step=None):
            navaan.RUN[slug] = {"step": "video", "attempt": 1, "started": time.time()}; navaan.STATUS[slug] = "running video"; time.sleep(0.5)
            navaan.RUN[slug] = {"step": None, "failed": "video", "log": "logs/video.log"}; return 1
        with mock.patch.object(navaan, "run", side_effect=slow):
            self.w.step(); time.sleep(0.3)
            v = J.view("song-001"); self.assertEqual((v["running"], v["progress"].get("step"), v["status_text"]), (True, "video", "running video"))
            self.wait_idle()
        v = J.view("song-001"); self.assertEqual((v["running"], v["rc"], v["progress"].get("failed")), (False, 1, "video"))

    def test_a_duplicate_trigger_runs_once(self):
        runs = []
        self.assertTrue(J.enqueue("song-001", "pipeline", {"all": True})); self.assertIsNone(J.enqueue("song-001", "pipeline", {"all": True}))
        with mock.patch.object(navaan, "pipeline", side_effect=lambda s, wait=False: runs.append(s) or 0):
            self.w.step(); self.w.step(); self.wait_idle()
        self.assertEqual(runs, ["song-001"])

    def test_slots_limit_parallel_jobs(self):
        for i in range(4): J.enqueue(f"song-00{i}", "step", {"step": "x"})
        gate = threading.Event()
        with mock.patch.object(navaan, "run", side_effect=lambda s, step=None: gate.wait(5) and 0):
            self.assertEqual(self.w.step(), 2); self.assertEqual(self.w.step(), 0)   # two slots busy: nothing more is claimed
            gate.set(); self.wait_idle()
            self.assertEqual(self.w.step(), 2); gate.set(); self.wait_idle()


class StopAndRestart(Base):
    def test_stop_from_the_portal_reaches_the_running_step(self):
        J.enqueue("song-001", "step", {"step": "video"})
        stopped = threading.Event()
        def long(slug, step=None):
            while not stopped.wait(0.05): pass
            return 130
        with mock.patch.object(navaan, "run", side_effect=long), mock.patch.object(navaan, "stop", side_effect=lambda s: stopped.set() or True) as stop:
            self.w.step(); time.sleep(0.2); self.assertTrue(J.request_cancel("song-001")); self.wait_idle()
        stop.assert_called_with("song-001")
        c = S._conn(); st = c.execute("SELECT status FROM jobs WHERE slug = 'song-001'").fetchone()["status"]; c.commit(); self.assertEqual(st, "canceled")

    def test_a_job_interrupted_by_a_restart_is_retried_once_by_the_next_worker(self):
        J.enqueue("song-001", "pipeline", {"all": True})
        j = J.claim("dead-worker")                       # claimed, then the worker dies: no heartbeat, no finish
        c = S._conn(); c.execute("UPDATE jobs SET locked_until = now() - interval '1 minute'"); c.commit()
        runs = []
        with mock.patch.object(navaan, "pipeline", side_effect=lambda s, wait=False: runs.append(s) or 0):
            self.w.step(); self.wait_idle()
        self.assertEqual(runs, ["song-001"]); v = J.view("song-001"); self.assertEqual((v["running"], v["rc"]), (False, 0))
        c = S._conn(); n = c.execute("SELECT attempts FROM jobs").fetchone()["attempts"]; c.commit(); self.assertEqual(n, 2)

    def test_a_clean_shutdown_gives_leases_back(self):
        J.enqueue("song-001", "pipeline"); J.claim("test-worker"); self.assertEqual(J.release("test-worker"), 1)
        self.assertEqual(J.reap(), 1); self.assertTrue(J.view("song-001")["queued"])


class Scheduler(Base):
    def test_a_scheduled_step_is_recorded_as_a_job_and_blocked_by_an_active_one(self):
        with mock.patch.object(navaan, "run", return_value=0) as run:
            self.assertEqual(self.w.fire("song-001", "publish_instagram"), 0)
        run.assert_called_once_with("song-001", step="publish_instagram")
        c = S._conn(); r = c.execute("SELECT kind, status, rc FROM jobs").fetchone(); c.commit(); self.assertEqual((r["kind"], r["status"], r["rc"]), ("scheduled", "done", 0))
        J.enqueue("song-002", "pipeline"); self.assertEqual(self.w.fire("song-002", "go_public"), 75)

    def test_embedded_or_external(self):
        with mock.patch.dict(os.environ, {"NAVAAN_WORKER": "external"}): self.assertTrue(W.external())
        with mock.patch.dict(os.environ, {"NAVAAN_WORKER": "embedded"}): self.assertFalse(W.external())

    def test_the_alive_file_and_the_worker_row_are_written_each_pass(self):
        self.w.step(); self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "alive"))); self.assertEqual(J.workers_alive(), 1)


if __name__ == "__main__":
    unittest.main()
