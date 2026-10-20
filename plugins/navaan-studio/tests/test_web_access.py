"""NAV-5 stage 1 over HTTP: a signed-in owner reaches the studio with a CSRF token of their own session, a listener reaches no studio route, a signed-out visitor reaches nothing (spec 002 SC-005)."""
import json, os, sys, tempfile, threading, unittest, urllib.error, urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import auth, core_store as CS
import navaan_ui as U
import navaan_common as C


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

    def call(self, path, tok=None, csrf=None, post=False, body=None, host=None):
        h = {"Host": host or f"127.0.0.1:{self.port}"}
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

    def test_the_public_host_is_the_listener_app_only_and_the_studio_host_is_the_studio(self):
        with mock.patch.dict(os.environ, {"NAVAAN_PUBLIC_HOST": "navaan.njlabs.dev,studio.navaan.online,navaan.online", "NAVAAN_LISTENER_HOSTS": "navaan.online"}):
            studio, public = "studio.navaan.online", "navaan.online"
            self.assertEqual(self.call("/api/songs", "owner-tok", host=studio)[0], 200)          # the owner on the studio host: everything
            self.assertEqual(self.call("/api/songs", "owner-tok", host=public)[0], 403)          # the same session on the public host: no studio
            for path in ("/api/settings", "/api/cloud", "/api/analytics", "/legacy"): self.assertEqual(self.call(path, "owner-tok", host=public)[0], 403, path)
            code, body = self.call("/api/me", "owner-tok", host=public); me = json.loads(body)
            self.assertEqual((code, me["roles"]), (200, ["listener"])); self.assertNotIn("studio.access", me["permissions"]); self.assertIn("library.view", me["permissions"])   # the app shows the listener side
            self.assertEqual(self.call("/api/client-log", "owner-tok", "csrf-owner", post=True, host=public)[0], 403)   # and no studio write either
            self.assertIn("studio.access", json.loads(self.call("/api/me", "owner-tok", host=studio)[1])["permissions"])
            self.assertEqual(self.call("/api/me", "owner-tok", host="evil.example")[0], 403)     # a host that is not on the list is refused outright

    def test_me_gives_a_signed_in_person_their_sessions_token_so_a_stale_page_can_carry_on_and_never_gives_one_to_a_guest(self):
        env = {"NAVAAN_PUBLIC_HOST": "studio.navaan.online,navaan.online", "NAVAAN_LISTENER_HOSTS": "navaan.online", "NAVAAN_STUDIO_HOST": "studio.navaan.online"}
        with mock.patch.dict(os.environ, env):
            for tok, csrf in (("lis-tok", "csrf-lis"), ("owner-tok", "csrf-owner")):
                code, body = self.call("/api/me", tok, host="navaan.online"); self.assertEqual((code, json.loads(body)["csrf"]), (200, csrf))
            code, body = self.call("/api/me", host="navaan.online"); self.assertNotIn("csrf", json.loads(body))   # a guest has none

    def test_the_public_host_needs_no_sign_in_and_gives_a_guest_the_catalogue_and_nothing_else(self):
        env = {"NAVAAN_PUBLIC_HOST": "studio.navaan.online,navaan.online", "NAVAAN_LISTENER_HOSTS": "navaan.online", "NAVAAN_STUDIO_HOST": "studio.navaan.online"}
        with mock.patch.dict(os.environ, env):
            pub, studio = "navaan.online", "studio.navaan.online"
            code, body = self.call("/app/", host=pub); self.assertEqual(code, 200); self.assertIn(b"navaan-token", body)   # the app, not the sign in page
            self.assertNotIn(b"passkey", body.lower())
            code, body = self.call("/api/me", host=pub); me = json.loads(body); self.assertEqual((code, me.get("guest"), me["permissions"]), (200, True, [])); self.assertEqual(me["studio_url"], "https://studio.navaan.online")
            for path in ("/api/catalog/tracks", "/api/catalog/filters", "/api/catalog/albums", "/api/search?q=tere", "/api/catalog/tracks?limit=5&offset=0"): self.assertEqual(self.call(path, host=pub)[0], 200, path)
            self.assertEqual(self.call("/api/play?slug=song-999", host=pub)[0], 404)                  # asks for a song that is not there or not licensed
            for path in ("/api/songs", "/api/settings", "/api/cloud", "/api/analytics", "/api/playlists", "/api/library", "/api/account", "/api/plans", "/legacy", "/api/schedule"): self.assertEqual(self.call(path, host=pub)[0], 403, path)
            self.assertEqual(self.call("/api/client-log", None, None, post=True, host=pub)[0], 401)  # no write without a session
            self.assertEqual(self.call("/", host=pub)[0], 200)                                         # the front door goes to the app, not to a login page
            self.assertIn(b"passkey", self.call("/app/", host=studio)[1].lower())                      # the studio host still asks the visitor to sign in
            self.assertEqual(self.call("/api/songs", host=studio)[0], 401)
            code, body = self.call("/api/me", "owner-tok", host=pub); me = json.loads(body)
            self.assertEqual((code, me["roles"], me["studio_url"]), (200, ["listener"], "https://studio.navaan.online")); self.assertNotIn("guest", me)   # the owner on the public site: the listener app, with the way to the studio
            code, body = self.call("/api/me", "owner-tok", host=studio); me = json.loads(body); self.assertEqual(me.get("public_url"), "https://navaan.online"); self.assertIn("studio.access", me["permissions"])   # on the studio host: the studio, with a way to the public site

    def test_visitors_can_send_reactions_and_messages_from_the_public_site_only_and_only_the_studio_reads_them(self):
        env = {"NAVAAN_PUBLIC_HOST": "studio.navaan.online,navaan.online", "NAVAAN_LISTENER_HOSTS": "navaan.online"}
        with mock.patch.dict(os.environ, env):
            pub, studio = "navaan.online", "studio.navaan.online"; post = lambda path, body, host=pub, tok=None: self.call(path, tok, None, post=True, body=body, host=host)
            self.assertEqual(post("/api/site/react", {"slug": "song-999", "reaction": "up"})[0], 404)       # no such song
            self.assertEqual(post("/api/site/react", {"slug": "song-999", "reaction": "meh"})[0], 400)
            self.assertEqual(post("/api/site/feedback", {"message": ""})[0], 400); self.assertEqual(post("/api/site/feedback", {"message": "hi", "email": "nope"})[0], 400)
            self.assertEqual(post("/api/site/feedback", {"message": "Nice site"})[0], 200); self.assertEqual(post("/api/site/feedback", {"message": "bot", "website": "http://spam"})[0], 200)   # the bot is thanked and ignored
            self.assertEqual(post("/api/site/react", {"slug": "x", "reaction": "up"}, host=studio)[0], 401)  # not a studio thing
            self.assertEqual(self.call("/api/site/feedback", host=pub)[0], 403); self.assertEqual(self.call("/api/site/reactions", host=pub)[0], 403)   # a visitor reads nothing
            code, body = self.call("/api/site/feedback", "owner-tok", host=studio); rows = json.loads(body); self.assertEqual(code, 200); self.assertEqual([r["message"] for r in rows], ["Nice site"])   # the bot's message was not kept
            self.assertEqual(self.call("/api/site/reactions", "owner-tok", host=studio)[0], 200)
            self.assertEqual(post("/api/site/feedback/handle", {"id": "not-a-uuid"}, host=studio, tok="owner-tok")[0], 403)   # needs the session's own token
            for i in range(6): last = post("/api/site/feedback", {"message": f"spam {i}"})[0]
            self.assertEqual(last, 429)   # five messages an hour from one address

    def test_visits_are_counted_from_the_public_site_and_only_the_studio_reads_them(self):
        env = {"NAVAAN_PUBLIC_HOST": "studio.navaan.online,navaan.online", "NAVAAN_LISTENER_HOSTS": "navaan.online"}
        with mock.patch.dict(os.environ, env):
            pub, studio = "navaan.online", "studio.navaan.online"; post = lambda body, host=pub: self.call("/api/site/hit", None, None, post=True, body=body, host=host)
            self.assertEqual(post({"kind": "view", "slug": "song-001", "src": "yt"})[0], 200); self.assertEqual(post({"kind": "play", "slug": "song-001", "seconds": 30})[0], 200)
            self.assertEqual(post({"kind": "nope"})[0], 400); self.assertEqual(post({"kind": "view", "slug": "song-001"}, host=studio)[0], 200)   # answered on the studio host too, never counted there
            self.assertEqual(self.call("/api/site/visits", host=pub)[0], 403)   # a visitor reads nothing
            code, body = self.call("/api/site/visits?days=7", "owner-tok", host=studio); v = json.loads(body); self.assertEqual(code, 200)
            self.assertEqual((v["totals"]["today"]["views"], v["totals"]["today"]["plays"], v["totals"]["today"]["seconds"]), (1, 1, 30)); self.assertEqual(v["sources"][0]["name"], "youtube")

    def test_only_the_studio_reads_the_sentiment_and_starts_scoring(self):
        import sentiment
        with mock.patch.object(sentiment, "summary", return_value={"totals": {"total": 0}}), mock.patch.object(sentiment, "run_async", return_value=True) as go:
            self.assertEqual(self.call("/api/analytics/sentiment?days=7", "owner-tok")[0], 200); self.assertEqual(self.call("/api/analytics/sentiment", "lis-tok")[0], 403)
            self.assertEqual(self.call("/api/analytics/sentiment/run", "lis-tok", "csrf-lis", post=True)[0], 403); go.assert_not_called()
            self.assertEqual(self.call("/api/analytics/sentiment/run", "owner-tok", "csrf-owner", post=True)[0], 200); go.assert_called_once()

    def test_the_owner_sets_a_shorts_music_level_and_the_typography_runs_again(self):
        D = os.path.join(__import__("navaan_common").songs_root(), "aha-009"); os.makedirs(D); json.dump({"type": "aha", "state": "drafted"}, open(os.path.join(D, "meta.json"), "w")); open(os.path.join(D, "timing.json"), "w").write("{}")
        call = lambda body, tok="owner-tok", csrf="csrf-owner": self.call("/api/music/level", tok, csrf, post=True, body={"slug": "aha-009", **body})
        self.assertEqual(call({"level": 90})[0], 400); self.assertEqual(call({"level": "loud"})[0], 400); self.assertEqual(call({"level": 30}, "lis-tok", "csrf-lis")[0], 403)
        code, body = call({"level": 30}); self.assertEqual(code, 200); self.assertEqual(json.loads(body)["level"], 30)
        self.assertIn("music_level: 30", open(os.path.join(D, "brief.md")).read()); self.assertFalse(os.path.exists(os.path.join(D, "timing.json")))   # the next typography takes it

    def test_an_aha_script_can_be_edited_replaced_or_sent_back_at_its_approval(self):
        import navaan_common as C
        D = os.path.join(C.songs_root(), "aha-010"); os.makedirs(D)
        def fresh():
            json.dump({"type": "aha", "state": "draft", "approvals": {"quote": {"at": "x"}}}, open(os.path.join(D, "meta.json"), "w")); open(os.path.join(D, "title.txt"), "w").write("T")
            json.dump({"text": "One. Two.", "lines": ["One.", "Two."], "captions": ["One", "Two"], "pictures": ["p" * 30, "q" * 30]}, open(os.path.join(D, "quote.json"), "w")); open(os.path.join(D, "visual_plan.json"), "w").write("{}")
        fresh(); post = lambda path, body, tok="owner-tok", csrf="csrf-owner": self.call(path, tok, csrf, post=True, body={"slug": "aha-010", **body})
        with mock.patch.object(U, "start_job", return_value=True) as go:
            self.assertEqual(post("/api/aha/edit-script", {"lines": ["Uno.", "Dos."], "captions": ["Uno", "Dos"]}, "lis-tok", "csrf-lis")[0], 403)
            self.assertEqual(post("/api/aha/edit-script", {"lines": ["only one"], "captions": ["x"]})[0], 400)
            code, body = post("/api/aha/edit-script", {"lines": ["Uno.", "Dos."], "captions": ["Uno", "Dos"]}); self.assertEqual((code, json.loads(body)["started"]), (200, False)); go.assert_not_called()
            self.assertEqual(json.load(open(os.path.join(D, "quote.json")))["lines"], ["Uno.", "Dos."])
            fresh(); code, body = post("/api/aha/replace-script", {"text": "My own first sentence. My own second sentence."}); self.assertEqual((code, json.loads(body)["started"]), (200, True))
            go.assert_called_once_with("aha-010", False, "quote", redo=True)
            self.assertFalse(os.path.exists(os.path.join(D, "quote.json"))); self.assertFalse(os.path.exists(os.path.join(D, "visual_plan.json"))); self.assertTrue(open(os.path.join(D, "quote_feedback.txt")).read().startswith("REPLACE:"))
            self.assertNotIn("quote", json.load(open(os.path.join(D, "meta.json")))["approvals"])
            fresh(); go.reset_mock(); code, body = post("/api/request-changes", {"gate": "quote", "note": "Make the hook sharper"}); self.assertEqual((code, json.loads(body)["started"]), (200, True))
            self.assertEqual(open(os.path.join(D, "quote_feedback.txt")).read().strip(), "Make the hook sharper"); self.assertFalse(os.path.exists(os.path.join(D, "quote.json"))); go.assert_called_once()
            json.dump({"type": "music", "state": "draft"}, open(os.path.join(D, "meta.json"), "w")); self.assertEqual(post("/api/aha/replace-script", {"text": "x" * 40})[0], 400)   # only for an Aha-lorithm short

    def test_the_owner_sets_a_songs_mood_and_nobody_else_can(self):
        D = os.path.join(__import__("navaan_common").songs_root(), "song-001"); os.makedirs(D); open(os.path.join(D, "title.txt"), "w").write("One"); json.dump({"type": "music", "state": "drafted"}, open(os.path.join(D, "meta.json"), "w"))
        post = lambda tok, csrf, **b: self.call("/api/mood", tok, csrf, post=True, body=b)
        self.assertEqual(post("owner-tok", "csrf-owner", slug="song-001", mood="disco")[0], 400)
        self.assertEqual(post("owner-tok", "csrf-owner", slug="song-001", mood="Dusk")[0], 200); self.assertEqual(json.load(open(os.path.join(D, "meta.json")))["mood"], "dusk")
        self.assertEqual(post("lis-tok", "csrf-lis", slug="song-001", mood="dawn")[0], 403)   # a listener has no say
        self.assertEqual(post("owner-tok", "csrf-owner", slug="song-001", mood="")[0], 200); self.assertNotIn("mood", json.load(open(os.path.join(D, "meta.json"))))   # empty clears it

    def test_a_visitor_makes_a_clip_of_a_song_and_anyone_with_the_link_can_play_it_with_range_support(self):
        import catalog_store as K, clip_share
        D = os.path.join(__import__("navaan_common").songs_root(), "song-001"); os.makedirs(D); open(os.path.join(D, "title.txt"), "w").write("Tere <Hone> Se")
        json.dump({"type": "music", "state": "published", "cloud": {"verified": True, "uploaded_at": "2026-10-01T10:00:00Z", "prefix": "navaan/songs/song-001/", "objects": {"final.mp3": {"size": 10}}}}, open(os.path.join(D, "meta.json"), "w"))
        K.sync_item("song-001"); self.addCleanup(lambda: getattr(K._LOCAL, "conn", None) and K._LOCAL.conn.close()); K.set_license("song-001", "confirmed", "owner", "paid plan")
        mp4 = os.path.join(self.tmp.name, "clip.mp4"); open(mp4, "wb").write(bytes(range(256)) * 4)   # 1024 bytes stand in for the video
        made = []
        def fake_make(slug, start, length): clip_share.check(slug, start, length); made.append((slug, start, length)); return mp4
        env = {"NAVAAN_PUBLIC_HOST": "studio.navaan.online,navaan.online", "NAVAAN_LISTENER_HOSTS": "navaan.online"}
        with mock.patch.dict(os.environ, env), mock.patch.object(clip_share, "make", fake_make):
            post = lambda body, host="navaan.online": self.call("/api/clip", None, None, post=True, body=body, host=host)
            code, body = post({"slug": "song-001", "start": 5, "length": 15}); d = json.loads(body)
            self.assertEqual((code, d["token"], d["url"]), (200, "song-001-5-15", "/c/song-001-5-15.mp4")); self.assertTrue(d["page"].endswith("/c/song-001-5-15"))
            self.assertEqual(post({"slug": "song-001", "start": 5, "length": 4})[0], 400)   # 5 to 90 seconds
            self.assertEqual(post({"slug": "song-001", "start": 5, "length": 91})[0], 400)
            self.assertEqual(post({"slug": "song-001", "start": "x"})[0], 400); self.assertEqual(post({"slug": "ghost", "start": 0, "length": 15})[0], 404)
            st, h, b = self.raw("/c/song-001-5-15"); page = b.decode()
            self.assertEqual(st, 200); self.assertIn('property="og:video"', page); self.assertIn("/app/song/song-001", page); self.assertIn("Hear the full song", page); self.assertNotIn("<Hone>", page)
            st, h, b = self.raw("/c/song-001-5-15.mp4"); self.assertEqual((st, h["Content-Type"], h["Accept-Ranges"], len(b)), (200, "video/mp4", "bytes", 1024))
            st, h, b = self.raw("/c/song-001-5-15.mp4", headers={"Range": "bytes=0-99"}); self.assertEqual((st, h["Content-Range"], len(b)), (206, "bytes 0-99/1024", 100))   # Safari asks for ranges
            st, h, b = self.raw("/c/song-001-5-15.mp4", headers={"Range": "bytes=-24"}); self.assertEqual((st, h["Content-Range"]), (206, "bytes 1000-1023/1024"))
            self.assertEqual(self.raw("/c/song-001-5-4")[0], 404); self.assertEqual(self.raw("/c/song-001-5-91")[0], 404); self.assertEqual(self.raw("/c/ghost-5-15")[0], 404)
            for i in range(21): last = post({"slug": "song-001", "start": 5, "length": 15})[0]
            self.assertEqual(last, 429)   # twenty clips an hour from one address

    def test_a_new_inspiration_is_narrated_unless_skipped_and_only_a_known_voice_counts(self):
        import narration, navaan_common as C
        post = lambda **b: self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=b)
        code, body = post(type="inspiration", idea="You are allowed to outgrow your old life.", narrate="eleven", voice="nj"); self.assertEqual(code, 200); D = C.song_dir(json.loads(body)["slug"])
        self.assertEqual((narration.get_option(D, "narrate"), narration.get_option(D, "voice")), ("eleven", "nj"))
        code, body = post(type="inspiration", idea="Another quote that stays quiet.", narrate="none"); D2 = C.song_dir(json.loads(body)["slug"]); self.assertEqual(narration.get_option(D2, "narrate"), "none")   # skipped when asked
        code, body = post(type="inspiration", idea="A third quote.", narrate="eleven", voice="bogus"); D3 = C.song_dir(json.loads(body)["slug"]); self.assertEqual(narration.get_option(D3, "voice"), "suno1")   # an unknown voice falls back to the default

    def test_changing_the_voice_or_pace_drops_a_voice_made_the_old_way_until_the_video_is_approved(self):
        import narration, navaan, navaan_common as C
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="inspiration", idea="Stay soft, stay kind.", narrate="eleven", voice="suno1")); D = C.song_dir(json.loads(body)["slug"]); slug = json.loads(body)["slug"]
        mk = lambda: [open(os.path.join(D, f), "w").write("x") for f in ("voiceover.mp3", "voiceover.srt", "narration_sync.json")]
        has = lambda: [os.path.exists(os.path.join(D, f)) for f in ("voiceover.mp3", "voiceover.srt", "narration_sync.json")]
        post = lambda **b: self.call("/api/narration/eleven", "owner-tok", "csrf-owner", post=True, body=dict(slug=slug, **b))
        mk(); self.assertEqual(post(on=True, voice="suno1", pace="slow")[0], 200); self.assertEqual(has(), [True] * 3)    # suno1 and slow are the defaults: nothing changed, the take stays
        mk(); self.assertEqual(post(on=True, voice="suno1", pace="normal")[0], 200); self.assertEqual(has(), [False] * 3)   # a new pace: made again
        self.assertEqual(narration.get_option(D, "pace"), "normal")
        self.assertEqual(post(on=True, voice="suno1", pace="fast")[0], 400)
        navaan.edit_meta(slug, lambda m: m.setdefault("approvals", {}).update(media={"at": "x"}))
        mk(); self.assertEqual(post(on=True, voice="nj", pace="calm")[0], 200); self.assertEqual(has(), [True] * 3)   # the approved video is not undone by a settings change

    def test_saving_an_edited_narration_script_drops_the_old_voice_and_empty_goes_back(self):
        import narrate_eleven, navaan, navaan_common as C
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="inspiration", idea="Stay soft, stay kind.", narrate="eleven")); slug = json.loads(body)["slug"]; D = C.song_dir(slug)
        mk = lambda: [open(os.path.join(D, f), "w").write("x") for f in ("voiceover.mp3", "narration_sync.json")]
        has = lambda: [os.path.exists(os.path.join(D, f)) for f in ("voiceover.mp3", "narration_sync.json")]
        post = lambda **b: self.call("/api/narration/script", "owner-tok", "csrf-owner", post=True, body=dict(slug=slug, **b))
        mk(); code, body = post(text="[softly] Stay... kind."); self.assertEqual(code, 200); self.assertEqual(has(), [False, False]); self.assertEqual(json.loads(body)["script"], "[softly] Stay... kind.")
        self.assertEqual(open(os.path.join(D, narrate_eleven.SCRIPT)).read().strip(), "[softly] Stay... kind.")
        self.assertEqual(post(text="x" * 5000)[0], 400)
        code, body = post(text=""); self.assertEqual(code, 200); self.assertFalse(json.loads(body)["script_custom"]); self.assertFalse(os.path.exists(os.path.join(D, narrate_eleven.SCRIPT)))
        navaan.edit_meta(slug, lambda m: m.setdefault("approvals", {}).update(media={"at": "x"}))
        mk(); self.assertEqual(post(text="Changed after approval.")[0], 200); self.assertEqual(has(), [True, True])   # an approved video is not undone by an edit
        self.assertEqual(self.call("/api/narration/script", "lis-tok", "csrf-lis", post=True, body=dict(slug=slug, text="x"))[0], 403)   # a listener has no say

    def test_background_music_for_an_inspiration_is_added_and_removed_and_a_voice_does_not_switch_it_off(self):
        import base64, shutil as _sh, subprocess as _sp, tempfile as _tf, narration, navaan, navaan_common as C
        if not (_sh.which("ffmpeg") and _sh.which("ffprobe")): self.skipTest("ffmpeg is needed")
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="inspiration", idea="Stay soft, stay kind.", narrate="none")); slug = json.loads(body)["slug"]; D = C.song_dir(slug)
        wav = os.path.join(_tf.mkdtemp(), "a.mp3"); _sp.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=330:duration=3", "-c:a", "libmp3lame", wav], check=True)
        b64 = base64.b64encode(open(wav, "rb").read()).decode()
        up = lambda **b: self.call("/api/music/upload", "owner-tok", "csrf-owner", post=True, body=dict(slug=slug, **b))
        open(os.path.join(D, "timing.json"), "w").write("old")
        code, body = up(name="Calm Piano.mp3", audio=b64); self.assertEqual(code, 200); self.assertEqual(json.loads(body)["music"]["name"], "Calm Piano.mp3")
        self.assertEqual(narration.get_option(D, "music"), "auto"); self.assertFalse(os.path.exists(os.path.join(D, "timing.json")))   # made from the old music: made again
        self.assertEqual(up(name="x.exe", audio=b64)[0], 400); self.assertEqual(up(name="x.mp3", audio=base64.b64encode(b"not audio").decode())[0], 400)
        self.assertIn("music added via ui: Calm Piano.mp3", "\n".join(str(h) for h in navaan.meta(slug)["history"]))
        code, body = self.call("/api/music/remove", "owner-tok", "csrf-owner", post=True, body=dict(slug=slug)); self.assertEqual(code, 200); self.assertEqual(narration.get_option(D, "music"), "none")
        navaan.edit_meta(slug, lambda m: m.setdefault("approvals", {}).update(media={"at": "x"})); open(os.path.join(D, "timing.json"), "w").write("old")
        code, body = up(name="Calm Piano.mp3", audio=b64); self.assertEqual(code, 200); self.assertEqual(json.loads(body)["redo"], "Plan the typography"); self.assertTrue(os.path.exists(os.path.join(D, "timing.json")))   # an approved video keeps its sound and is told what to redo
        self.assertEqual(self.call("/api/music/upload", "lis-tok", "csrf-lis", post=True, body=dict(slug=slug, name="a.mp3", audio=b64))[0], 403)   # a listener has no say

    def test_importing_a_song_needs_the_suno_link_takes_the_sound_from_your_file_or_the_page_and_reads_the_link_first(self):
        import base64, suno_import
        audio = {"name": "The Streets.mp3", "data": base64.b64encode(b"\0" * 60000).decode()}
        imp = lambda **b: self.call("/api/import", "owner-tok", "csrf-owner", post=True, body=b)
        code, body = imp(audio=audio); self.assertEqual(code, 400); self.assertIn("Add the Suno link", json.loads(body)["error"])   # the file alone is no longer enough
        info0 = {"title": "The Streets We Carry", "lyrics": "[Verse]\nline one\nline two", "style": "soft pop", "video_url": ""}
        with mock.patch.object(suno_import, "read_page", return_value=info0):   # the link alone, and the page lists no video: asked for the file instead, nothing created
            code, body = imp(url="https://suno.com/s/1K4BKj0pldFbnlkF"); self.assertEqual(code, 400); self.assertIn("Add the song's audio file instead", json.loads(body)["error"])
        with mock.patch.object(suno_import, "read_page", return_value={**info0, "video_url": "https://cdn1.suno.ai/x.mp4"}), mock.patch.object(suno_import, "fetch_voice", side_effect=ValueError("The downloaded Suno file is damaged, so I did not use it.")):
            code, body = imp(url="https://suno.com/s/1K4BKj0pldFbnlkF"); self.assertEqual(code, 400); self.assertIn("damaged", json.loads(body)["error"])   # a bad download is refused before anything is made
        with mock.patch.object(suno_import, "read_page", side_effect=ValueError("I could not find lyrics on that Suno page. Check that the song is public.")):
            code, body = imp(url="https://suno.com/song/25dbc87e-adf4-46a6-a532-080437def045", audio=audio); self.assertEqual(code, 400); self.assertIn("could not find lyrics", json.loads(body)["error"])
        self.assertEqual(self.call("/api/songs", "owner-tok", "csrf-owner")[0], 200)   # nothing was created by the refused imports
        info = {"title": "The Streets We Carry", "lyrics": "[Verse 1]\nThere was a quiet in those little streets,", "style": "soft pop, cinematic"}
        with mock.patch.object(suno_import, "read_page", return_value=info), mock.patch.object(suno_import, "fetch", lambda slug, dest=None: False), mock.patch.object(U, "start_job", lambda sl, all_=True: True):   # no job: a worker left by another test would run the import under us
            code, body = imp(url="https://suno.com/song/25dbc87e-adf4-46a6-a532-080437def045", audio=audio)
        self.assertEqual(code, 200); import navaan_common as C; D = C.song_dir(json.loads(body)["slug"])
        self.assertEqual(open(os.path.join(D, "lyrics.txt")).read().strip(), info["lyrics"]); self.assertEqual(open(os.path.join(D, "style.txt")).read().strip(), "soft pop, cinematic"); self.assertTrue(os.path.isfile(os.path.join(D, "takes", "upload.mp3")))   # the words from the link, the sound from the file

    def test_a_song_import_with_only_the_link_takes_the_sound_from_the_suno_page_video(self):
        import shutil as _sh, subprocess as _sp, tempfile as _tf, suno_import, navaan_common as C
        if not (_sh.which("ffmpeg") and _sh.which("ffprobe")): self.skipTest("ffmpeg is needed")
        t = _tf.mkdtemp(); self.addCleanup(_sh.rmtree, t, True); m4a = os.path.join(t, "v.m4a")
        _sp.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=30", "-c:a", "aac", "-b:a", "192k", m4a], check=True)
        info = {"title": "The Streets We Carry", "lyrics": "[Verse 1]\nThere was a quiet in those little streets,", "style": "soft pop", "video_url": "https://cdn1.suno.ai/x.mp4"}
        seen = {}
        def fake_fetch(url, tmp, max_seconds=0, max_bytes=0): seen.update(url=url, secs=max_seconds, mb=max_bytes >> 20); return m4a
        imp = lambda **b: self.call("/api/import", "owner-tok", "csrf-owner", post=True, body=b)
        with mock.patch.object(suno_import, "read_page", return_value=info), mock.patch.object(suno_import, "fetch_voice", fake_fetch), mock.patch.object(suno_import, "fetch", lambda slug, dest=None: False), mock.patch.object(U, "start_job", lambda sl, all_=True: True):
            code, body = imp(url="https://suno.com/s/abc12345")
        self.assertEqual(code, 200); D = C.song_dir(json.loads(body)["slug"])
        self.assertEqual((seen["url"], seen["secs"], seen["mb"]), ("https://cdn1.suno.ai/x.mp4", 600.0, 80))   # a whole song is allowed up to ten minutes
        self.assertTrue(os.path.isfile(os.path.join(D, "takes", "upload.m4a"))); self.assertEqual(open(os.path.join(D, "lyrics.txt")).read().strip(), info["lyrics"])   # the sound from the page, the words from the link
        self.assertEqual(open(os.path.join(D, "title.txt")).read().strip(), "The Streets We Carry")

    def test_the_picture_plan_is_edited_on_the_step_page_and_a_bad_edit_changes_nothing(self):
        import navaan, navaan_common as C
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="music", idea="rain")); slug = json.loads(body)["slug"]; D = C.song_dir(slug)
        pack = {"concept": "A quiet ache.", "character": "A woman.", "style_line": "Rain.", "look": {"style_line": "Rain."}, "prompts": [{"n": 1, "section": "Verse", "prompt": "First.", "camera": "pan"}]}
        json.dump(pack, open(os.path.join(D, "prompt_pack.json"), "w"))
        save = lambda tok="owner-tok", csrf="csrf-owner", **b: self.call("/api/plan/save", tok, csrf, post=True, body=dict(slug=slug, **b))
        self.assertEqual(save(character="A lone man.", prompts=[{"n": 1, "prompt": "Second."}])[0], 200)
        got = json.load(open(os.path.join(D, "prompt_pack.json"))); self.assertEqual((got["character"], got["prompts"][0]["prompt"], got["prompts"][0]["camera"]), ("A lone man.", "Second.", "pan"))
        self.assertIn("picture plan edited via ui:owner1", "\n".join(str(h) for h in navaan.meta(slug)["history"]))
        code, body = save(prompts=[{"n": 9, "prompt": "x"}]); self.assertEqual(code, 400); self.assertIn("no picture 9", json.loads(body)["error"])
        self.assertEqual(json.load(open(os.path.join(D, "prompt_pack.json")))["character"], "A lone man.")
        self.assertEqual(save("lis-tok", "csrf-lis", character="x")[0], 403)   # a listener has no say

    def test_write_the_prompt_for_pictures_reaches_the_prompt_pack_and_does_not_fail_with_an_internal_error(self):
        # a local `import prompt_pack` in another branch of the same handler once made the name unbound here: the button answered 500
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="music", idea="rain")); slug = json.loads(body)["slug"]
        with mock.patch.object(U.prompt_pack, "make", lambda sl, count=None: {"slug": sl, "count": count}):
            code, body = self.call("/api/visuals/prompts", "owner-tok", "csrf-owner", post=True, body=dict(slug=slug, count=4))
        self.assertEqual((code, json.loads(body)), (200, {"ok": True, "pack": {"slug": slug, "count": 4}}))
        with mock.patch.object(U.prompt_pack, "make", mock.Mock(side_effect=RuntimeError("no key"))):
            code, body = self.call("/api/visuals/prompts", "owner-tok", "csrf-owner", post=True, body=dict(slug=slug))
        self.assertEqual((code, json.loads(body)["error"]), (400, "no key"))

    def test_the_youtube_text_and_the_instagram_caption_are_edited_in_the_studio_within_what_each_platform_accepts(self):
        import navaan_common as C
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="music", idea="rain")); slug = json.loads(body)["slug"]; D = C.song_dir(slug)
        save = lambda name, content, tok="owner-tok", csrf="csrf-owner": self.call("/api/save", tok, csrf, post=True, body=dict(slug=slug, file=name, content=content))
        good = json.dumps({"title": "Porch Light", "description": "d", "tags": ["folk", "country"]})
        self.assertEqual(save("youtube.json", good)[0], 200); self.assertEqual(json.load(open(os.path.join(D, "youtube.json")))["title"], "Porch Light")
        for bad, why in ((json.dumps({"title": " ", "description": "d"}), "cannot be empty"), (json.dumps({"title": "x" * 101, "description": "d"}), "100 characters"),
                         (json.dumps({"title": "t", "description": "\u0915" * 1700}), "5,000 bytes"), (json.dumps({"title": "t", "description": "d", "tags": ["x" * 300, "y" * 300]}), "500 characters"),
                         (json.dumps({"title": "t", "description": "d", "tags": "folk"}), "list of words"), (json.dumps([1]), "not valid")):
            code, body = save("youtube.json", bad); self.assertEqual(code, 400, why); self.assertIn(why, json.loads(body)["error"])
        self.assertEqual(json.load(open(os.path.join(D, "youtube.json")))["title"], "Porch Light")   # a refused edit changes nothing
        self.assertEqual(save("instagram.txt", "a" * 2200)[0], 200)
        code, body = save("instagram.txt", "a" * 2201); self.assertEqual(code, 400); self.assertIn("2,200 characters", json.loads(body)["error"])
        import navaan; navaan.edit_meta(slug, lambda m: m.setdefault("published", {}).update(youtube_items=[{"file": "final_16x9.mp4", "id": "abc"}]))
        code, body = save("youtube.json", good); self.assertEqual(code, 400); self.assertIn("already on YouTube", json.loads(body)["error"])   # once it is up, YouTube Studio is the place
        self.assertEqual(save("youtube.json", good, "lis-tok", "csrf-lis")[0], 403)   # a listener has no say

    def test_a_publishing_time_given_at_creation_in_central_time_schedules_both_platforms_and_a_bad_one_creates_nothing(self):
        import navaan, publish_schedule as P
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="music", idea="rain", publish_at_ct="2030-12-01T18:30"))
        self.assertEqual((code, json.loads(body)["publish_at"]), (200, "2030-12-02T00:30:00Z")); slug = json.loads(body)["slug"]
        sc = navaan.meta(slug)["schedule"]; self.assertEqual((sc["youtube_at"], sc["instagram_at"]), ("2030-12-02T00:30:00Z", "2030-12-02T00:30:00Z"))
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="inspiration", idea="hope"))
        self.assertIsNone(json.loads(body)["publish_at"]); self.assertNotIn("schedule", navaan.meta(json.loads(body)["slug"]))   # no time: it publishes when the pipeline finishes
        before = len(os.listdir(os.path.dirname(C.song_dir(slug))))
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="music", idea="x", publish_at_ct="2001-01-01T10:00"))
        self.assertEqual(code, 400); self.assertIn("future", json.loads(body)["error"]); self.assertEqual(len(os.listdir(os.path.dirname(C.song_dir(slug)))), before)   # nothing created

    def test_choosing_the_visuals_can_approve_the_spend_in_the_same_click(self):
        import navaan
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="music", idea="rain")); slug = json.loads(body)["slug"]
        with mock.patch.dict(os.environ, {"NAVAAN_ROOT": self.tmp.name}):
            code, body = self.call("/api/visuals/save", "owner-tok", "csrf-owner", post=True, body=dict(slug=slug, mode="flow", approve_spend=True))
        self.assertEqual((code, json.loads(body)["spend_approved"]), (200, True)); self.assertIn("(with the visuals)", navaan.meta(slug)["approvals"]["credits"]["via"])
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="music", idea="sun")); other = json.loads(body)["slug"]
        self.call("/api/visuals/save", "owner-tok", "csrf-owner", post=True, body=dict(slug=other, mode="flow")); self.assertNotIn("credits", navaan.meta(other).get("approvals", {}))   # not asked: not approved

    def test_feedback_at_the_video_review_names_one_video_and_only_that_one_is_made_again(self):
        import navaan, navaan_common as C, reel_lyrics
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="music", idea="rain")); slug = json.loads(body)["slug"]; D = C.song_dir(slug)
        navaan.edit_meta(slug, lambda m: m.setdefault("approvals", {}).update(media={"at": "x", "via": "ui:owner1"}))
        sent = []; req = lambda **b: self.call("/api/request-changes", "owner-tok", "csrf-owner", post=True, body=dict(slug=slug, gate="media", **b))
        with mock.patch.object(U, "start_job", lambda sl, all_=False, step=None, redo=False: sent.append((sl, all_, step, redo)) or True), mock.patch.object(U.jobs, "active", lambda sl: False):
            code, body = req(note="lyrics late", video="trailer"); self.assertEqual(code, 400); self.assertIn("say which video", json.loads(body)["error"])
            code, body = req(note="lyrics late", video="reel_lyrics", offset=99); self.assertEqual(code, 400)   # a bad nudge is refused before anything changes
            self.assertEqual(sent, []); self.assertIn("media", navaan.meta(slug)["approvals"])
            code, body = req(note="lyrics are late", video="reel_lyrics", offset=-1.5); self.assertEqual((code, json.loads(body)["started"]), (200, True))
            self.assertEqual(sent, [(slug, False, "reel", True)])   # the reel only, not the full video
            self.assertEqual(reel_lyrics.offset(D), -1.5); self.assertNotIn("media", navaan.meta(slug)["approvals"])
            self.assertIn("changes requested at media about the reel with lyrics via ui:owner1: lyrics are late", "\n".join(str(h) for h in navaan.meta(slug)["history"]))
            sent.clear(); code, body = req(note="too dark", video="full"); self.assertEqual(json.loads(body)["started"], True); self.assertEqual(sent, [(slug, False, "video", True)])
            sent.clear(); code, body = req(note="old style, note only"); self.assertEqual((code, json.loads(body)["started"]), (200, False)); self.assertEqual(sent, [])   # without a video it only records the note, as before
        with mock.patch.object(U.jobs, "active", lambda sl: True): self.assertEqual(req(note="x", video="reel")[0], 409)

    def test_the_instagram_reel_can_go_without_lyrics_and_the_lyrics_can_be_nudged(self):
        import navaan, navaan_common as C, reel_lyrics
        code, body = self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="music", idea="rain")); slug = json.loads(body)["slug"]; D = C.song_dir(slug)
        lyr = lambda **b: self.call("/api/reel/lyrics", "owner-tok", "csrf-owner", post=True, body=dict(slug=slug, **b))
        self.assertEqual(navaan.ig_reel_candidates(slug)[:2], ["final_reel_9x16_cap.mp4", "final_reel_9x16.mp4"])   # with lyrics by default
        code, body = lyr(on=False); self.assertEqual((code, json.loads(body)["on"]), (200, False))
        self.assertEqual(navaan.ig_reel_candidates(slug)[0], "final_reel_9x16.mp4"); self.assertTrue(all("_cap" not in c for c in navaan.ig_reel_candidates(slug)))   # Instagram takes the plain reel
        self.assertFalse(json.loads(self.call(f"/api/song/{slug}", "owner-tok")[1])["reel_lyrics"]["on"])
        code, body = lyr(on=True, offset=1.5); self.assertEqual(json.loads(body), {"ok": True, "on": True, "offset": 1.5}); self.assertEqual(navaan.ig_reel_candidates(slug)[0], "final_reel_9x16_cap.mp4")
        self.assertEqual(lyr(offset="soon")[0], 400); self.assertEqual(lyr(offset=11)[0], 400); self.assertEqual(reel_lyrics.offset(D), 1.5)   # a bad nudge changes nothing
        lyr(offset=0); self.assertFalse(os.path.exists(os.path.join(D, "reel_lyrics.json")))
        self.assertEqual(self.call("/api/reel/lyrics", "lis-tok", "csrf-lis", post=True, body=dict(slug=slug, on=False))[0], 403)
    def test_an_inspiration_can_take_its_voice_from_a_suno_link_and_a_bad_link_creates_nothing(self):
        import suno_import, shutil as _sh, subprocess, tempfile as _tf, navaan_common as C, narration
        if not (_sh.which("ffmpeg") and _sh.which("ffprobe")): self.skipTest("ffmpeg is needed")
        t = _tf.mkdtemp(); self.addCleanup(_sh.rmtree, t, True); m4a = os.path.join(t, "voice.m4a")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=5", "-c:a", "aac", m4a], check=True)
        new = lambda **b: self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="inspiration", **b))
        info = {"title": "You Are Allowed to Change", "lyrics": "[Verse]\nYou are allowed to change,\nand grow", "style": "intimate", "video_url": "https://cdn1.suno.ai/x.mp4"}
        before = len(json.loads(self.call("/api/songs", "owner-tok", "csrf-owner")[1]))
        with mock.patch.object(suno_import, "read_page", side_effect=ValueError("I could not find lyrics on that Suno page.")):
            code, body = new(suno_url="https://suno.com/s/abc123", narrate="eleven", voice="suno1"); self.assertEqual(code, 400); self.assertIn("could not find lyrics", json.loads(body)["error"])
        with mock.patch.object(suno_import, "read_page", return_value=info), mock.patch.object(suno_import, "fetch_voice", side_effect=ValueError("The downloaded Suno file is damaged, so I did not use it.")):
            code, body = new(suno_url="https://suno.com/s/abc123"); self.assertEqual(code, 400); self.assertIn("damaged", json.loads(body)["error"])
        with mock.patch.object(suno_import, "read_page", return_value={**info, "video_url": ""}):
            code, body = new(suno_url="https://suno.com/s/abc123"); self.assertEqual(code, 400); self.assertIn("ElevenLabs", json.loads(body)["error"])   # says what to do instead
        self.assertEqual(len(json.loads(self.call("/api/songs", "owner-tok", "csrf-owner")[1])), before)   # the refused ones created nothing
        with mock.patch.object(suno_import, "read_page", return_value=info), mock.patch.object(suno_import, "fetch_voice", return_value=m4a):
            code, body = new(suno_url="https://suno.com/s/abc123", narrate="eleven", voice="suno1")
        self.assertEqual(code, 200); D = C.song_dir(json.loads(body)["slug"])
        self.assertTrue(os.path.isfile(os.path.join(D, "voiceover.m4a"))); self.assertEqual(narration.get_option(D, "voice_from"), "suno")
        self.assertEqual(narration.get_option(D, "narrate"), "eleven")   # ElevenLabs stays the backup: running that step again replaces the Suno voice
        self.assertEqual(json.load(open(os.path.join(D, "quote.json")))["lines"], ["You are allowed to change,", "and grow"])
        self.assertEqual(self.call("/api/new", "lis-tok", "csrf-lis", post=True, body=dict(type="inspiration", suno_url="https://suno.com/s/abc123"))[0], 403)

    def test_a_failed_or_stuck_item_can_be_deleted_and_a_published_one_cannot(self):
        import navaan, navaan_common as C, catalog_store as K
        mk = lambda idea: json.loads(self.call("/api/new", "owner-tok", "csrf-owner", post=True, body=dict(type="music", idea=idea))[1])["slug"]
        dele = lambda slug, tok="owner-tok", csrf="csrf-owner": self.call("/api/delete", tok, csrf, post=True, body=dict(slug=slug))
        gone, kept = mk("a failed one"), mk("a published one"); D = C.song_dir(gone); open(os.path.join(D, "lyrics.txt"), "w").write("kept on disk\n")
        d = json.loads(self.call(f"/api/song/{gone}", "owner-tok")[1]); self.assertEqual(d["deletable"], {"ok": True, "why": ""})
        self.assertEqual(dele(gone, "lis-tok", "csrf-lis")[0], 403)   # a listener has no say
        with mock.patch.object(U.jobs, "active", lambda sl: True): self.assertEqual(dele(gone)[0], 409)   # not while it runs
        code, body = dele(gone); self.assertEqual(code, 200); moved = json.loads(body)["moved_to"]; self.assertTrue(moved.startswith("_deleted/" + gone + "-"))
        self.assertFalse(os.path.exists(D)); self.assertEqual(open(os.path.join(C.songs_root(), moved, "lyrics.txt")).read(), "kept on disk\n")   # moved, not erased
        note = json.load(open(os.path.join(C.songs_root(), moved, "deleted.json"))); self.assertEqual((note["slug"], note["by"]), (gone, "ui:owner1"))
        self.assertNotIn(gone, [r["slug"] for r in json.loads(self.call("/api/songs", "owner-tok")[1])])   # gone from the list
        self.assertEqual(self.call(f"/api/song/{gone}", "owner-tok")[0], 404)   # no such item any more
        navaan.edit_meta(kept, lambda m: m.setdefault("published", {}).update(instagram="https://www.instagram.com/reel/x/"))
        d = json.loads(self.call(f"/api/song/{kept}", "owner-tok")[1]); self.assertFalse(d["deletable"]["ok"]); self.assertIn("Take it down there first", d["deletable"]["why"])
        code, body = dele(kept); self.assertEqual(code, 400); self.assertIn("published", json.loads(body)["error"]); self.assertTrue(os.path.isdir(C.song_dir(kept)))   # a published item stays

    def test_the_owner_switches_automatic_licence_confirmation_on_with_a_statement_and_nobody_else_can(self):
        import licence_cfg
        with mock.patch.dict(os.environ, {"NAVAAN_CONF_DIR": os.path.join(self.tmp.name, "conf")}):
            save = lambda tok="owner-tok", csrf="csrf-owner", **b: self.call("/api/settings/licence_save", tok, csrf, post=True, body=b)
            code, body = save(auto=True, statement=""); self.assertEqual(code, 400); self.assertIn("statement", json.loads(body)["error"]); self.assertFalse(licence_cfg.load()["auto"])
            code, body = save(auto=True, statement="Every song I publish is on a paid Suno plan."); self.assertEqual(code, 200); self.assertTrue(json.loads(body)["licence"]["auto"]); self.assertTrue(licence_cfg.load()["auto"])
            self.assertTrue(json.loads(self.call("/api/settings", "owner-tok")[1])["licence"]["auto"])   # the Settings page reads it back
            self.assertEqual(save("lis-tok", "csrf-lis", auto=False, statement="x")[0], 403); self.assertTrue(licence_cfg.load()["auto"])   # a listener cannot change it
            self.assertEqual(save(auto=False, statement="")[0], 200); self.assertFalse(licence_cfg.load()["auto"])

    def test_the_logo_and_mood_pictures_are_public_art_the_sign_in_page_uses(self):
        d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "moods")); os.makedirs(os.path.join(d, "brand"))
        open(os.path.join(d, "moods", "night-wide.webp"), "wb").write(b"RIFFxxxxWEBP"); open(os.path.join(d, "brand", "mark.png"), "wb").write(b"\x89PNG"); open(os.path.join(d, "index.html"), "w").write("<html>TOPSECRETAPP</html>")
        with mock.patch.dict(os.environ, {"NAVAAN_WEB_DIST": d}):
            st, h, b = self.raw("/app/moods/night-wide.webp"); self.assertEqual((st, h["Content-Type"]), (200, "image/webp")); self.assertIn("max-age", h["Cache-Control"])
            self.assertEqual(self.raw("/app/brand/mark.png")[0], 200)
            self.assertEqual(self.raw("/app/moods/missing.webp")[0], 404)
            self.assertEqual(self.raw("/app/moods/../index.html")[0], 404)   # nothing else of the app leaks without a sign in
            st, h, b = self.raw("/app/index.html"); self.assertNotIn(b"TOPSECRETAPP", b)   # the app itself still asks for a sign in
    def test_the_sign_in_page_can_show_the_version_without_a_session(self):
        code, body = self.call("/auth/state"); d = json.loads(body)
        self.assertEqual(code, 200); self.assertTrue(d.get("version"))   # public: the sign in page prints it
        self.assertNotIn("scheduler", d)   # the rest stays behind the sign in

    def test_a_visitor_can_ask_for_an_account_with_what_they_like_and_only_the_studio_reads_the_count(self):
        env = {"NAVAAN_PUBLIC_HOST": "studio.navaan.online,navaan.online", "NAVAAN_LISTENER_HOSTS": "navaan.online"}
        with mock.patch.dict(os.environ, env):
            pub, studio = "navaan.online", "studio.navaan.online"; post = lambda body, host=pub: self.call("/api/site/interest", None, None, post=True, body=body, host=host)
            self.assertEqual(post({})[0], 400); self.assertEqual(post({"moods": ["Calm"], "email": "nope"})[0], 400)   # something to say, and an email that looks like one
            self.assertEqual(post({"moods": ["Calm", "Calm", "Hopeful"], "genres": ["Indie"], "languages": ["Hindi"], "email": "a@b.co"})[0], 200)
            self.assertEqual(post({"moods": ["Calm"], "website": "http://spam"})[0], 200)   # a bot is thanked and ignored
            self.assertEqual(self.call("/api/site/interest", host=pub)[0], 403)   # a visitor reads nothing
            code, body = self.call("/api/site/interest", "owner-tok", host=studio); d = json.loads(body)
            self.assertEqual((code, d["total"], d["with_email"], d["moods"]), (200, 1, 1, {"Calm": 1, "Hopeful": 1}))   # the repeated word counted once, the bot not at all
            for i in range(6): last = post({"moods": ["Calm"]})[0]
            self.assertEqual(last, 429)

    def test_one_sign_in_covers_every_host_under_the_domain_and_logout_clears_it(self):
        with mock.patch.dict(os.environ, {"NAVAAN_COOKIE_DOMAIN": "navaan.online"}):
            for host in ("navaan.online", "studio.navaan.online"):
                auth.CTX.host = host; auth.CTX.https = True
                c = auth.cookie_header("tok"); self.assertIn("Domain=navaan.online", c); self.assertIn("HttpOnly", c); self.assertIn("SameSite=Strict", c); self.assertIn("Secure", c)
                self.assertEqual(len(auth.login_cookies("tok")), 2); self.assertNotIn("Domain=", auth.login_cookies("tok")[1]); self.assertIn("Max-Age=0", auth.login_cookies("tok")[1])   # and an old host-only cookie is removed
            auth.CTX.host = "navaan.njlabs.dev"; self.assertNotIn("Domain=", auth.cookie_header("tok")); self.assertEqual(len(auth.login_cookies("tok")), 1)   # the old address keeps its own sign in
            auth.CTX.host = "studio.navaan.online"; clears = [auth.cookie_header("", clear=True), auth.cookie_header("", clear=True, host_only=True)]
            self.assertIn("Domain=navaan.online", clears[0]); self.assertNotIn("Domain=", clears[1])
            auth.CTX.https = True
            self.assertEqual(auth.rp_of("studio.navaan.online")[0], "navaan.online"); self.assertEqual(auth.rp_of("navaan.online")[0], "navaan.online"); self.assertEqual(auth.rp_of("studio.navaan.online")[1], "https://studio.navaan.online")
            self.assertEqual(auth.rp_of("navaan.njlabs.dev")[0], "navaan.njlabs.dev")   # a passkey on the old address stays its own

    def test_a_shared_link_is_made_on_the_public_host(self):
        with mock.patch.dict(os.environ, {"NAVAAN_PUBLIC_HOST": "studio.navaan.online,navaan.online", "NAVAAN_LISTENER_HOSTS": "navaan.online"}):
            h = U.H.__new__(U.H); h.headers = {"Host": "studio.navaan.online"}; h.client_address = ("1.1.1.1", 0)
            self.assertEqual(h._base(), "https://navaan.online")

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
        for path in ("/api/songs", "/api/settings", "/api/cloud", "/legacy", "/api/analytics"): self.assertEqual(self.call(path, "lis-tok")[0], 403, path)
        code, body = self.call("/app/studio/songs", "lis-tok"); self.assertEqual(code, 200); self.assertIn(b"csrf-lis", body)   # the app itself is for every signed-in person; it only shows what the routes allow
        code, body = self.call("/", "lis-tok"); self.assertEqual(code, 200); self.assertIn(b"csrf-lis", body)   # the front door leads a listener into the app, not to a refusal
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
        self.assertEqual(st, 200); page = b.decode(); self.assertIn('property="og:title" content="Tere &lt;Hone&gt; Se"', page); self.assertIn("/s/" + tok + "/play.mp3#t=5", page); self.assertIn("/app/song/song-001", page); self.assertNotIn("30 second", page); self.assertNotIn("Sign in", page); self.assertNotIn("<Hone>", page); self.assertIn("noindex", page)
        st, h, b = self.raw(f"/s/{tok}/preview.mp3"); self.assertEqual((st, h["Location"]), (302, "https://bucket.example/navaan/songs/song-001/derived/preview-30s.mp3"))
        st, h, b = self.raw(f"/s/{tok}/play.mp3"); self.assertEqual((st, h["Location"]), (302, "https://bucket.example/navaan/songs/song-001/final.mp3"))   # the whole song, no cookie
        self.assertEqual(self.raw("/s/nonexistent0000")[0], 404)
        st, h, b = self.raw("/img/song-001/320.webp"); self.assertEqual((st, h["Content-Type"]), (200, "image/webp")); self.assertIn("immutable", h["Cache-Control"]); self.assertTrue(b[:4] == b"RIFF")
        self.assertEqual(self.raw("/img/song-001/320.webp", headers={"If-None-Match": h["ETag"]})[0], 304)
        self.assertEqual(self.raw("/img/song-001/999.webp")[0], 404); self.assertEqual(self.raw("/img/ghost/320.webp")[0], 404)
        self.assertEqual(self.raw("/img/song-001/poster-320.webp")[0], 404); self.assertIn("/img/song-001/1280.jpg", self.raw("/s/" + tok)[2].decode())   # no poster yet: the cover is the preview
        K.set_picture("song-001", "poster", pre + "poster_2x3.png", "image/png", len(cover))   # the owner put the poster on share links
        st, h2, b2 = self.raw("/img/song-001/poster-320.webp"); self.assertEqual((st, h2["Content-Type"]), (200, "image/webp")); self.assertNotEqual(h2["ETag"], h["ETag"])   # its own picture and cache entry, not the cover's
        self.assertEqual(self.raw("/img/ghost/poster-320.webp")[0], 404)
        al = K.save_album("", "Raat Ke Baad", "album"); K.reorder(al, ["song-001"]); K.set_album_cover(al, "navaan/albums/" + al + "/cover_1x1.png", len(cover))
        self.assertEqual(self.raw(f"/img/album/{al}/320.webp")[0], 404)   # a draft album's cover is not public
        K.save_album(al, "Raat Ke Baad", "album", "published")
        st, h, b = self.raw(f"/img/album/{al}/320.webp"); self.assertEqual((st, h["Content-Type"]), (200, "image/webp")); self.assertIn("immutable", h["Cache-Control"])
        self.assertEqual(self.raw(f"/img/album/{al}/poster-320.webp")[0], 404); self.assertEqual(self.raw("/img/album/ghost/320.webp")[0], 404)   # an album has a cover, no poster
        self.assertEqual(self.raw("/img/" + al + "/320.webp")[0], 404)   # and the album's name is not a song's
        code, body = post("owner-tok", "csrf-owner", "/api/share", album=al); self.assertEqual(code, 200); atok = json.loads(body)["token"]; self.assertTrue(json.loads(body)["url"].endswith("/s/" + atok))
        st, h, b = self.raw("/s/" + atok); self.assertEqual(st, 200); self.assertIn("Album by", b.decode()); self.assertIn(f"/s/{atok}/play/song-001.mp3", b.decode())   # a visitor with no cookie sees the album and can play its songs
        st, h, b = self.raw(f"/s/{atok}/play/song-001.mp3"); self.assertEqual((st, h["Location"]), (302, "https://bucket.example/navaan/songs/song-001/final.mp3"))
        self.assertEqual(self.raw(f"/s/{atok}/play/ghost.mp3")[0], 404); self.assertEqual(self.raw(f"/s/{atok}/play.mp3")[0], 404); self.assertEqual(self.raw(f"/s/{atok}/preview.mp3")[0], 404)   # only a song of this album, only whole
        self.assertEqual(self.raw(f"/s/{tok}/play/song-001.mp3")[0], 404)   # a song's own link plays only that song's page
        self.assertEqual(post("owner-tok", "csrf-owner", "/api/share", album="no-such-album")[0], 404)
        self.assertEqual(post("lis-tok", "csrf-lis", "/api/poster/publish", slug="song-001")[0], 403); self.assertEqual(post("owner-tok", "csrf-owner", "/api/poster/publish", slug="song-001")[0], 400)   # a listener has no say; the owner is told there is no poster yet
        page = self.raw("/s/" + tok)[2].decode(); self.assertIn("/img/song-001/poster-1280.jpg", page); self.assertNotIn("/img/song-001/1280.jpg", page)   # the poster replaces the cover in the link preview
        code, body = self.call("/api/share", "owner-tok"); self.assertEqual([x["opens"] for x in json.loads(body)], [3])   # the page was opened three times (once, then before and after the poster was put on it); the preview does not count
        rows = json.loads(self.call("/api/songs", "owner-tok")[1]); self.assertEqual(rows[0]["art"]["colour"], "#c82828"); self.assertGreater(rows[0]["art"]["v"], 0)   # the list is told the cover exists, its colour (set by the first resize above) and its version, which goes in the picture's address
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
