"""Author: Navjyot Nishant
Created: 2026-11-13
Last updated: 2026-11-13
Description: spec 003, album release. A song is never public on its own: its full video waits for its album; the Short goes out alone as a teaser; releasing an album lists it and every song at once and hands each full video to the scheduler.
"""
import json, os, sys, tempfile, types, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name; self.addCleanup(os.environ.pop, "NAVAAN_ROOT", None)
        import navaan_common as C, catalog_store as K, navaan as N
        self.C, self.K, self.N = C, K, N; K._LOCAL.conn = None; self.addCleanup(lambda: getattr(K._LOCAL, "conn", None) and K._LOCAL.conn.close())

    def song(self, slug, title="A Song", album=None, extra=None, kind="music"):
        D = os.path.join(self.C.songs_root(), slug); os.makedirs(D)
        open(os.path.join(D, "title.txt"), "w", encoding="utf-8").write(title + "\n")
        m = {"slug": slug, "type": kind, "state": "published", **({"album": album} if album else {}),
             "cloud": {"verified": True, "uploaded_at": "2026-10-01T10:00:00Z", "prefix": f"n/{slug}/", "objects": {"final.mp3": {"size": 1}}},
             "published": {"youtube_items": [{"id": f"{slug}-full", "file": "final_16x9.mp4", "privacy": "private"}, {"id": f"{slug}-short", "file": "final_reel_9x16.mp4", "privacy": "private"}]},
             **(extra or {})}
        self.C.item_save(slug, m); self.K.sync_item(slug); return D


class Hold(Base):
    def test_a_song_in_an_unreleased_album_waits_and_says_for_which_album(self):
        self.song("song-001", album="First Light")
        self.assertEqual(self.N.album_hold("song-001"), "Waiting for album release: First Light. Release the album to make this song public.")
        self.song("song-002")
        self.assertIn("Add this song to an album", self.N.album_hold("song-002"))

    def test_a_released_or_legacy_song_and_other_types_are_not_held(self):
        self.song("song-001", album="First Light", extra={"release": {"album": "first-light", "at": "x", "by": "owner"}})
        self.song("song-002", extra={"release": {"legacy": True}})
        self.song("insp-001", kind="inspiration")
        self.assertEqual([self.N.album_hold(s) for s in ("song-001", "song-002", "insp-001")], [None, None, None])

    def test_run_stops_at_go_public_with_code_7_unless_the_scheduler_is_firing_a_released_song(self):
        self.song("song-001", album="First Light")
        seen = []
        with mock.patch.object(self.N, "plan", lambda s: ([], {"type": "run", "step": "go_public"})), mock.patch.object(self.N, "account_problem", lambda s, sid: None), \
             mock.patch.object(self.N, "gate_ok", lambda *a, **k: True), mock.patch("builtins.print", lambda *a, **k: seen.append(" ".join(map(str, a)))):
            import contextvars
            self.assertEqual(contextvars.copy_context().run(self.N._run, "song-001", step="go_public", retries=0), 7)   # _run binds the step to the log context: keep it out of the other tests
        self.assertTrue(any("Waiting for album release: First Light" in x for x in seen))

    def test_the_plan_shows_the_hold_and_lets_instagram_go_on(self):
        self.song("song-001", album="First Light")
        st = lambda sid, done=False, before=None: {"id": sid, "label": sid, "kind": "script", "done": (lambda m, d=done: d), "before": before, "after": None}
        steps = [st("video", True), st("youtube_short", True, "publish_short"), st("go_public", False, "go_public"), st("instagram_caption"), st("publish_instagram", False, "publish_instagram")]
        with mock.patch.object(self.N, "steps", lambda slug, D: steps), mock.patch.object(self.N, "gate_ok", lambda D, ap, g, published=False: g != "go_public"), mock.patch.object(self.N, "ig_enabled", lambda m: True):
            rows, nxt, lanes = self.N.plan_lanes("song-001")
            r = {x["id"]: x for x in rows}["go_public"]
            self.assertEqual((r["status"], r["needs_gate"]), ("waiting for album release", None))   # no per-song approval offered (FR-003)
            self.assertEqual(nxt, {"type": "run", "step": "instagram_caption"})   # the teaser lane is not stuck behind the hold
        steps[3]["done"] = steps[4]["done"] = (lambda m: True)
        with mock.patch.object(self.N, "steps", lambda slug, D: steps), mock.patch.object(self.N, "ig_enabled", lambda m: True):
            self.assertEqual(self.N.plan("song-001")[1]["type"], "held")

    def test_go_public_is_done_with_the_full_video_and_the_short_has_its_own_step(self):
        full = {"id": "f", "file": "final_16x9.mp4", "privacy": "public"}; short = {"id": "s", "file": "final_reel_9x16.mp4", "privacy": "private"}
        m = {"type": "music", "published": {"youtube_items": [full, short]}}
        self.assertTrue(self.N.public_done(m)); self.assertFalse(self.N.short_public_done(m))
        self.assertFalse(self.N.public_done({**m, "type": "inspiration"}))   # other types: every upload, as before


class OnlyFlag(Base):
    def flip(self, only):
        import publish_youtube as Y
        self.song("song-001", extra={"approvals": {"go_public": {"at": "x"}, "publish_short": {"at": "x"}}})
        updated = []
        class Req:
            def __init__(self, r): self.r = r
            def execute(self): return self.r
        class Videos:
            def list(self, part, id): return Req({"items": [{"id": i, "status": {"privacyStatus": "private"}} for i in id.split(",")]})
            def update(self, part, body): updated.append(body["id"]); return Req({})
        svc = types.SimpleNamespace(videos=lambda: Videos())
        with mock.patch.object(Y, "service", lambda: svc), mock.patch.object(Y, "write_published", lambda s: None), mock.patch("builtins.print"):
            Y.go_public(types.SimpleNamespace(slug="song-001", yes=True, only=only))
        return updated

    def test_only_short_flips_the_short_and_only_full_the_full_video(self):
        self.assertEqual(self.flip("short"), ["song-001-short"])

    def test_only_full(self):
        self.assertEqual(self.flip("full"), ["song-001-full"])

    def test_both_when_left_out(self):
        self.assertEqual(sorted(self.flip(None)), ["song-001-full", "song-001-short"])


if __name__ == "__main__":
    unittest.main()


class Album(Base):
    def setUp(self):
        super().setUp()
        import album_release as R; self.R = R
        for s in ("song-001", "song-002"): self.song(s, s.title(), album="First Light")
        self.ready = mock.patch.object(R, "_why_not", lambda s: None); self.ready.start(); self.addCleanup(self.ready.stop)   # readiness has its own test below

    def listed(self):
        return {r["slug"]: r["status"] for r in self.K._conn().execute("SELECT slug, status FROM tracks").fetchall()}


class Release(Album):
    def test_release_now_lists_the_album_and_every_song_and_hands_each_full_video_to_the_scheduler(self):
        self.assertEqual(self.listed(), {"song-001": "draft", "song-002": "draft"})
        st = self.R.confirm("first-light", ["song-001", "song-002"], "owner1")
        self.assertEqual(st["status"], "published"); self.assertEqual(self.listed(), {"song-001": "published", "song-002": "published"})
        self.assertEqual([a["slug"] for a in self.K.public_albums(True)], ["first-light"])
        for s in ("song-001", "song-002"):
            m = self.C.item_load(s)
            self.assertEqual(m["approvals"]["go_public"]["via"], "album release first-light by owner1")
            self.assertEqual((m["release"]["album"], m["schedule"]["done"]), ("first-light", False)); self.assertTrue(m["schedule"]["youtube_at"])
            self.assertTrue(any("released with album first-light" in h for h in m["history"]))
            self.assertIsNone(self.N.album_hold(s))   # the scheduler's go_public now passes
        self.K.sync_all(); self.assertEqual(set(self.listed().values()), {"published"})   # a later sync keeps them listed

    def test_a_changed_song_list_or_a_song_not_ready_is_refused_and_nothing_changes(self):
        self.assertRaises(ValueError, self.R.confirm, "first-light", ["song-001"], "owner1")
        with mock.patch.object(self.R, "_why_not", lambda s: "gate media not approved" if s == "song-002" else None):
            with self.assertRaises(self.R.NotReady) as cm: self.R.confirm("first-light", ["song-001", "song-002"], "owner1")
        self.assertEqual([(x["slug"], x["reason"]) for x in cm.exception.state["songs"]], [("song-001", None), ("song-002", "gate media not approved")])
        self.assertEqual(set(self.listed().values()), {"draft"}); self.assertNotIn("go_public", self.C.item_load("song-001").get("approvals", {}))
        self.K.save_album("", "Empty"); st = self.R.status("empty"); self.assertEqual((st["ready"], st["blocked"]), (False, "Add at least one song"))

    def test_the_listing_is_all_or_nothing(self):
        with mock.patch.object(self.K, "_reindex_album", side_effect=RuntimeError("db down")):
            self.assertRaises(RuntimeError, self.R.confirm, "first-light", ["song-001", "song-002"], "owner1")
        self.assertEqual(set(self.listed().values()), {"draft"}); self.assertEqual(self.K.albums()[0]["status"], "draft")
        self.assertFalse(self.C.released(self.C.item_load("song-001")))

    def test_a_later_time_schedules_it_and_a_time_too_soon_is_refused(self):
        import datetime
        later = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        st = self.R.confirm("first-light", ["song-001", "song-002"], "owner1", at=later)
        self.assertEqual((st["status"], st["release_at"]), ("scheduled", later)); self.assertEqual(set(self.listed().values()), {"draft"})
        self.assertNotIn("release", self.C.item_load("song-001"))
        soon = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertRaises(ValueError, self.R.confirm, "first-light", ["song-001", "song-002"], "owner1", at=soon)

    def test_a_failed_song_can_be_tried_again_and_progress_is_shown_per_song(self):
        self.R.confirm("first-light", ["song-001", "song-002"], "owner1")
        self.C.item_update("song-001", lambda m: m["schedule"].setdefault("attempts", {}).__setitem__("go_public", {"n": 3, "last": "x", "error": "quota"}))
        s = {x["slug"]: x for x in self.R.status("first-light")["songs"]}
        self.assertEqual((s["song-001"]["youtube"], s["song-001"]["error"], s["song-002"]["youtube"], s["song-001"]["site"]), ("failed", "quota", "private", "listed"))
        self.R.retry("first-light", "song-001"); self.assertNotIn("go_public", self.C.item_load("song-001")["schedule"].get("attempts", {}))
        self.assertRaises(ValueError, self.R.retry, "first-light", "song-999")
        self.assertRaises(ValueError, self.R.confirm, "first-light", ["song-001", "song-002"], "owner1")   # already released


class Readiness(Base):
    def test_each_song_names_what_is_missing_before_it_can_be_released(self):
        import album_release as R
        self.song("song-001", album="First Light")
        rows = lambda *r: (list(r), {"type": "done"})
        row = lambda i, status="done", gate=None, label=None: {"id": i, "label": label or i, "status": status, "needs_gate": gate}
        cases = [(rows(row("video"), row("archive"), row("youtube_short", "ready"), row("go_public", "ready")), None),   # the teaser Short is not needed
                 (rows(row("video", "waiting for approval", "media"), row("go_public")), "gate media not approved"),
                 (rows(row("video"), row("archive", "ready", label="Publish to NAVAAN"), row("go_public")), "Publish to NAVAAN: not done yet")]
        for plan, want in cases:
            with mock.patch.object(self.N, "plan", lambda s, p=plan: p): self.assertEqual(R._why_not("song-001"), want)


class Scheduled(Album):
    def schedule(self, hours=1):
        import datetime
        t = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0) + datetime.timedelta(hours=hours)
        self.R.confirm("first-light", ["song-001", "song-002"], "owner1", at=t.strftime("%Y-%m-%dT%H:%M:%SZ")); return t

    def test_nothing_before_the_time_then_it_releases(self):
        import datetime
        t = self.schedule()
        self.assertEqual(self.R.tick(t - datetime.timedelta(minutes=1)), []); self.assertEqual(set(self.listed().values()), {"draft"})
        self.assertEqual(self.R.tick(t + datetime.timedelta(seconds=30)), [("first-light", "released")])
        self.assertEqual(set(self.listed().values()), {"published"}); self.assertEqual(self.C.item_load("song-001")["release"]["album"], "first-light")
        self.assertEqual(self.R.tick(t + datetime.timedelta(minutes=5)), [])   # once

    def test_a_song_not_ready_waits_with_the_reason_then_the_release_is_missed_and_alerted(self):
        import datetime, settings_api
        t = self.schedule()
        with mock.patch.object(self.R, "_why_not", lambda s: "gate media not approved" if s == "song-002" else None):
            self.assertEqual(self.R.tick(t + datetime.timedelta(minutes=1)), [("first-light", "waiting: Song-002: gate media not approved")])
            self.assertEqual(self.R.status("first-light")["blocked"], "Song-002: gate media not approved")
            self.assertEqual(self.R.tick(t + datetime.timedelta(hours=13)), [("first-light", "missed")])
        self.assertEqual(self.R.status("first-light")["status"], "missed"); self.assertEqual(set(self.listed().values()), {"draft"})
        with mock.patch.object(settings_api, "status", lambda *a, **k: {"accounts": []}), mock.patch.object(settings_api, "claude_status", lambda: {"state": "ok"}), mock.patch.object(settings_api, "conf_disk", lambda: None):
            self.assertIn("album_missed:first-light", [x["id"] for x in settings_api.alerts()])
        st = self.R.confirm("first-light", ["song-001", "song-002"], "owner1"); self.assertEqual(st["status"], "published")   # released again, now

    def test_cancel_takes_back_the_approvals_and_a_changed_song_list_disarms_it(self):
        import datetime
        t = self.schedule()
        self.R.cancel("first-light", "owner1")
        self.assertEqual(self.R.status("first-light")["status"], "draft"); self.assertNotIn("go_public", self.C.item_load("song-001").get("approvals", {}))
        self.assertEqual(self.R.tick(t + datetime.timedelta(minutes=1)), []); self.assertRaises(ValueError, self.R.cancel, "first-light", "owner1")
        self.schedule(); self.K.reorder("first-light", ["song-002", "song-001"]); self.assertFalse(self.R.disarm("first-light"))   # a new order alone is fine
        self.K.reorder("first-light", ["song-001"]); self.assertTrue(self.R.disarm("first-light"))
        self.assertEqual(self.R.status("first-light")["status"], "draft"); self.assertNotIn("go_public", self.C.item_load("song-002").get("approvals", {}))


class Teaser(Base):
    def test_a_teaser_of_an_unreleased_song_points_at_its_album_with_the_date(self):
        import datetime
        self.song("song-001", album="First Light")
        self.assertEqual(self.C.with_site_link("Caption", "song-001", teaser=True), "Caption\n\nComing soon · First Light\nhttps://navaan.online/app/album/first-light")
        t = datetime.datetime(2026, 12, 1, 12, 30, tzinfo=datetime.timezone.utc)
        self.K._tx(lambda c: c.execute("UPDATE albums SET release_at = ? WHERE slug = 'first-light'", (t,)))
        d = t.astimezone()
        self.assertEqual(self.C.with_site_link("", "song-001", plain=True, teaser=True), f"Out {d.day} {d:%b %Y} · First Light\nnavaan.online/app/album/first-light")
        self.assertEqual(self.C.with_site_link("x", "song-001"), "x\n\nHear the full song free: https://navaan.online/app/song/song-001")   # the full video's own description: the song page, which works once released

    def test_a_released_song_and_other_types_are_unchanged(self):
        self.song("song-001", album="First Light", extra={"release": {"album": "first-light", "at": "x", "by": "o"}})
        self.assertEqual(self.C.with_site_link("x", "song-001", teaser=True), "x\n\nHear the full song free: https://navaan.online/app/song/song-001")
        self.assertEqual(self.C.with_site_link("x", None, itype="inspiration", teaser=True), "x\n\nMore from NAVAAN: https://navaan.online")
        self.assertEqual(self.C.with_site_link("x", "song-001", itype="aha", teaser=True), "x")

    def test_the_short_description_has_no_link_to_a_private_full_video(self):
        import short_meta
        D = self.song("song-001", album="First Light", extra={"published": {"youtube_items": [{"id": "f", "file": "final_16x9.mp4", "url": "https://youtu.be/f", "privacy": "private"}]}})
        json.dump({"title": "One", "description": "About it.\n\nMore."}, open(os.path.join(D, "youtube.json"), "w"))
        with mock.patch("builtins.print"): short_meta.main("song-001")
        self.assertNotIn("youtu.be/f", json.load(open(os.path.join(D, "youtube_short.json")))["description"])
        self.C.item_update("song-001", lambda m: m.__setitem__("release", {"album": "first-light", "at": "x", "by": "o"}))
        with mock.patch("builtins.print"): short_meta.main("song-001")
        self.assertIn("Full song: https://youtu.be/f", json.load(open(os.path.join(D, "youtube_short.json")))["description"])


class TeaserLength(Base):
    def test_a_clip_of_an_unreleased_song_must_be_30_to_60_seconds_and_shorter_than_the_song(self):
        D = self.song("song-001", album="First Light"); clip = os.path.join(D, "final_reel_9x16.mp4"); open(clip, "w").close(); open(os.path.join(D, "final.mp3"), "w").close()
        for d, full, bad in ((45, 200, False), (20, 200, True), (75, 200, True), (50, 50, True), (45, None, False)):
            with mock.patch.object(self.C, "duration", lambda p, d=d, full=full: d if p.endswith(".mp4") else full):
                self.assertEqual(bool(self.N.teaser_problem("song-001", clip)), bad, (d, full))
        self.C.item_update("song-001", lambda m: m.__setitem__("release", {"album": "first-light", "at": "x", "by": "o"}))
        with mock.patch.object(self.C, "duration", lambda p: 200): self.assertIsNone(self.N.teaser_problem("song-001", clip))   # released: any length


class ComingSoon(Base):
    def test_an_announced_album_shows_its_date_and_teasers_but_no_songs_and_an_unannounced_one_is_not_found(self):
        import datetime
        self.song("song-001", album="First Light", extra={"published": {"youtube_items": [{"id": "f", "file": "final_16x9.mp4", "privacy": "private", "url": "https://youtu.be/f"},
                                                                         {"id": "s", "file": "final_reel_9x16.mp4", "privacy": "public", "url": "https://youtube.com/shorts/s"}],
                                                                        "instagram": "https://www.instagram.com/reel/r/"}})
        self.assertIsNone(self.K.album_page("first-light", True))
        self.K.save_album("first-light", "First Light", "album", None, None, "", True)
        t = datetime.datetime(2026, 12, 1, 12, 30, tzinfo=datetime.timezone.utc); self.K._tx(lambda c: c.execute("UPDATE albums SET release_at = ?", (t,)))
        p = self.K.album_page("first-light", True)
        self.assertEqual((p["coming_soon"], p["release_at"], p["title"]), (True, "2026-12-01T12:30:00Z", "First Light")); self.assertNotIn("tracks", p)
        self.assertEqual(p["teasers"], [{"platform": "youtube_short", "url": "https://youtube.com/shorts/s"}, {"platform": "instagram", "url": "https://www.instagram.com/reel/r/"}])   # the private full video is not a teaser
        self.assertNotIn("youtu.be/f", json.dumps(p))
        import album_release; mock.patch.object(album_release, "_why_not", lambda s: None).start(); self.addCleanup(mock.patch.stopall)
        album_release.confirm("first-light", ["song-001"], "o")
        p = self.K.album_page("first-light", True); self.assertNotIn("coming_soon", p); self.assertEqual([x["slug"] for x in p["tracks"]], ["song-001"])   # the same address, now the album
