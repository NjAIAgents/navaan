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
        for path in ("/api/songs", "/api/settings", "/api/cloud", "/legacy", "/", "/api/analytics"): self.assertEqual(self.call(path, "lis-tok")[0], 403, path)
        code, body = self.call("/app/studio/songs", "lis-tok"); self.assertEqual(code, 200); self.assertIn(b"csrf-lis", body)   # the app itself is for every signed-in person; it only shows what the routes allow
        self.assertEqual(self.call("/app/")[0], 200); self.assertNotIn(b"csrf-lis", self.call("/app/")[1])   # signed out: only the sign-in page
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
        self.assertEqual(post("lis-tok", "csrf-lis", "/api/share", slug="song-001")[0], 404)   # a listener may share, but to them an unconfirmed song does not exist
        code, body = post("owner-tok", "csrf-owner", "/api/share", slug="song-001"); self.assertEqual((code, json.loads(body)["error"][:20]), (400, "this track\'s licence"))   # the owner is told why
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
        code, body = post("lis-tok", "csrf-lis", "/api/share", slug="song-001"); mine = json.loads(body)["token"]; self.assertEqual(code, 200)        # a listener shares a confirmed song
        self.assertEqual(self.raw("/s/" + mine)[0], 200); self.assertEqual([x["token"] for x in json.loads(self.call("/api/share", "lis-tok")[1])], [mine]); self.assertEqual(json.loads(self.call("/api/share", "owner-tok")[1])[0]["token"], mine)
        self.assertEqual(json.loads(post("owner-tok", "csrf-owner", "/api/share/revoke", token=mine)[1]), {"revoked": True})                            # the owner stops anyone's link
        mine2 = json.loads(post("lis-tok", "csrf-lis", "/api/share", slug="song-001")[1])["token"]
        other = CS.ensure_user("listener2", role="listener"); CS.create_session(auth.skey("lis2-tok"), other["id"], "csrf-lis2", "4.4.4.4", None, 3600)
        self.assertEqual(json.loads(post("lis2-tok", "csrf-lis2", "/api/share/revoke", token=mine2)[1]), {"revoked": False}); self.assertEqual(self.raw("/s/" + mine2)[0], 200)   # not theirs

    def test_playlists_plans_and_account_over_http(self):
        import catalog_store as K, entitlements as E, library_store as L, navaan_common as C
        for i in (1, 2):
            D = os.path.join(C.songs_root(), f"song-00{i}"); os.makedirs(D); open(os.path.join(D, "title.txt"), "w").write(f"Song {i}")
            json.dump({"type": "music", "state": "published"}, open(os.path.join(D, "meta.json"), "w")); K.sync_item(f"song-00{i}")
        for m in (K, E, L): self.addCleanup(lambda m=m: hasattr(getattr(m, "_tx", None), "close") and m._tx.close())
        self.addCleanup(lambda: getattr(K._LOCAL, "conn", None) and K._LOCAL.conn.close())
        post = lambda tok, csrf, path, **b: self.call(path, tok, csrf, post=True, body=b)
        lis = lambda path, **b: post("lis-tok", "csrf-lis", path, **b); own = lambda path, **b: post("owner-tok", "csrf-owner", path, **b)
        ids = []
        for i in range(3):
            code, body = lis("/api/playlists/create", name=f"List {i}"); self.assertEqual(code, 200); ids.append(json.loads(body)["id"])
        code, body = lis("/api/playlists/create", name="A fourth"); r = json.loads(body)
        self.assertEqual((code, r["limit"], r["plan"], r["upgrade"]), (403, 3, "free", "/app/plans")); self.assertIn("3", r["error"])   # a clear message with what to do
        self.assertEqual(lis("/api/billing/entitlement", plan="free", feature="playlists.max", limit=9)[0], 403)   # only the owner changes plans
        self.assertEqual(own("/api/billing/entitlement", plan="free", feature="playlists.max", enabled=True, limit=4)[0], 200)
        self.assertEqual(lis("/api/playlists/create", name="A fourth")[0], 200)                                 # SC-008: a data change, nothing redeployed
        self.assertEqual(own("/api/billing/entitlement", plan="ghost", feature="x", limit=1)[0], 404); self.assertEqual(own("/api/billing/entitlement", plan="free", feature="x", limit=-1)[0], 400)
        # another person's playlist is not found; a listener cannot reach the studio
        self.assertEqual(self.call("/api/playlists/" + ids[0], "owner-tok")[0], 404); self.assertEqual(own("/api/playlists/delete", id=ids[0])[0], 404)
        self.assertEqual(self.call("/api/playlists/" + ids[0], "lis-tok")[0], 200); self.assertEqual(lis("/api/analytics/rec", id="x")[0], 403)
        self.assertEqual(lis("/api/playlists/add", id=ids[0], slug="song-001")[0], 200); self.assertEqual(lis("/api/playlists/add", id=ids[0], slug="song-002", after="song-001")[0], 200)
        self.assertEqual(lis("/api/playlists/move", id=ids[0], slug="song-002", after="")[0], 200)
        self.assertEqual([t["slug"] for t in json.loads(self.call("/api/playlists/" + ids[0], "lis-tok")[1])["tracks"]], ["song-002", "song-001"])
        self.assertEqual(lis("/api/playlists/add", id=ids[0], slug="song-001")[0], 400); self.assertEqual(lis("/api/library/save", kind="track", slug="song-002")[0], 200)
        self.assertEqual([t["slug"] for t in json.loads(self.call("/api/library", "lis-tok")[1])["tracks"]], ["song-002"]); self.assertEqual(json.loads(self.call("/api/library", "owner-tok")[1])["tracks"], [])
        # plans page data and what this person has used
        r = json.loads(self.call("/api/plans", "lis-tok")[1]); self.assertEqual((r["mine"]["plan"]["key"], r["mine"]["usage"]["playlists"], r["mine"]["unlimited"]), ("free", 4, False)); self.assertEqual([p["key"] for p in r["plans"]], ["free", "premium"])
        self.assertTrue(json.loads(self.call("/api/plans", "owner-tok")[1])["mine"]["unlimited"])
        # playing needs the plan's audio.play; a play is recorded
        with mock.patch("objstore.par_url", lambda k, s=300: "https://bucket.example/" + k):
            json.dump({"type": "music", "state": "published", "cloud": {"verified": True, "uploaded_at": "2026-10-01T10:00:00Z", "prefix": "n/s1/", "objects": {"final.mp3": {"size": 5}}}}, open(os.path.join(C.songs_root(), "song-001", "meta.json"), "w")); K.sync_item("song-001")
            self.assertEqual(self.raw("/api/play?slug=song-001", "lis-tok")[0], 404)                          # a listener only gets confirmed songs
            self.assertEqual(self.raw("/api/play?slug=song-001", "owner-tok")[0], 200); K.set_license("song-001", "confirmed", "owner", "paid plan"); L._tx(lambda c: c.execute("DELETE FROM play_events"))
            self.assertEqual(self.raw("/api/play?slug=song-001", "lis-tok")[0], 200)
            self.assertEqual(L._conn().execute("SELECT count(*) AS n FROM play_events").fetchone()["n"], 1)
            own("/api/billing/entitlement", plan="free", feature="audio.play", enabled=False)
            st, h, b = self.raw("/api/play?slug=song-001", "lis-tok"); self.assertEqual(st, 403); self.assertIn("plan", json.loads(b)["error"])
            self.assertEqual(self.raw("/api/play?slug=song-001", "owner-tok")[0], 200)                       # the owner is never limited
        # export, then delete: the owner cannot, a listener can and then has nothing
        st, h, b = self.raw("/api/account/export", "lis-tok"); self.assertEqual(st, 200); self.assertIn("attachment", h["Content-Disposition"]); x = json.loads(b); self.assertEqual(x["account"]["username"], "listener1"); self.assertEqual(len(x["library"]["playlists"]), 4)
        self.assertEqual(own("/api/account/delete", confirm="delete my account")[0], 403)
        self.assertEqual(lis("/api/account/delete", confirm="yes")[0], 400); self.assertEqual(lis("/api/account/delete", confirm="delete my account")[0], 200)
        self.assertEqual(self.call("/api/me", "lis-tok")[0], 401)                                           # the person and their sessions are gone
        self.assertEqual(L._conn().execute("SELECT count(*) AS n FROM playlists").fetchone()["n"], 0)       # all four of theirs went
        left = L._conn().execute("SELECT user_id::text AS u FROM play_events").fetchall(); self.assertEqual(len(left), 1)   # their play went; the owner's own play is untouched
        self.assertEqual(left[0]["u"], CS.ensure_user("owner1")["id"])
        self.assertEqual(self.call("/api/me", "owner-tok")[0], 200)                                         # the owner's session is untouched

    def test_browse_filters_track_page_lyrics_shared_playlists_and_the_local_bucket(self):
        import catalog_store as K, library_store as L, entitlements as E, navaan_common as C, objstore
        bucket = os.path.join(self.tmp.name, "bucket"); os.makedirs(bucket)
        for m in (K, E, L): self.addCleanup(lambda m=m: hasattr(getattr(m, "_tx", None), "close") and m._tx.close())
        self.addCleanup(lambda: getattr(K._LOCAL, "conn", None) and K._LOCAL.conn.close())
        p = mock.patch.dict(os.environ, {"NAVAAN_OBJSTORE_DIR": bucket}); p.start(); self.addCleanup(p.stop)
        specs = [("song-001", "Tere Hone Se", "Hindi", "Hindi Romantic", "First Light"), ("song-002", "Pata Hi Na Chala", "Hindi", "Indie", None), ("song-003", "From Then to Forever", "English", "Acoustic ballad", None)]
        for slug, title, lang, genre, album in specs:
            D = os.path.join(C.songs_root(), slug); os.makedirs(D); open(os.path.join(D, "title.txt"), "w", encoding="utf-8").write(title)
            open(os.path.join(D, "lyrics.txt"), "w", encoding="utf-8").write("line one\nline two"); json.dump({"genre": genre, "language": lang}, open(os.path.join(D, "tags.json"), "w"))
            json.dump({"type": "music", "state": "published", **({"album": album} if album else {}), "cloud": {"verified": True, "uploaded_at": "2026-10-01T10:00:00Z", "prefix": f"n/{slug}/", "objects": {"final.mp3": {"size": 5}, "caption_timing.json": {"size": 40}}}}, open(os.path.join(D, "meta.json"), "w")); K.sync_item(slug)
        os.makedirs(os.path.join(bucket, "n", "song-001")); open(os.path.join(bucket, "n", "song-001", "caption_timing.json"), "w").write('[[2.5, "line one"], [7, "line two"]]'); open(os.path.join(bucket, "n", "song-001", "final.mp3"), "wb").write(bytes(range(100)))
        for sl in ("song-001", "song-003"): K.set_license(sl, "confirmed", "owner", "paid plan")   # song-002 stays unconfirmed
        slugs = lambda tok, q="": [t["slug"] for t in json.loads(self.call("/api/catalog/tracks" + q, tok)[1])]
        self.assertEqual(sorted(slugs("lis-tok")), ["song-001", "song-003"]); self.assertEqual(sorted(slugs("owner-tok")), ["song-001", "song-002", "song-003"])   # a listener never sees an unconfirmed song
        self.assertEqual(slugs("owner-tok", "?language=English"), ["song-003"]); self.assertEqual(slugs("owner-tok", "?genre=Indie"), ["song-002"]); self.assertEqual(slugs("owner-tok", "?album=first-light"), ["song-001"]); self.assertEqual(slugs("owner-tok", "?language=Hindi&genre=Indie"), ["song-002"])
        f = json.loads(self.call("/api/catalog/filters", "lis-tok")[1]); self.assertEqual((f["languages"], f["genres"], [a["slug"] for a in f["albums"]]), (["English", "Hindi"], ["Acoustic ballad", "Hindi Romantic"], ["first-light"]))
        self.assertEqual(self.call("/api/catalog/tracks")[0], 401)
        t = json.loads(self.call("/api/catalog/track/song-001", "lis-tok")[1]); self.assertEqual((t["title"], t["genre"], t["lyrics"], t["timed_lines"]), ("Tere Hone Se", "Hindi Romantic", "line one\nline two", [[2.5, "line one"], [7.0, "line two"]]))
        self.assertEqual(self.call("/api/catalog/track/song-002", "lis-tok")[0], 404); self.assertEqual(self.call("/api/catalog/track/song-002", "owner-tok")[0], 200)   # unconfirmed: owner only
        self.assertIsNone(json.loads(self.call("/api/catalog/track/song-003", "lis-tok")[1])["timed_lines"])   # no timing file: plain lyrics only
        # the local bucket stands in for the real one: play link, range, no escape from the folder
        st, h, b = self.raw("/api/play?slug=song-001", "lis-tok"); url = json.loads(b)["url"]; self.assertEqual(url, "/dev-bucket/n/song-001/final.mp3")
        st, h, b = self.raw(url, headers={"Range": "bytes=10-19"}); self.assertEqual((st, h["Content-Range"], b), (206, "bytes 10-19/100", bytes(range(10, 20))))
        self.assertEqual(self.raw(url)[0], 200); self.assertEqual(self.raw("/dev-bucket/..%2F..%2Fetc%2Fpasswd")[0], 404)
        # a playlist opens by its link only when unlisted or public, and then read only
        u = {"user_id": CS.ensure_user("listener1", role="listener")["id"], "roles": ["listener"]}; pid = L.create_playlist(u, "Evening", visibility="unlisted"); L.add_track(u["user_id"], pid, "song-001")
        priv = L.create_playlist(u, "Mine", visibility="private")
        r = json.loads(self.call("/api/playlists/" + pid, "owner-tok")[1]); self.assertEqual((r["name"], r["mine"], [t["slug"] for t in r["tracks"]]), ("Evening", False, ["song-001"]))
        self.assertEqual(json.loads(self.call("/api/playlists/" + pid, "lis-tok")[1])["mine"], True); self.assertEqual(self.call("/api/playlists/" + priv, "owner-tok")[0], 404)   # private: nothing
        self.assertEqual(self.call("/api/playlists/" + pid)[0], 401)
        self.assertEqual(self.call("/api/playlists/delete", "owner-tok", "csrf-owner", post=True, body={"id": pid})[0], 404)                       # reading is not editing

    def test_a_request_gives_its_database_connections_back(self):
        """The portal runs a thread per request; each must close its connections, or a busy moment uses up the database's limit."""
        import analytics_db as db
        c = db.connect(os.path.join(self.tmp.name, "probe"), base="studio", isolate=True); self.addCleanup(c.close)
        n = lambda: c.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname = current_database()").fetchone()["n"]
        self.call("/api/songs", "owner-tok"); before = n()
        for _ in range(40):
            for path in ("/api/songs", "/api/catalog/tracks", "/api/playlists", "/api/plans", "/api/me"): self.call(path, "owner-tok")
        c.commit(); self.assertLessEqual(n() - before, 3, "connections left open by 200 requests")

    def test_a_signed_out_visitor_reaches_nothing(self):
        self.assertEqual(self.call("/api/songs")[0], 401); self.assertEqual(self.call("/api/client-log", None, "x", post=True)[0], 401)
        self.assertEqual(self.call("/api/songs", "not-a-session")[0], 401)

    def test_a_revoked_session_stops_working_at_once(self):
        self.assertEqual(self.call("/api/songs", "owner-tok-2")[0], 200)
        CS.revoke_session(auth.skey("owner-tok-2"))
        self.assertEqual(self.call("/api/songs", "owner-tok-2")[0], 401)


if __name__ == "__main__":
    unittest.main()
