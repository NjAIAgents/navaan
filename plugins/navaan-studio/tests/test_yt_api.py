"""Tests for the YouTube side of the portal API. Run: python3 -W ignore -m unittest test_yt_api"""
import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_yt_reco import Base, CH, NOW, NOWDT, ts, day
import analytics_api as api
import _pgenv  # noqa: F401  (must come before analytics_db)
import analytics_db as db
import ig_reco as rc


class Api(Base):
    def setUp(self):
        super().setUp()
        self.conn.commit()
        self.path = os.path.join(self.tmp.name, "t.db")
        self.run_ok()
        for k in range(1, 8):
            self.daily("subscribers_count", {k: 100 - k})
        self.daily("views", {1: 50, 2: 40, 3: 30})
        self.daily("minutes_watched", {1: 120.0, 2: 60.0})
        self.daily("subs_gained", {1: 4, 2: 2})
        self.daily("subs_lost", {1: 1})
        self.moh = self.video(10, views=3000, slug="moh", lang="Hindi", pct=70.0, subs=9)
        self.short = self.video(9, views=900, kind="short", slug="moh", pct=90.0)
        for a in (12, 20, 28, 35):
            self.video(a, views=1000 + a)
        self.conn.execute("INSERT INTO yt_snapshots (video_id, captured_at, views, likes, comments, minutes_watched, avg_view_s, avg_view_pct, subs_gained, subs_lost, shares) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (self.moh, "2026-10-12T00:00:00Z", 2000, 40, 4, 200.0, 80.0, 65.0, 5, 0, 1))
        for r, w in ((0.0, 1.0), (0.1, 0.8), (0.5, 0.5), (1.0, 0.2)):
            self.conn.execute("INSERT INTO yt_retention (video_id, captured_on, ratio, watch_ratio, relative) VALUES (?,?,?,?,?)", (self.moh, "2026-10-13", r, w, None))
        self.conn.execute("INSERT INTO yt_traffic (channel_id, captured_on, source, views, minutes) VALUES (?,?,?,?,?)", (CH, "2026-10-13", "YT_SEARCH", 70, 10.0))
        self.conn.execute("INSERT INTO yt_traffic (channel_id, captured_on, source, views, minutes) VALUES (?,?,?,?,?)", (CH, "2026-10-13", "SHORTS", 30, 5.0))
        self.conn.execute("INSERT INTO yt_audience (channel_id, captured_on, breakdown, bucket, value) VALUES (?,?,?,?,?)", (CH, "2026-10-13", "country", "IN", 80))
        self.conn.execute("INSERT INTO yt_comments (comment_id, video_id, parent_id, username, text, posted_at, is_own, first_seen_at, last_seen_at) VALUES ('c1', ?, NULL, 'fan', 'beautiful', ?, 0, ?, ?)",
                          (self.moh, ts(1), NOW, NOW))
        self.conn.execute("INSERT INTO yt_runs (run_id, channel_id, started_at, finished_at, status, stats_json, errors_json) VALUES ('rx', ?, ?, ?, 'partial', '{\"videos\": 6}', '[{\"where\": \"retention\", \"error\": \"thin\"}]')", (CH, NOW, NOW))
        self.conn.commit()

    def test_overview_shapes(self):
        o = api.yt_overview("all", 30, self.path)
        self.assertFalse(o["empty"])
        k = o["kpis"]
        self.assertEqual(k["waiting"], 1)
        self.assertEqual(k["subs_gained"], 6)
        self.assertEqual(k["subs_net"], 5)
        self.assertEqual(k["watch_hours"], 3.0)
        self.assertIsNotNone(k["subscribers_change"])
        names = {v["video_id"]: v for v in o["videos"]}
        self.assertEqual(names[self.moh]["views"], 3000)
        self.assertEqual(names[self.moh]["name"], "Moh")
        self.assertTrue(names[self.short]["url"].startswith("https://www.youtube.com/shorts/"))
        self.assertEqual(len(names[self.moh]["trend"]), 2)
        self.assertEqual([t["source"] for t in o["traffic"]], ["YT_SEARCH", "SHORTS"])
        self.assertEqual(o["audience"]["country"][0], ["IN", 80])
        self.assertEqual(o["retention"][0]["video_id"], self.moh)
        self.assertEqual(o["runs"][0]["errors"], 1)
        self.assertTrue(o["analytics_ok"])
        self.assertEqual({r["name"] for r in o["patterns"]["kind"]}, {"video", "short"})
        json.dumps(o)

    def test_overview_without_youtube_data(self):
        c = db.connect(os.path.join(self.tmp.name, "other.db"))
        c.close()
        o = api.yt_overview("all", 30, os.path.join(self.tmp.name, "other.db"))
        self.assertTrue(o["empty"])
        self.assertEqual(o["reason"], "no_data")
        self.assertTrue(api.yt_overview("all", 30, os.path.join(self.tmp.name, "missing.db"))["empty"])

    def test_song_view_has_youtube_block(self):
        v = api.song_view("moh", self.path)
        y = v["youtube"]
        self.assertEqual({x["video_id"] for x in y["videos"]}, {self.moh, self.short})
        full = [x for x in y["videos"] if x["video_id"] == self.moh][0]
        self.assertEqual(full["compare"]["views_rank"], 1)
        self.assertGreater(full["compare"]["views_vs_median"], 2)
        self.assertEqual(len(full["history"]), 2)
        self.assertEqual(len(full["retention"]), 4)
        self.assertEqual(len(full["comments_waiting"]), 1)
        self.assertEqual(y["totals"]["views"], 3900)
        short = [x for x in y["videos"] if x["video_id"] == self.short][0]
        self.assertEqual(short["compare"]["same_kind_videos"], 1)   # compared with shorts only
        json.dumps(v)

    def test_song_findings_use_the_video_id(self):
        bad = self.video(15, views=100, slug="weak", pct=10.0)
        api.analyze_now("all", self.path, "youtube")
        y = api.song_view("weak", self.path)["youtube"]["videos"][0]
        self.assertTrue(y["findings"])
        self.assertTrue(all(f["rule_id"].startswith("yt_") for f in y["findings"]))

    def test_song_recommendations_are_full_cards_that_cite_the_video(self):
        self.video(15, views=100, slug="weak", pct=10.0)
        api.analyze_now("all", self.path, "youtube")
        y = api.song_view("weak", self.path)["youtube"]["videos"][0]
        ids = {f["finding_id"] for f in y["findings"]}
        c = db.connect(self.path)
        R = api.recommendations(c, [CH], "youtube")
        want = {r["rec_id"] for r in R["open"] + R["done"] if ids & set(r["finding_ids"])}
        self.assertEqual({r["rec_id"] for r in y["recommendations"]}, want)
        for r in y["recommendations"]:
            for k in ("why", "action", "evidence", "finding_ids", "confidence", "priority", "status", "category"):
                self.assertIn(k, r)
        json.dumps(y)

    def test_unlinked_videos_are_offered_and_link_survives(self):
        y = api.song_view("nothing-yet", self.path)["youtube"]
        self.assertEqual(y["videos"], [])
        self.assertGreaterEqual(len(y["unlinked"]), 4)
        vid = y["unlinked"][0]["video_id"]
        api.link_video(vid, "hand", self.path)
        self.assertEqual(api.song_view("hand", self.path)["youtube"]["videos"][0]["video_id"], vid)
        import yt_collect
        c = db.connect(self.path)
        yt_collect.link_songs(c)
        self.assertEqual(db.one(c, "SELECT slug FROM yt_videos WHERE video_id = ?", (vid,))["slug"], "hand")
        c.close()
        api.link_video(vid, "", self.path)
        self.assertEqual(api.song_view("hand", self.path)["youtube"]["videos"], [])
        for bad in (("../x", "s"), (vid, "bad slug!"), ("nope12345", "s")):
            with self.assertRaises(ValueError):
                api.link_video(bad[0], bad[1], self.path)

    def test_by_song_merges_youtube_totals(self):
        b = api.by_song(self.path)
        self.assertEqual(b["moh"]["yt_videos"], 2)
        self.assertEqual(b["moh"]["yt_views"], 3900)
        self.assertEqual(b["moh"]["posts"], 0)

    def test_platform_state_is_separate(self):
        self.assertIsNot(api._state("youtube")[0], api._state("instagram")[0])
        self.assertIsNot(api._state("youtube")[1], api._state("instagram")[1])
        with self.assertRaises(ValueError):
            api._state("tiktok")
        self.assertIn("--platform youtube", api.ask_prompt("music", "youtube"))
        self.assertNotIn("--platform youtube", api.ask_prompt("music", "instagram"))

    def test_analyze_now_and_recommendations_for_youtube(self):
        res = api.analyze_now("all", self.path, "youtube")
        self.assertEqual(res[0]["label"], "music")
        o = api.yt_overview("all", 30, self.path)
        self.assertTrue(o["reco"]["ready"])
        self.assertEqual(o["reco"]["ask"], api.YT_ASK)
        self.assertTrue(o["reco"]["open"])
        r = o["reco"]["open"][0]
        self.assertEqual(r["account"], "music")
        self.assertTrue(r["evidence"])
        # marking one done stores a YouTube baseline and the outcome reads it
        api.set_rec_status(r["rec_id"], "done", None, self.path)
        c = db.connect(self.path)
        row = db.one(c, "SELECT baseline_json FROM recommendations WHERE rec_id = ?", (r["rec_id"],))
        self.assertIn("median_avg_view_pct", json.loads(row["baseline_json"]))
        c.close()

    def test_market_notes_are_filtered_by_platform(self):
        c = db.connect(self.path)
        rc.add_notes(c, "yt topic", "only for youtube", url="https://example.com/y", platform="youtube")
        rc.add_notes(c, "ig topic", "only for instagram", url="https://example.com/i", platform="instagram")
        c.close()
        api.analyze_now("all", self.path, "youtube")
        c = db.connect(self.path, readonly=True)
        yt = api.recommendations(c, [CH], "youtube")
        ig = api.recommendations(c, [CH], "instagram")
        c.close()
        self.assertEqual(yt["notes"], 1)
        self.assertEqual(ig["notes"], 1)

    def test_implement_works_for_a_youtube_recommendation(self):
        api.analyze_now("all", self.path, "youtube")
        o = api.yt_overview("all", 30, self.path)
        rid = [r for r in o["reco"]["open"] if r["category"] != "timing"][0]["rec_id"]
        rules = os.path.join(self.tmp.name, "rules.json")
        keep = api.rules_path
        api.rules_path = lambda: rules      # never touch the real standing_rules.json
        try:
            res = api.implement_rec(rid, self.path)
            saved = json.load(open(rules))
        finally:
            api.rules_path = keep
        self.assertEqual(saved[0]["platform"], "youtube")
        self.assertEqual(res["kind"], "rule")


if __name__ == "__main__":
    unittest.main()
