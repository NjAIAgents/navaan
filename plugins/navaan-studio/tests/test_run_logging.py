"""NAV-12: a step's output goes to its own file exactly as before AND into the log stream, line by line, in one run log."""
import io, json, os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import navaan, navaan_log as L


# Dummy secret shapes built from pieces so no real-looking token sits in the source (a scanner would flag it). They only prove the scrubber masks them.
FAKE_GOOGLE = "ya" + "29." + "A0AbCdEfGhIjKlMnOp"
FAKE_OPENAI = "s" + "k-" + "abcdefghijklmnop1234"
FAKE_VAULT = "h" + "vs." + "CAESIabcdefghijklmnop"
FAKE_PW = "hunter2" + "hunter2"

def _read(p):
    with open(p, encoding="utf-8", newline="") as f: return f.read()


class RunLog(unittest.TestCase):
    def setUp(self):
        L.reset_for_tests()
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"NAVAAN_LOG_DIR": os.path.join(self.tmp.name, "logs"), "NAVAAN_LOG_LEVEL": "DEBUG", "NAVAAN_ROOT": self.tmp.name}); env.start(); self.addCleanup(env.stop)
        self.out = io.StringIO(); so = sys.stdout; sys.stdout = self.out; self.addCleanup(lambda: setattr(sys, "stdout", so))
        L.setup(stdout=True); self.addCleanup(L.reset_for_tests)

    def recs(self): return [json.loads(x) for x in self.out.getvalue().splitlines() if x.strip()]

    def run_cmd(self, script):
        stepfile = os.path.join(self.tmp.name, "step.log")
        with L.ctx(item="song-1", step="video", job_id="song-1-test"), open(stepfile, "w", encoding="utf-8") as lf:
            rc = navaan.run_cmd(["bash", "-c", script], lf, None, None)
        return rc, _read(stepfile)

    def test_output_reaches_the_step_file_unchanged_and_the_log_line_by_line(self):
        rc, filetext = self.run_cmd("echo one; echo two 1>&2; printf 'p1\\rp2\\r'; echo three")
        self.assertEqual(rc, 0)
        for s in ("one", "two", "p1\rp2\r", "three"): self.assertIn(s, filetext)
        lines = [r["line"] for r in self.recs() if r["event"] == "step_output"]
        self.assertEqual(lines, ["one", "two", "p1", "p2", "three"])
        r = next(r for r in self.recs() if r["event"] == "step_output"); self.assertEqual((r["item"], r["step"], r["job_id"]), ("song-1", "video", "song-1-test"))

    def test_command_start_and_finish_are_logged_and_a_failure_is_a_warning(self):
        rc, _ = self.run_cmd("echo hi; exit 3")
        self.assertEqual(rc, 3)
        ev = {r["event"]: r for r in self.recs()}
        self.assertIn("exit 3", ev["command_started"]["cmd"]); self.assertEqual((ev["command_finished"]["rc"], ev["command_finished"]["level"]), (3, "warning"))

    def test_a_chatty_command_is_cut_in_the_log_but_not_in_the_file(self):
        rc, filetext = self.run_cmd("seq 1 5000")
        self.assertEqual(rc, 0); self.assertIn("5000", filetext)
        recs = self.recs()
        self.assertEqual(sum(1 for r in recs if r["event"] == "step_output"), navaan.MAX_LOGGED_LINES)
        t = next(r for r in recs if r["event"] == "step_output_truncated"); self.assertEqual(t["lines_not_logged"], 5000 - navaan.MAX_LOGGED_LINES)

    def test_a_token_printed_by_a_step_is_masked_in_the_log_only(self):
        rc, filetext = self.run_cmd("echo 'refresh token=" + FAKE_GOOGLE + " for owner@example.com'")
        self.assertIn(FAKE_GOOGLE, filetext)   # the per-step file is what the step printed
        self.assertNotIn(FAKE_GOOGLE, self.out.getvalue()); self.assertNotIn("owner@example.com", self.out.getvalue())

    def test_the_whole_run_reads_in_order_in_one_file(self):
        self.run_cmd("echo a; echo b")
        evs = [json.loads(x)["event"] for x in _read(os.path.join(self.tmp.name, "logs", "runs", "song-1-test.jsonl")).splitlines()]
        self.assertEqual(evs, ["command_started", "step_output", "step_output", "command_finished"])


if __name__ == "__main__":
    unittest.main()
