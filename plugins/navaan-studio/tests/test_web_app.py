"""NAV-8: the portal serves the built app at /app/ (single page app fallback, hashed assets cached for good, nothing outside dist) and the classic view at /legacy."""
import os, sys, tempfile, threading, unittest, urllib.error, urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import navaan_ui as U


class App(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.dist = os.path.join(self.tmp.name, "dist"); os.makedirs(os.path.join(self.dist, "assets"))
        with open(os.path.join(self.dist, "index.html"), "w") as f: f.write('<html><meta name="navaan-token" content="__TOKEN__"><script src="/app/assets/app-abc.js"></script></html>')
        with open(os.path.join(self.dist, "assets", "app-abc.js"), "w") as f: f.write("console.log(1)")
        with open(os.path.join(self.tmp.name, "secret.txt"), "w") as f: f.write("top secret")
        env = mock.patch.dict(os.environ, {"NAVAAN_AUTH": "off", "NAVAAN_WEB_DIST": self.dist, "NAVAAN_ROOT": self.tmp.name}); env.start(); self.addCleanup(env.stop)
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), U.H); self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start(); self.addCleanup(self.srv.server_close); self.addCleanup(self.srv.shutdown)

    def get(self, path, follow=True):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k): return None
        op = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect)
        try:
            with op.open(urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers={"Host": f"127.0.0.1:{self.port}"}), timeout=10) as r: return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e: return e.code, dict(e.headers), e.read()

    def test_index_gets_the_session_token_and_is_never_cached(self):
        for p in ("/app/", "/app/studio/songs", "/app/albums"):   # any route that is not a file is the app's index
            code, h, body = self.get(p)
            self.assertEqual(code, 200, p); self.assertIn(U.TOKEN.encode(), body); self.assertNotIn(b"__TOKEN__", body); self.assertEqual(h["Cache-Control"], "no-store")
            self.assertTrue(h["Content-Type"].startswith("text/html"))

    def test_app_without_the_slash_redirects(self):
        code, h, _ = self.get("/app", follow=False)
        self.assertEqual((code, h["Location"]), (308, "/app/"))

    def test_hashed_assets_are_cached_for_a_year_with_the_right_type(self):
        code, h, body = self.get("/app/assets/app-abc.js")
        self.assertEqual((code, body), (200, b"console.log(1)")); self.assertIn("immutable", h["Cache-Control"]); self.assertIn("javascript", h["Content-Type"])

    def test_a_missing_file_is_a_404_not_the_index(self):
        self.assertEqual(self.get("/app/assets/nope.js")[0], 404)

    def test_nothing_outside_dist_is_reachable(self):
        for p in ("/app/../secret.txt", "/app/assets/../../secret.txt", "/app/%2e%2e/secret.txt", "/app/..%2fsecret.txt"):
            code, _, body = self.get(p)
            self.assertNotIn(b"top secret", body, p)

    def test_an_unbuilt_app_says_how_to_build_it(self):
        with mock.patch.dict(os.environ, {"NAVAAN_WEB_DIST": os.path.join(self.tmp.name, "missing")}):
            code, _, body = self.get("/app/")
        self.assertEqual(code, 503); self.assertIn(b"npm ci", body)

    def test_the_classic_view_is_at_the_root_and_at_legacy(self):
        a, b = self.get("/")[2], self.get("/legacy")[2]
        self.assertIn(b"NAVAAN", a); self.assertEqual(a.replace(U.TOKEN.encode(), b""), b.replace(U.TOKEN.encode(), b""))

    def test_signed_out_people_get_the_sign_in_page_for_every_door(self):
        with mock.patch.dict(os.environ, {"NAVAAN_AUTH": "on"}):
            for p in ("/", "/legacy", "/app/", "/app/studio/songs"):
                code, _, body = self.get(p)
                self.assertEqual(code, 200, p); self.assertNotIn(U.TOKEN.encode(), body, p); self.assertIn(b"/auth/", body, p)
            self.assertEqual(self.get("/api/songs")[0], 401)


if __name__ == "__main__":
    unittest.main()
