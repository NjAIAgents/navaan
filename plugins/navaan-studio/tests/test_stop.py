import os, sys, io, time, threading, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import navaan


class Stop(unittest.TestCase):
    def test_stop_ends_the_running_step_and_what_it_started(self):
        out = {}
        env = mock.patch.dict(os.environ, {"NAVAAN_ROOT": tempfile.mkdtemp()}); env.start(); self.addCleanup(env.stop)
        def go():
            with open(os.devnull, "w") as lf: out["rc"] = navaan.run_cmd(["bash", "-c", "sleep 60 & wait"], lf, None, "stop-test")
        t = threading.Thread(target=go); t.start()
        for _ in range(50):
            if "stop-test" in navaan.PROC: break
            time.sleep(0.1)
        self.assertIn("stop-test", navaan.PROC)
        t0 = time.time(); self.assertTrue(navaan.stop("stop-test")); t.join(15)
        self.assertFalse(t.is_alive()); self.assertLess(time.time() - t0, 12)
        self.assertNotEqual(out["rc"], 0)
        self.assertNotIn("stop-test", navaan.PROC)
        navaan.STOP.discard("stop-test")

    def test_wiring(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
        ui = open(os.path.join(root, "ui.html"), encoding="utf-8").read(); srv = open(os.path.join(root, "navaan_ui.py"), encoding="utf-8").read()
        self.assertIn("stopIt()", ui); self.assertIn("/api/stop", ui + srv); self.assertIn("jobs.request_cancel(slug)", srv)   # the web server asks; the worker stops the step at its next heartbeat
        self.assertIn("N.stop(slug)", open(os.path.join(root, "worker.py"), encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()
