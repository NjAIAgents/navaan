"""Tests for the YouTube recommendation rules and their link into the shared store. Run: python3 -W ignore -m unittest test_yt_reco"""
import json, os, sys, tempfile, unittest, datetime

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
sys.path.insert(0, SCRIPTS)
import analytics_db as db
import ig_reco as rc
import yt_reco as yr

CH = "UCabc"
NOW = "2026-10-13T12:00:00Z"
NOWDT = rc.parse_ts(NOW)


def ts(days_ago, hour=10):
    return (NOWDT - datetime.timedelta(days=days_ago)).replace(hour=hour, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def day(d):
    return (NOWDT - datetime.timedelta(days=d)).strftime("%Y-%m-%d")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "t.db")
        self.conn = db.connect(self.path)
        self.conn.execute("INSERT INTO yt_channels (channel_id, label, title, created_at, analytics_ok) VALUES (?,?,?,?,1)", (CH, "music", "NAVAAN", NOW))
        self.n = 0

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def video(self, age, views=1000, kind="video", pct=45.0, privacy="public", slug=None, lang=None, subs=3, title=None):
        self.n += 1
        vid = f"v{self.n}"
        if slug:
            db.upsert(self.conn, "songs", {"slug": slug, "title": slug.title(), "language": lang, "genre": "Pop", "updated_at": NOW}, ("slug",))
        self.conn.execute("INSERT INTO yt_videos (video_id, channel_id, slug, kind, title, published_at, duration_s, privacy, first_seen_at, last_seen_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (vid, CH, slug, kind, title or f"Title {self.n}", ts(age), 200 if kind == "video" else 40, privacy, NOW, NOW))
        if views is not None:
            self.conn.execute("INSERT INTO yt_snapshots (video_id, captured_at, views, likes, comments, minutes_watched, avg_view_s, avg_view_pct, subs_gained, subs_lost, shares) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                              (vid, NOW, views, 50, 5, 300.0, 90.0, pct, subs, 0, 2))
        self.conn.commit()
        return vid

    def run_ok(self, days_ago=0):
        self.conn.execute("INSERT INTO yt_runs (run_id, channel_id, started_at, finished_at, status) VALUES (?,?,?,?,?)", (f"r{days_ago}{self.n}", CH, ts(days_ago), ts(days_ago), "ok"))
        self.conn.commit()

    def daily(self, metric, d):
        for k, v in d.items():
            db.upsert(self.conn, "yt_daily", {"channel_id": CH, "period_end": day(k), "metric": metric, "value": v, "collected_at": NOW}, ("channel_id", "period_end", "metric"))
        self.conn.commit()

    def healthy(self):
        self.run_ok()
        for a in (8, 15, 22, 29, 36, 43):
            self.video(a, views=1000 + a)

    def rules(self):
        D = yr.load(self.conn, CH, NOWDT)
        return {x["rule_id"]: x for x in yr.run_rules(D, yr.settings())}


class TestRules(Base):
    def test_empty_channel(self):
        r = self.rules()
        self.assertEqual(r["yt_data_stale"]["severity"], "high")
        self.assertIn("yt_data_thin", r)

    def test_healthy_channel_is_quiet(self):
        self.healthy()
        self.assertEqual(set(self.rules()) - {"yt_best_video_pattern"}, set())

    def test_no_analytics_login(self):
        self.healthy()
        self.conn.execute("UPDATE yt_channels SET analytics_ok = 0")
        self.assertIn("yt_no_analytics", self.rules())

    def test_still_private(self):
        self.healthy()
        self.video(5, views=0, privacy="private")
        self.video(1, views=0, privacy="private")
        e = self.rules()["yt_still_private"]["evidence"]
        self.assertEqual(len(e["videos"]), 1)

    def test_posting_gap_and_cadence(self):
        self.run_ok()
        for a in (16, 22, 30, 40, 50):
            self.video(a)
        self.assertEqual(self.rules()["yt_posting_gap"]["severity"], "medium")
        self.conn.execute("DELETE FROM yt_videos")
        self.conn.execute("DELETE FROM yt_snapshots")
        for a in (31, 40, 50, 60):
            self.video(a)
        self.assertEqual(self.rules()["yt_posting_gap"]["severity"], "high")
        self.conn.execute("DELETE FROM yt_videos")
        self.conn.execute("DELETE FROM yt_snapshots")
        self.video(3)
        for a in (60, 70, 80, 90):
            self.video(a)
        r = self.rules()
        self.assertIn("yt_cadence_low", r)
        self.assertNotIn("yt_posting_gap", r)

    def test_subscriber_stall_and_low_rate(self):
        self.healthy()
        self.daily("subscribers_count", {d: 120 for d in range(0, 14)})
        self.daily("views", {d: 100 for d in range(0, 28)})
        self.daily("subs_gained", {d: 0 for d in range(0, 28)})
        r = self.rules()
        self.assertIn("yt_subs_stall", r)
        self.assertEqual(r["yt_low_subscribe_rate"]["evidence"]["per_1000_views"], 0)

    def test_views_decline(self):
        self.healthy()
        self.daily("views", {**{d: 100 for d in range(8, 14)}, **{d: 30 for d in range(0, 7)}})
        self.assertIn("yt_views_decline", self.rules())

    def test_underperformer_and_weak_retention_compare_same_kind_only(self):
        self.healthy()
        for a in (10, 12, 14, 18):
            self.video(a, views=50000, kind="short", pct=90.0)   # shorts are huge: must not make the full videos look weak
        r = self.rules()
        self.assertNotIn("yt_underperformer", r)
        w = self.video(9, views=200, pct=15.0)
        r = self.rules()
        self.assertEqual(r["yt_underperformer"]["subject"], w)
        self.assertEqual(r["yt_weak_retention"]["subject"], w)

    def test_young_videos_not_judged(self):
        self.healthy()
        self.video(2, views=5, pct=5.0)
        r = self.rules()
        self.assertNotIn("yt_underperformer", r)
        self.assertNotIn("yt_weak_retention", r)

    def test_early_dropoff_from_retention_curve(self):
        self.healthy()
        vid = self.video(5, views=800)
        for ratio, w in ((0.01, 1.0), (0.10, 0.35), (0.5, 0.2)):
            self.conn.execute("INSERT INTO yt_retention (video_id, captured_on, ratio, watch_ratio) VALUES (?,?,?,?)", (vid, day(0), ratio, w))
        self.conn.commit()
        e = self.rules()["yt_early_dropoff"]["evidence"]
        self.assertEqual(e["watching_at_10pct"], 0.35)

    def test_shorts_vs_full(self):
        self.healthy()
        for a in (10, 12, 14):
            self.video(a, views=9000, kind="short")
        self.assertIn("yt_shorts_vs_full", self.rules())

    def test_language_gap_full_videos_only(self):
        self.run_ok()
        for a, lang in ((8, "Hindi"), (15, "Hindi"), (22, "English"), (29, "English"), (36, "Hindi"), (43, "English")):
            self.video(a, views=3000 if lang == "Hindi" else 1000, slug=f"s{a}", lang=lang)
        self.assertEqual(self.rules()["yt_language_gap"]["evidence"]["better"], "Hindi")

    def test_traffic_rules(self):
        self.healthy()
        for src, v in (("SHORTS", 700), ("YT_SEARCH", 10), ("BROWSE", 90)):
            self.conn.execute("INSERT INTO yt_traffic (channel_id, captured_on, source, views) VALUES (?,?,?,?)", (CH, day(0), src, v))
        self.conn.commit()
        r = self.rules()
        self.assertIn("yt_search_low", r)
        self.assertIn("yt_shorts_feed_dependent", r)

    def test_comments_unanswered(self):
        self.healthy()
        vid = "v1"
        for cid, parent, own, when in (("a", None, 0, 3), ("b", None, 0, 2), ("r", "a", 1, 2)):
            self.conn.execute("INSERT INTO yt_comments (comment_id, video_id, parent_id, text, posted_at, is_own, first_seen_at, last_seen_at) VALUES (?,?,?,?,?,?,?,?)", (cid, vid, parent, "t", ts(when), own, NOW, NOW))
        self.conn.commit()
        self.assertEqual(self.rules()["yt_comments_unanswered"]["evidence"]["waiting"], 1)

    def test_every_rule_has_advice(self):
        for rid in ("yt_data_stale", "yt_no_analytics", "yt_data_thin", "yt_still_private", "yt_posting_gap", "yt_cadence_low", "yt_subs_stall", "yt_views_decline", "yt_low_subscribe_rate",
                    "yt_underperformer", "yt_weak_retention", "yt_early_dropoff", "yt_best_video_pattern", "yt_shorts_vs_full", "yt_language_gap", "yt_genre_gap", "yt_search_low",
                    "yt_shorts_feed_dependent", "yt_comments_unanswered", "yt_audience_split"):
            a = yr.advice({"rule_id": rid, "evidence": {}, "detail": "d", "title": "t"})
            self.assertTrue(a and a["title"] and a["action"], rid)


class TestStore(Base):
    def setUp(self):
        super().setUp()
        self.healthy()
        self.weak = self.video(9, views=200, pct=15.0)

    def test_analyze_and_idempotent(self):
        res = yr.analyze(self.conn, CH, NOW)
        self.assertGreaterEqual(res["findings"], 2)
        n = (db.one(self.conn, "SELECT COUNT(*) AS n FROM findings")["n"], db.one(self.conn, "SELECT COUNT(*) AS n FROM recommendations")["n"])
        yr.analyze(self.conn, CH, NOW)
        self.assertEqual(n, (db.one(self.conn, "SELECT COUNT(*) AS n FROM findings")["n"], db.one(self.conn, "SELECT COUNT(*) AS n FROM recommendations")["n"]))
        recs = db.rows(self.conn, "SELECT * FROM recommendations")
        self.assertTrue(all(r["ig_user_id"] == CH and r["rule_id"].startswith("yt_") for r in recs))

    def test_claude_recs_validate_and_supersede(self):
        yr.analyze(self.conn, CH, NOW)
        f = db.one(self.conn, "SELECT finding_id FROM findings WHERE rule_id = 'yt_weak_retention'")["finding_id"]
        rule_rec = db.one(self.conn, "SELECT rec_id FROM recommendations WHERE rule_id = 'yt_weak_retention'")["rec_id"]
        item = {"title": "Cut the slow middle", "why": "w", "action": "Trim 20s.", "expected_effect": "More watched", "category": "retention", "priority": 1, "confidence": "medium", "finding_ids": [f]}
        res = rc.add_recs(self.conn, CH, [item], NOW)
        self.assertEqual(len(res["stored"]), 1, res)
        self.assertEqual(db.one(self.conn, "SELECT status FROM recommendations WHERE rec_id = ?", (rule_rec,))["status"], "superseded")
        bad = rc.add_recs(self.conn, CH, [{**item, "title": "Other", "finding_ids": ["nope"]}], NOW)
        self.assertEqual(bad["stored"], [])

    def test_done_baseline_and_outcome_use_youtube_metrics(self):
        yr.analyze(self.conn, CH, NOW)
        rid = db.one(self.conn, "SELECT rec_id FROM recommendations")["rec_id"]
        rc.set_status(self.conn, rid, "done", None, NOW)
        base = json.loads(db.one(self.conn, "SELECT baseline_json FROM recommendations WHERE rec_id = ?", (rid,))["baseline_json"])
        self.assertIn("median_avg_view_pct", base)
        later = "2026-11-05T12:00:00Z"
        for i in range(3):
            self.n += 1
            vid = f"after{self.n}"
            posted = (NOWDT + datetime.timedelta(days=2 + 4 * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.conn.execute("INSERT INTO yt_videos (video_id, channel_id, kind, title, published_at, privacy, first_seen_at, last_seen_at) VALUES (?,?,?,?,?,?,?,?)", (vid, CH, "video", "t", posted, "public", later, later))
            self.conn.execute("INSERT INTO yt_snapshots (video_id, captured_at, views, avg_view_pct) VALUES (?,?,?,?)", (vid, later, 5000, 70.0))
        self.conn.commit()
        rc.outcomes(self.conn, later)
        o = json.loads(db.one(self.conn, "SELECT outcome_json FROM recommendations WHERE rec_id = ?", (rid,))["outcome_json"])
        self.assertEqual(o["verdict"], "improved")
        self.assertIn("median_avg_view_pct", o["change_pct"])

    def test_instagram_and_youtube_do_not_mix(self):
        self.conn.execute("INSERT INTO accounts (ig_user_id, label, username, created_at) VALUES ('1784','music','navaan_p5l',?)", (NOW,))
        self.conn.commit()
        yr.analyze(self.conn, CH, NOW)
        rc.analyze(self.conn, "1784", NOW)
        self.assertTrue(all(r["rule_id"].startswith("yt_") for r in db.rows(self.conn, "SELECT rule_id FROM findings WHERE ig_user_id = ?", (CH,))))
        self.assertFalse(any(r["rule_id"].startswith("yt_") for r in db.rows(self.conn, "SELECT rule_id FROM findings WHERE ig_user_id = '1784'")))
        rc.outcomes(self.conn, NOW)   # must not crash on a mix of platforms

    def test_notes_are_filtered_by_platform(self):
        rc.add_notes(self.conn, "Shorts length", "x", "https://a.com/1", now=NOW, platform="youtube")
        rc.add_notes(self.conn, "Reels hooks", "y", "https://a.com/2", now=NOW, platform="instagram")
        rc.add_notes(self.conn, "General", "z", "https://a.com/3", now=NOW)
        yt_topics = sorted(n["topic"] for n in yr.pack(self.conn, CH, NOW)["market"]["notes"])
        self.assertEqual(yt_topics, ["General", "Shorts length"])
        D = rc.load(self.conn, "x", NOWDT)
        self.assertEqual(sorted(n["topic"] for n in D["notes"]), ["General", "Reels hooks"])
        with self.assertRaises(ValueError):
            rc.add_notes(self.conn, "t", "s", "https://a.com", now=NOW, platform="tiktok")

    def test_pack_shape(self):
        yr.analyze(self.conn, CH, NOW)
        p = yr.pack(self.conn, CH, NOW)
        for k in ("platform", "account", "top_videos", "findings", "recommendations_so_far", "market", "rules_for_the_advisor", "retention_at_10pct", "traffic_sources_28d"):
            self.assertIn(k, p)
        self.assertEqual(p["platform"], "youtube")
        json.dumps(p)


if __name__ == "__main__":
    unittest.main()
