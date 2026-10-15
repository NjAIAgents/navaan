"""NAV-12: the web server logs every request once, returns a request id, logs errors with a stack, and takes browser error reports."""
import io, json, os, sys, tempfile, threading, time, unittest, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import navaan_log as L
import navaan_ui as U


# Dummy secret shapes built from pieces so no real-looking token sits in the source (a scanner would flag it). They only prove the scrubber masks them.
FAKE_GOOGLE = "ya" + "29." + "A0AbCdEfGhIjKlMnOp"
FAKE_OPENAI = "s" + "k-" + "abcdefghijklmnop1234"
FAKE_VAULT = "h" + "vs." + "CAESIabcdefghijklmnop"
FAKE_PW = "hunter2" + "hunter2"

def _read(p):
    with open(p, encoding="utf-8") as f: return f.read()


class WebLog(unittest.TestCase):
    def setUp(self):
        L.reset_for_tests()
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"NAVAAN_LOG_DIR": os.path.join(self.tmp.name, "logs"), "NAVAAN_LOG_LEVEL": "DEBUG", "NAVAAN_AUTH": "off", "NAVAAN_ROOT": self.tmp.name})
        env.start(); self.addCleanup(env.stop)
        self.out = io.StringIO(); so = sys.stdout; sys.stdout = self.out; self.addCleanup(lambda: setattr(sys, "stdout", so))
        L.setup(stdout=True); self.addCleanup(L.reset_for_tests)
        U.CLIENT_LOG.clear()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), U.H); self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start(); self.addCleanup(self.srv.server_close); self.addCleanup(self.srv.shutdown)

    def call(self, path, body=None, headers=None, post=None):
        h = {"Host": f"127.0.0.1:{self.port}", **(headers or {})}
        data = None
        if body is not None or post:
            h.update({"Content-Type": "application/json", "X-Navaan-Token": U.TOKEN}); data = json.dumps(body if body is not None else {}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=10) as r: return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e: return e.code, dict(e.headers), e.read()

    def recs(self, event=None):
        time.sleep(0.2)
        rs = [json.loads(x) for x in self.out.getvalue().splitlines() if x.strip()]
        return [r for r in rs if r["event"] == event] if event else rs


class Requests(WebLog):
    def test_every_reply_carries_a_request_id_and_a_proxy_id_is_kept(self):
        _, h, _ = self.call("/privacy"); self.assertRegex(h["X-Request-Id"], r"^[0-9a-f]{16}$")
        _, h2, _ = self.call("/privacy", headers={"X-Request-Id": "from-nginx-12345"}); self.assertEqual(h2["X-Request-Id"], "from-nginx-12345")

    def test_a_routine_poll_is_debug_and_a_post_is_info_with_status_and_duration(self):
        self.call("/privacy")
        r = self.recs("http_request")[0]
        self.assertEqual((r["level"], r["status"], r["method"], r["path"]), ("debug", 200, "GET", "/privacy")); self.assertIn("ms", r); self.assertGreater(r["bytes"], 0)
        code, _, _ = self.call("/api/nope", post=True)
        self.assertIn(code, (400, 404))
        p = [x for x in self.recs("http_request") if x["method"] == "POST"][0]
        self.assertEqual((p["level"], p["status"]), ("info", code))

    def test_query_strings_never_reach_the_log(self):
        self.call("/privacy?code=SECRETCODE123&state=1")
        self.assertNotIn("SECRETCODE123", self.out.getvalue())

    def test_an_unexpected_error_is_logged_once_with_a_stack_and_the_reply_names_the_request(self):
        with mock.patch.object(U.auth, "session", side_effect=RuntimeError("boom in session")):
            code, h, body = self.call("/api/status")
        self.assertEqual(code, 500)
        rid = h["X-Request-Id"]; self.assertEqual(json.loads(body)["request_id"], rid)
        errs = [r for r in self.recs() if r["level"] == "error"]
        self.assertEqual(len(errs), 1, errs)
        e = errs[0]; self.assertEqual((e["event"], e["request_id"], e["error"]["type"]), ("request_failed", rid, "RuntimeError")); self.assertIn("boom in session", e["error"]["stack"])

    def test_a_bad_request_is_info_not_error(self):
        code, _, _ = self.call("/api/nope", post=True)
        self.assertIn(code, (400, 404))
        r = self.recs("http_error")[0]; self.assertEqual((r["level"], r["status"]), ("info", code))


class ClientLog(WebLog):
    def test_browser_errors_are_logged_with_page_user_and_request_id_and_scrubbed(self):
        code, h, _ = self.call("/api/client-log", {"kind": "error", "message": "x is undefined for owner@example.com", "stack": "at f (ui.html:1:2)", "page": "#/song/song-003",
                                                  "ui_request_id": "abc123def4567890", "src": "https://h/ui.html?token=" + FAKE_GOOGLE})
        self.assertEqual(code, 200)
        r = self.recs("client_error")[0]
        self.assertEqual((r["level"], r["page"], r["ui_request_id"], r["user"]), ("error", "#/song/song-003", "abc123def4567890", "local"))
        for s in ("owner@example.com", FAKE_GOOGLE): self.assertNotIn(s, self.out.getvalue())

    def test_reports_are_rate_limited(self):
        codes = [self.call("/api/client-log", {"kind": "error", "message": "m"})[0] for _ in range(32)]
        self.assertEqual(codes[:30], [200] * 30); self.assertEqual(codes[30:], [429, 429])

    def test_oversized_fields_are_cut(self):
        self.call("/api/client-log", {"kind": "error", "message": "m" * 5000, "stack": "s" * 9000})
        r = self.recs("client_error")[0]; self.assertLessEqual(len(r["message"]), 500 + 40); self.assertLessEqual(len(r["stack"]), 3000 + 40)

    def test_the_endpoint_needs_the_token_like_every_other_post(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/client-log", data=b"{}", headers={"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm: urllib.request.urlopen(req, timeout=10)
        self.assertEqual(cm.exception.code, 403)


class Jobs(WebLog):
    """The web server only queues work now; the logging of a run is the worker's (tests/test_worker.py)."""
    def test_a_run_is_queued_once_and_a_second_start_is_refused(self):
        import jobs
        self.assertTrue(U.start_job("song-777", step="video")); self.assertFalse(U.start_job("song-777", all_steps=True))
        v = jobs.view("song-777"); self.assertEqual((v["running"], v["queued"]), (True, True))
        self.assertEqual(self.recs("job_queued")[0]["item"], "song-777")


if __name__ == "__main__":
    unittest.main()
