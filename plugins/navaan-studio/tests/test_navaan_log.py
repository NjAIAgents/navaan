"""NAV-12: structured logging (spec 002 FR-034, FR-035, SC-014)."""
import io, json, os, sys, tempfile, unittest, contextlib, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import navaan_log as L


# Dummy secret shapes built from pieces so no real-looking token sits in the source (a scanner would flag it). They only prove the scrubber masks them.
FAKE_GOOGLE = "ya" + "29." + "A0AbCdEfGhIjKlMnOp"
FAKE_OPENAI = "s" + "k-" + "abcdefghijklmnop1234"
FAKE_VAULT = "h" + "vs." + "CAESIabcdefghijklmnop"
FAKE_PW = "hunter2" + "hunter2"

def _read(p):
    with open(p, encoding="utf-8") as f: return f.read()


class LogCase(unittest.TestCase):
    def setUp(self):
        L.reset_for_tests()
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        os.environ["NAVAAN_LOG_DIR"] = self.tmp.name; os.environ["NAVAAN_LOG_LEVEL"] = "DEBUG"
        self.out = io.StringIO(); self._so = sys.stdout; sys.stdout = self.out
        self.addCleanup(self._restore)
        L.setup(stdout=True)
        self.log = L.get("test")

    def _restore(self):
        sys.stdout = self._so; L.reset_for_tests(); os.environ.pop("NAVAAN_LOG_DIR", None); os.environ.pop("NAVAAN_LOG_LEVEL", None)

    def lines(self): return [json.loads(x) for x in self.out.getvalue().splitlines() if x.strip()]
    def file_lines(self): return [json.loads(x) for x in _read(os.path.join(self.tmp.name, "app.jsonl")).splitlines()]


class Format(LogCase):
    def test_one_json_record_with_the_basic_fields(self):
        L.event(self.log, "info", "upload_started", file="a.mp4")
        r = self.lines()[0]
        self.assertEqual((r["level"], r["service"], r["component"], r["event"], r["file"]), ("info", "navaan-studio", "test", "upload_started", "a.mp4"))
        self.assertTrue(r["ts"].endswith("Z"))

    def test_same_record_goes_to_stdout_and_the_file(self):
        L.event(self.log, "warning", "slow", ms=1500)
        self.assertEqual(self.lines(), self.file_lines())

    def test_exception_is_logged_once_with_type_message_and_stack(self):
        try: raise ValueError("bad quote")
        except ValueError: L.exc(self.log, "step_failed", step="quote")
        recs = self.lines(); self.assertEqual(len(recs), 1)
        e = recs[0]["error"]
        self.assertEqual(e["type"], "ValueError"); self.assertEqual(e["message"], "bad quote"); self.assertIn("Traceback", e["stack"]); self.assertEqual(recs[0]["step"], "quote")

    def test_ignored_is_debug_with_the_reason(self):
        try: int("x")
        except ValueError as e: L.ignored(self.log, "optional number", e)
        r = self.lines()[0]; self.assertEqual(r["level"], "debug"); self.assertIn("optional number", r["event"]); self.assertEqual(r["error"]["type"], "ValueError")


class Context(LogCase):
    def test_ids_ride_along_and_are_restored(self):
        with L.ctx(request_id="r1", item="song-001"):
            with L.ctx(step="video"):
                L.event(self.log, "info", "inner")
            L.event(self.log, "info", "outer")
        L.event(self.log, "info", "none")
        a, b, c = self.lines()
        self.assertEqual((a["request_id"], a["item"], a["step"]), ("r1", "song-001", "video"))
        self.assertEqual((b["request_id"], "step" in b), ("r1", False))
        self.assertNotIn("request_id", c)

    def test_a_new_thread_starts_with_an_empty_context(self):
        import threading
        seen = []
        with L.ctx(request_id="main"):
            t = threading.Thread(target=lambda: seen.append(L.current("request_id"))); t.start(); t.join()
        self.assertEqual(seen, [None])

    def test_request_id_accepts_a_sane_header_only(self):
        self.assertEqual(L.new_request_id("abcd1234-ef"), "abcd1234-ef")
        self.assertNotEqual(L.new_request_id("bad id; drop"), "bad id; drop")
        self.assertRegex(L.new_request_id(None), r"^[0-9a-f]{16}$")


class Scrub(LogCase):
    SECRETS = ["owner@example.com", FAKE_GOOGLE, FAKE_OPENAI, FAKE_VAULT, FAKE_PW]

    def test_known_secret_shapes_never_reach_the_log(self):
        L.event(self.log, "info", "login by owner@example.com", detail="Authorization: Bearer " + FAKE_GOOGLE,
                url="https://x.test/cb?code=" + FAKE_OPENAI + "&state=1", msg="password=" + FAKE_PW + " token=" + FAKE_VAULT,
                headers={"Cookie": "navaan_session=abc", "X-Api-Key": "k", "ok": "fine"})
        text = self.out.getvalue() + _read(os.path.join(self.tmp.name, "app.jsonl"))
        for s in self.SECRETS: self.assertNotIn(s, text, s)
        r = self.lines()[0]
        self.assertEqual(r["headers"]["Cookie"], "[redacted]"); self.assertEqual(r["headers"]["X-Api-Key"], "[redacted]"); self.assertEqual(r["headers"]["ok"], "fine")
        self.assertIn("?[redacted]", r["url"])

    def test_secrets_inside_an_exception_message_are_masked_too(self):
        try: raise RuntimeError("refresh failed for owner@example.com with token=" + FAKE_GOOGLE)
        except RuntimeError: L.exc(self.log, "oauth_failed")
        text = self.out.getvalue()
        self.assertNotIn("owner@example.com", text); self.assertNotIn(FAKE_GOOGLE, text)

    def test_long_values_are_cut(self):
        L.event(self.log, "info", "big", blob="x" * 9000)
        self.assertLess(len(self.lines()[0]["blob"]), 4200)


class RunLog(LogCase):
    def test_a_job_gets_its_own_file_in_order(self):
        with L.ctx(job_id="song-001-run1", item="song-001"):
            for i in range(3): L.event(self.log, "info", f"line{i}")
        L.event(self.log, "info", "outside")
        p = os.path.join(self.tmp.name, "runs", "song-001-run1.jsonl")
        evs = [json.loads(x)["event"] for x in _read(p).splitlines()]
        self.assertEqual(evs, ["line0", "line1", "line2"])

    def test_job_id_cannot_escape_the_runs_folder(self):
        with L.ctx(job_id="../../etc/evil"): L.event(self.log, "info", "x")
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "..", "etc")))
        self.assertTrue(any(n.endswith(".jsonl") for n in os.listdir(os.path.join(self.tmp.name, "runs"))))

    def test_prune_removes_old_run_files_only(self):
        import time
        d = os.path.join(self.tmp.name, "runs"); os.makedirs(d, exist_ok=True)
        old, new = os.path.join(d, "old.jsonl"), os.path.join(d, "new.jsonl")
        for p in (old, new):
            with open(p, "w") as f: f.write("{}")
        os.utime(old, (time.time() - 40 * 86400,) * 2)
        L._prune(d, 30)
        self.assertFalse(os.path.exists(old)); self.assertTrue(os.path.exists(new))


class Quiet(unittest.TestCase):
    def test_cli_mode_keeps_stdout_clean(self):
        L.reset_for_tests()
        with tempfile.TemporaryDirectory() as t:
            os.environ["NAVAAN_LOG_DIR"] = t; os.environ.pop("NAVAAN_LOG_STDOUT", None)
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    L.setup(stdout=False); L.event(L.get("cli"), "info", "hello")
                self.assertEqual(buf.getvalue(), "")
                self.assertIn("hello", _read(os.path.join(t, "app.jsonl")))
            finally:
                L.reset_for_tests(); os.environ.pop("NAVAAN_LOG_DIR", None)


class Repeats(unittest.TestCase):
    def test_the_same_error_is_written_once_a_minute_and_the_next_says_how_many_were_held_back(self):
        f = L._Dedupe(window=60)
        def rec(msg="boom"):
            r = logging.LogRecord("navaan.x", logging.ERROR, "", 0, msg, (), None); return r
        self.assertTrue(f.filter(rec()))
        self.assertFalse(f.filter(rec())); self.assertFalse(f.filter(rec()))
        self.assertTrue(f.filter(rec("other")))            # a different event is never held back
        f.seen[("navaan.x", "boom", "", "", None, None, None, None, None)] = (0, 2)       # a minute has passed
        r = rec(); self.assertTrue(f.filter(r)); self.assertEqual(r.fields["suppressed"], 2)

    def test_info_and_debug_are_never_held_back(self):
        f = L._Dedupe()
        for _ in range(3): self.assertTrue(f.filter(logging.LogRecord("navaan.x", logging.INFO, "", 0, "tick", (), None)))


class Soft(LogCase):
    def test_a_missing_file_is_debug_and_any_other_failure_is_a_warning_with_the_stack(self):
        try: open("/nonexistent/x.json")
        except FileNotFoundError: L.soft(self.log, "load_error", what="x.json")
        try: raise ValueError("bad value")
        except ValueError: L.soft(self.log, "parse_error")
        a, b = self.lines()
        self.assertEqual((a["level"], a["error"]["type"]), ("debug", "FileNotFoundError"))
        self.assertEqual((b["level"], b["error"]["type"]), ("warning", "ValueError")); self.assertIn("Traceback", b["error"]["stack"])


class ScrubShapes(unittest.TestCase):
    def test_names_with_a_prefix_and_other_token_shapes_are_masked(self):
        jwt = "ey" + "Jhbgci0iJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcDEFghiJKL"
        aws = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
        gh = "gh" + "p_" + "a" * 36
        g1 = "1/" + "/0g" + "A" * 30
        pw = "hunter2" + "hunter2"; tk = "abc123" + "def456"
        el = "s" + "k_" + "abcdef1234567890abcd"
        for s in ("ELEVENLABS_API_KEY=" + el, "DB_PASS" + "WORD=" + pw, "VAULT_TO" + "KEN=" + tk, jwt, aws, gh, g1, el):
            out = L.scrub_text("line " + s + " end")
            for bad in ("hunter2hunter2", "abc123def456", jwt, aws, gh, g1, el):
                self.assertNotIn(bad, out, s)

    def test_the_whole_query_string_goes_even_after_odd_characters(self):
        out = L.scrub_text("GET /cb?code=4/0Ab_xx&state=a;b@c!d HTTP/1.1")
        self.assertNotIn("a;b", out); self.assertNotIn("0Ab_xx", out)

    def test_auth_events_are_never_held_back_and_other_items_are_kept_apart(self):
        f = L._Dedupe(window=60)
        mk = lambda m: logging.LogRecord("navaan.auth", logging.WARNING, "", 0, m, (), None)
        self.assertTrue(f.filter(mk("auth_failed"))); self.assertTrue(f.filter(mk("auth_failed")))
        with L.ctx(item="song-1", step="video"): self.assertTrue(f.filter(mk("step_failed")))
        with L.ctx(item="song-2", step="video"): self.assertTrue(f.filter(mk("step_failed")))


if __name__ == "__main__":
    unittest.main()
