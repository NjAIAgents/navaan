"""NAV-5 stage 1 over HTTP: a signed-in owner reaches the studio with a CSRF token of their own session, a listener reaches no studio route, a signed-out visitor reaches nothing (spec 002 SC-005)."""
import json, os, sys, tempfile, threading, unittest, urllib.error, urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import auth, core_store as CS
import navaan_ui as U


class Access(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        dist = os.path.join(self.tmp.name, "dist"); os.makedirs(dist)
        with open(os.path.join(dist, "index.html"), "w") as f: f.write('<meta name="navaan-token" content="__TOKEN__">')
        for p in (mock.patch.object(auth, "DIR", self.tmp.name), mock.patch.dict(os.environ, {"NAVAAN_AUTH": "", "NAVAAN_WEB_DIST": dist, "NAVAAN_ROOT": self.tmp.name, "NAVAAN_LOG_DIR": os.path.join(self.tmp.name, "logs")})):
            p.start(); self.addCleanup(p.stop)
        CS._LOCAL.conn = None; self.addCleanup(lambda: getattr(CS._LOCAL, "conn", None) and CS._LOCAL.conn.close())
        owner = CS.ensure_user("owner1", role="owner"); lis = CS.ensure_user("listener1", role="listener")
        CS.create_session(auth.skey("owner-tok"), owner["id"], "csrf-owner", "1.1.1.1", None, 3600)
        CS.create_session(auth.skey("owner-tok-2"), owner["id"], "csrf-owner-2", "1.1.1.1", None, 3600)
        CS.create_session(auth.skey("lis-tok"), lis["id"], "csrf-lis", "2.2.2.2", None, 3600)
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), U.H); self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start(); self.addCleanup(self.srv.server_close); self.addCleanup(self.srv.shutdown)

    def call(self, path, tok=None, csrf=None, post=False, body=None):
        h = {"Host": f"127.0.0.1:{self.port}"}
        if tok: h["Cookie"] = f"{auth.COOKIE}={tok}"
        data = None
        if post: h["Content-Type"] = "application/json"; data = json.dumps(body or {}).encode()
        if csrf: h["X-Navaan-Token"] = csrf
        try:
            with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=h), timeout=10) as r: return r.status, r.read()
        except urllib.error.HTTPError as e: return e.code, e.read()

    def test_the_owner_reaches_the_studio_and_the_page_carries_that_sessions_token(self):
        self.assertEqual(self.call("/api/songs", "owner-tok")[0], 200)
        code, body = self.call("/app/", "owner-tok"); self.assertEqual(code, 200); self.assertIn(b"csrf-owner", body)
        code, body = self.call("/app/", "owner-tok-2"); self.assertIn(b"csrf-owner-2", body); self.assertNotIn(b'"csrf-owner"', body)
        code, body = self.call("/legacy", "owner-tok"); self.assertEqual(code, 200)

    def test_me_tells_who_and_what_the_session_may_do(self):
        code, body = self.call("/api/me", "owner-tok"); me = json.loads(body)
        self.assertEqual((code, me["user"], me["roles"]), (200, "owner1", ["owner"])); self.assertIn("studio.approve", me["permissions"])
        code, body = self.call("/api/me", "lis-tok"); me = json.loads(body)
        self.assertEqual((code, me["roles"]), (200, ["listener"])); self.assertNotIn("studio.access", me["permissions"])
        self.assertEqual(self.call("/api/me")[0], 401)

    def test_a_post_needs_this_sessions_own_token(self):
        self.assertEqual(self.call("/api/client-log", "owner-tok", "csrf-owner", post=True)[0], 200)
        self.assertEqual(self.call("/api/client-log", "owner-tok", "csrf-owner-2", post=True)[0], 403)   # another session's token
        self.assertEqual(self.call("/api/client-log", "owner-tok", U.TOKEN, post=True)[0], 403)         # the old process-wide token
        self.assertEqual(self.call("/api/client-log", "owner-tok", None, post=True)[0], 403)

    def test_a_listener_reaches_no_studio_route(self):
        for path in ("/api/songs", "/api/settings", "/api/cloud", "/app/", "/legacy", "/", "/api/analytics"): self.assertEqual(self.call(path, "lis-tok")[0], 403, path)
        self.assertEqual(self.call("/api/client-log", "lis-tok", "csrf-lis", post=True)[0], 403)
        self.assertEqual(self.call("/api/run", "lis-tok", "csrf-lis", post=True)[0], 403)

    def test_search_needs_library_view_and_the_album_editor_needs_the_studio(self):
        code, body = self.call("/api/search?q=tere+hone", "owner-tok"); self.assertEqual((code, json.loads(body)), (200, {"hits": []}))
        self.assertEqual(self.call("/api/search?q=tere+hone", "lis-tok")[0], 200)   # a listener has library.view
        self.assertEqual(self.call("/api/search?q=x&limit=abc", "owner-tok")[0], 400); self.assertEqual(self.call("/api/search?q=x")[0], 401)
        for path in ("/api/albums",): self.assertEqual(self.call(path, "lis-tok")[0], 403)
        self.assertEqual(self.call("/api/albums/save", "lis-tok", "csrf-lis", post=True, body={"title": "x"})[0], 403)

    def test_the_owner_creates_orders_and_deletes_an_album_over_http(self):
        post = lambda path, **b: self.call(path, "owner-tok", "csrf-owner", post=True, body=b)
        code, body = post("/api/albums/save", title="First Light", kind="ep"); self.assertEqual((code, json.loads(body)), (200, {"slug": "first-light"}))
        self.assertEqual(post("/api/albums/save", title=" ")[0], 400); self.assertEqual(post("/api/albums/save", slug="ghost", title="x")[0], 404)
        self.assertEqual(post("/api/albums/reorder", album="first-light", tracks=["nope"])[0], 400)
        code, body = self.call("/api/albums", "owner-tok"); self.assertEqual([(a["slug"], a["kind"]) for a in json.loads(body)], [("first-light", "ep")])
        self.assertEqual(json.loads(post("/api/albums/delete", slug="first-light")[1]), {"deleted": True}); self.assertEqual(json.loads(self.call("/api/albums", "owner-tok")[1]), [])

    def test_only_the_owner_sets_a_licence_and_it_is_audited(self):
        import catalog_store as K, navaan_common as C
        D = os.path.join(C.songs_root(), "song-001"); os.makedirs(D); open(os.path.join(D, "title.txt"), "w").write("One"); json.dump({"type": "music", "state": "published"}, open(os.path.join(D, "meta.json"), "w")); K.sync_item("song-001")
        self.addCleanup(lambda: getattr(K._LOCAL, "conn", None) and K._LOCAL.conn.close())
        ed = CS.ensure_user("editor1", role="editor"); CS.create_session(auth.skey("ed-tok"), ed["id"], "csrf-ed", "3.3.3.3", None, 3600)
        post = lambda tok, csrf, **b: self.call("/api/catalog/license", tok, csrf, post=True, body=b)
        self.assertEqual(post("ed-tok", "csrf-ed", slug="song-001", status="confirmed", note="x")[0], 403)   # an editor may use the studio but not decide licences
        self.assertEqual(post("lis-tok", "csrf-lis", slug="song-001", status="confirmed", note="x")[0], 403)
        self.assertEqual(post("owner-tok", "csrf-owner", slug="song-001", status="maybe", note="x")[0], 400); self.assertEqual(post("owner-tok", "csrf-owner", slug="ghost", status="confirmed", note="x")[0], 404)
        self.assertEqual(json.loads(self.call("/api/tracks", "owner-tok")[1])[0]["license_status"], "unconfirmed")
        self.assertEqual(post("owner-tok", "csrf-owner", slug="song-001", status="confirmed", note="paid plan", plan="paid")[0], 200)
        t = json.loads(self.call("/api/tracks", "owner-tok")[1])[0]; self.assertEqual((t["license_status"], t["plan"], t["decided_by"]), ("confirmed", "paid", "owner1"))
        self.assertEqual(CS._run(lambda c: c.execute("SELECT count(*) AS n FROM audit_log WHERE action = 'track_license'").fetchone())["n"], 1)

    def test_the_schedule_list_is_for_the_studio(self):
        self.assertEqual(json.loads(self.call("/api/schedule", "owner-tok")[1]), []); self.assertEqual(self.call("/api/schedule", "lis-tok")[0], 403); self.assertEqual(self.call("/api/schedule")[0], 401)

    def raw(self, path, tok=None, headers=None):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10); h = {"Host": f"127.0.0.1:{self.port}", **(headers or {})}
        if tok: h["Cookie"] = f"{auth.COOKIE}={tok}"
        c.request("GET", path, headers=h); r = c.getresponse(); b = r.read(); c.close(); return r.status, dict(r.getheaders()), b

    def test_shared_links_covers_and_play_links(self):
        import catalog_store as K, media, objstore
        from test_media import png
        D = os.path.join(__import__("navaan_common").songs_root(), "song-001"); os.makedirs(D); open(os.path.join(D, "title.txt"), "w").write("Tere <Hone> Se")
        cover = png(); pre = "navaan/songs/song-001/"
        json.dump({"type": "music", "state": "published", "cloud": {"verified": True, "uploaded_at": "2026-10-01T10:00:00Z", "prefix": pre, "objects": {"cover_1x1.png": {"size": len(cover)}, "final.mp3": {"size": 10}}}}, open(os.path.join(D, "meta.json"), "w"))
        K.sync_item("song-001"); self.addCleanup(lambda: getattr(K._LOCAL, "conn", None) and K._LOCAL.conn.close())
        for p in (mock.patch.object(objstore, "get", lambda k: cover), mock.patch.object(objstore, "par_url", lambda k, s=300: "https://bucket.example/" + k), mock.patch.object(media, "ensure_preview", lambda sl: pre + "derived/preview-30s.mp3"),
                  mock.patch.dict(os.environ, {"NAVAAN_CACHE_DIR": os.path.join(self.tmp.name, "cache")})):
            p.start(); self.addCleanup(p.stop)
        post = lambda tok, csrf, path, **b: self.call(path, tok, csrf, post=True, body=b)
        self.assertEqual(post("lis-tok", "csrf-lis", "/api/share", slug="song-001")[0], 403)                      # a listener cannot make links yet
        code, body = post("owner-tok", "csrf-owner", "/api/share", slug="song-001"); self.assertEqual((code, json.loads(body)["error"][:20]), (400, "this track\'s licence"))   # not confirmed
        K.set_license("song-001", "confirmed", "owner", "paid plan")
        code, body = post("owner-tok", "csrf-owner", "/api/share", slug="song-001", start_ms=5000); tok = json.loads(body)["token"]; self.assertEqual(code, 200); self.assertTrue(json.loads(body)["url"].endswith("/s/" + tok))
        st, h, b = self.raw("/s/" + tok)   # no cookie: anyone with the link
        self.assertEqual(st, 200); page = b.decode(); self.assertIn('property="og:title" content="Tere &lt;Hone&gt; Se"', page); self.assertIn("/s/" + tok + "/preview.mp3", page); self.assertIn("/app/?t=5", page); self.assertNotIn("<Hone>", page); self.assertIn("noindex", page)
        st, h, b = self.raw(f"/s/{tok}/preview.mp3"); self.assertEqual((st, h["Location"]), (302, "https://bucket.example/navaan/songs/song-001/derived/preview-30s.mp3"))
        self.assertEqual(self.raw("/s/nonexistent0000")[0], 404)
        st, h, b = self.raw("/img/song-001/320.webp"); self.assertEqual((st, h["Content-Type"]), (200, "image/webp")); self.assertIn("immutable", h["Cache-Control"]); self.assertTrue(b[:4] == b"RIFF")
        self.assertEqual(self.raw("/img/song-001/320.webp", headers={"If-None-Match": h["ETag"]})[0], 304)
        self.assertEqual(self.raw("/img/song-001/999.webp")[0], 404); self.assertEqual(self.raw("/img/ghost/320.webp")[0], 404)
        code, body = self.call("/api/share", "owner-tok"); self.assertEqual([x["opens"] for x in json.loads(body)], [1])   # the page was opened once; the preview does not count
        rows = json.loads(self.call("/api/songs", "owner-tok")[1]); self.assertEqual(rows[0]["art"], {"colour": "#c82828"})   # the list is told the cover exists and its colour (set by the first resize above)
        st, h, b = self.raw("/api/play?slug=song-001", "lis-tok"); self.assertEqual((st, json.loads(b)["url"]), (200, "https://bucket.example/navaan/songs/song-001/final.mp3"))
        self.assertEqual(self.raw("/api/play?slug=ghost", "lis-tok")[0], 404); self.assertEqual(self.raw("/api/play?slug=song-001")[0], 401)
        self.assertEqual(json.loads(post("owner-tok", "csrf-owner", "/api/share/revoke", token=tok)[1]), {"revoked": True})
        self.assertEqual(self.raw("/s/" + tok)[0], 404); self.assertEqual(self.raw(f"/s/{tok}/preview.mp3")[0], 404)   # revoked: both stop

    def test_a_signed_out_visitor_reaches_nothing(self):
        self.assertEqual(self.call("/api/songs")[0], 401); self.assertEqual(self.call("/api/client-log", None, "x", post=True)[0], 401)
        self.assertEqual(self.call("/api/songs", "not-a-session")[0], 401)

    def test_a_revoked_session_stops_working_at_once(self):
        self.assertEqual(self.call("/api/songs", "owner-tok-2")[0], 200)
        CS.revoke_session(auth.skey("owner-tok-2"))
        self.assertEqual(self.call("/api/songs", "owner-tok-2")[0], 401)


if __name__ == "__main__":
    unittest.main()
