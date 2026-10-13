"""Tests for the recommendation engine. Run: python3 -W ignore -m unittest test_ig_reco  (from this folder). Synthetic SQLite database, no network."""
import json, os, sys, tempfile, unittest, datetime

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
sys.path.insert(0, SCRIPTS)
import analytics_db as db
import ig_reco as rc

UID = "1784"
NOW = "2026-10-13T12:00:00Z"
NOWDT = rc.parse_ts(NOW)


def ts(days_ago, hour=10):
    d = NOWDT - datetime.timedelta(days=days_ago)
    return d.replace(hour=hour, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def day(days_ago):
    return (NOWDT - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "t.db"))
        self.conn.execute("INSERT INTO accounts (ig_user_id, label, username, created_at) VALUES (?,?,?,?)", (UID, "music", "navaan_p5l", NOW))
        self.n = 0

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def post(self, age, views=1000, reach=800, saved=40, shares=20, likes=100, comments=10, watch_ms=9000, caption="cap", hour=10, slug=None, lang=None, genre=None):
        self.n += 1
        mid = f"m{self.n}"
        if slug:
            self.conn.execute("INSERT OR REPLACE INTO songs (slug, title, genre, language, updated_at) VALUES (?,?,?,?,?)", (slug, slug.title(), genre, lang, NOW))
        self.conn.execute("INSERT INTO media (media_id, ig_user_id, slug, product_type, permalink, caption, posted_at, first_seen_at, last_seen_at) VALUES (?,?,?,?,?,?,?,?,?)",
                          (mid, UID, slug, "REELS", f"https://x/{mid}", caption, ts(age, hour), NOW, NOW))
        if views is not None:
            self.conn.execute("INSERT INTO media_snapshots (media_id, captured_at, like_count, comments_count, reach, views, saved, shares, avg_watch_time_ms) VALUES (?,?,?,?,?,?,?,?,?)",
                              (mid, NOW, likes, comments, reach, views, saved, shares, watch_ms))
        self.conn.commit()
        return mid

    def collected(self, days_ago=0):
        self.conn.execute("INSERT INTO collector_runs (run_id, ig_user_id, started_at, finished_at, status) VALUES (?,?,?,?,?)", (f"r{self.n}{days_ago}", UID, ts(days_ago), ts(days_ago), "ok"))
        self.conn.commit()

    def daily(self, metric, values_by_days_ago):
        for d, v in values_by_days_ago.items():
            self.conn.execute("INSERT OR REPLACE INTO account_daily (ig_user_id, period_end, metric, value, collected_at) VALUES (?,?,?,?,?)", (UID, day(d), metric, v, NOW))
        self.conn.commit()

    def rules(self):
        D = rc.load(self.conn, UID, NOWDT)
        T, tz = rc.settings()
        return {x["rule_id"]: x for x in rc.run_rules(D, T, tz)}

    def healthy(self):
        """Five decent posts, fresh data, steady cadence: no alarms expected."""
        self.collected()
        for a in (1, 4, 8, 11, 15, 19):
            self.post(a)


class TestRules(Base):
    def test_empty_account(self):
        r = self.rules()
        self.assertIn("data_stale", r)
        self.assertIn("data_thin", r)
        self.assertEqual(r["data_stale"]["severity"], "high")

    def test_healthy_account_is_quiet(self):
        self.healthy()
        r = self.rules()
        self.assertEqual(set(r) - {"best_post_pattern"}, set(), r.keys())

    def test_stale_data(self):
        self.healthy()
        self.conn.execute("DELETE FROM collector_runs")
        self.collected(days_ago=5)
        self.assertIn("data_stale", self.rules())

    def test_posting_gap_and_severity(self):
        self.collected()
        for a in (9, 12, 15, 18, 21):
            self.post(a)
        self.assertEqual(self.rules()["posting_gap"]["severity"], "medium")
        self.post(20)  # older post, gap unchanged
        self.conn.execute("DELETE FROM media")
        for a in (16, 20, 24, 28, 30):
            self.post(a)
        self.assertEqual(self.rules()["posting_gap"]["severity"], "high")

    def test_cadence_low(self):
        self.collected()
        self.post(2)
        for a in (40, 50, 60, 70):
            self.post(a)
        r = self.rules()
        self.assertIn("cadence_low", r)
        self.assertNotIn("posting_gap", r)

    def test_follower_stall(self):
        self.healthy()
        self.daily("followers_count", {d: 120 for d in range(0, 14)})
        r = self.rules()
        self.assertIn("follower_stall", r)
        self.daily("followers_count", {d: 100 + (14 - d) for d in range(0, 14)})
        self.assertNotIn("follower_stall", self.rules())

    def test_views_decline(self):
        self.healthy()
        self.daily("views", {**{d: 100 for d in range(8, 14)}, **{d: 30 for d in range(0, 7)}})
        e = self.rules()["views_decline"]["evidence"]
        self.assertLess(e["views_last_7d"], e["views_prev_7d"])

    def test_underperformer_and_weak_hook(self):
        self.healthy()
        self.post(5, views=200, watch_ms=3000)
        r = self.rules()
        self.assertIn("underperformer", r)
        self.assertIn("weak_hook", r)

    def test_new_posts_are_not_judged(self):
        self.healthy()
        self.post(1, views=10, watch_ms=500)
        self.assertNotIn("underperformer", self.rules())

    def test_passive_likes_and_low_conversation(self):
        self.collected()
        for a in (1, 4, 8, 11, 15):
            self.post(a, likes=200, saved=2, shares=1, comments=1)
        r = self.rules()
        self.assertIn("passive_likes", r)
        self.assertIn("low_conversation", r)

    def test_low_distribution(self):
        self.healthy()
        self.daily("followers_count", {0: 5000})
        self.assertIn("low_distribution", self.rules())

    def test_timing_mismatch(self):
        self.collected()
        for a in (1, 4, 8, 11, 15):
            self.post(a, hour=3)
        for h in range(24):
            self.conn.execute("INSERT INTO online_hours (ig_user_id, captured_on, hour, followers) VALUES (?,?,?,?)", (UID, day(0), h, 100 if h in (17, 18, 19) else 5))
        self.conn.commit()
        e = self.rules()["timing_mismatch"]["evidence"]
        self.assertEqual(e["peak_hours_utc"], [17, 18, 19])
        self.assertTrue(e["peak_hours_local"][0].startswith("17:00 UTC"))

    def test_timing_ok_when_close(self):
        self.collected()
        for a in (1, 4, 8, 11, 15):
            self.post(a, hour=18)
        for h in range(24):
            self.conn.execute("INSERT INTO online_hours (ig_user_id, captured_on, hour, followers) VALUES (?,?,?,?)", (UID, day(0), h, 100 if h in (17, 18, 19) else 5))
        self.conn.commit()
        self.assertNotIn("timing_mismatch", self.rules())

    def test_language_gap(self):
        self.collected()
        for a, lang in ((1, "Hindi"), (4, "Hindi"), (8, "English"), (11, "English"), (15, "Hindi"), (19, "English")):
            self.post(a, views=3000 if lang == "Hindi" else 1000, slug=f"s{a}", lang=lang, genre="Pop")
        r = self.rules()
        self.assertEqual(r["language_gap"]["evidence"]["better"], "Hindi")
        self.assertNotIn("genre_gap", r)

    def test_comments_unanswered(self):
        self.healthy()
        mid = "m1"
        self.conn.execute("INSERT INTO comments (comment_id, media_id, text, posted_at, first_seen_at, last_seen_at) VALUES ('c1',?,?,?,?,?)", (mid, "nice", ts(3), NOW, NOW))
        self.conn.execute("INSERT INTO comments (comment_id, media_id, text, posted_at, first_seen_at, last_seen_at) VALUES ('c2',?,?,?,?,?)", (mid, "love", ts(2), NOW, NOW))
        self.conn.commit()
        self.assertEqual(self.rules()["comments_unanswered"]["evidence"]["waiting"], 2)
        self.conn.execute("INSERT INTO comments (comment_id, media_id, parent_id, is_own, text, posted_at, first_seen_at, last_seen_at) VALUES ('c3',?,'c1',1,'thanks',?,?,?)", (mid, ts(2), NOW, NOW))
        self.conn.commit()
        self.assertEqual(self.rules()["comments_unanswered"]["evidence"]["waiting"], 1)

    def test_audience_split(self):
        self.healthy()
        for b, v in (("IN", 60), ("US", 40)):
            self.conn.execute("INSERT INTO audience (ig_user_id, captured_on, breakdown, bucket, value) VALUES (?,?,?,?,?)", (UID, day(0), "country", b, v))
        self.conn.commit()
        self.assertIn("audience_split", self.rules())

    def test_peer_gap_and_hashtags(self):
        self.healthy()
        self.daily("followers_count", {0: 1000})
        for u in ("a", "b", "c"):
            self.conn.execute("INSERT INTO peers (username, added_at, last_fetched_at, followers_count) VALUES (?,?,?,?)", (u, NOW, NOW, 1000))
            for i in range(5):
                self.conn.execute("INSERT INTO peer_media (username, media_id, caption, posted_at, like_count, comments_count, captured_at) VALUES (?,?,?,?,?,?,?)", (u, f"{u}{i}", "x", ts(i * 5), 400, 40, NOW))
        for i in range(3):
            self.conn.execute("INSERT INTO hashtag_media (hashtag, media_id, kind, caption, captured_at) VALUES (?,?,?,?,?)", ("indiepop", f"h{i}", "top_media", "song #indiepop #lofi", NOW))
        self.conn.commit()
        r = self.rules()
        self.assertIn("peer_engagement_gap", r)
        self.assertIn("lofi", r["hashtag_overlap"]["evidence"]["tags"])


class TestStore(Base):
    def setUp(self):
        super().setUp()
        self.collected()
        for a in (1, 4, 8, 11, 15, 19):
            self.post(a)
        self.post(6, views=200, watch_ms=3000)

    def test_analyze_creates_findings_and_rule_recs(self):
        res = rc.analyze(self.conn, UID, NOW)
        self.assertGreaterEqual(res["findings"], 2)
        recs = db.rows(self.conn, "SELECT * FROM recommendations WHERE source = 'rule'")
        self.assertTrue(recs)
        for r in recs:
            self.assertEqual(r["status"], "open")
            self.assertTrue(json.loads(r["finding_ids"]))
            self.assertIn(r["priority"], (1, 2, 3))

    def test_analyze_idempotent(self):
        rc.analyze(self.conn, UID, NOW)
        a = (db.one(self.conn, "SELECT COUNT(*) AS n FROM findings")["n"], db.one(self.conn, "SELECT COUNT(*) AS n FROM recommendations")["n"])
        rc.analyze(self.conn, UID, NOW)
        b = (db.one(self.conn, "SELECT COUNT(*) AS n FROM findings")["n"], db.one(self.conn, "SELECT COUNT(*) AS n FROM recommendations")["n"])
        self.assertEqual(a, b)

    def test_first_seen_kept_and_resolved(self):
        rc.analyze(self.conn, UID, NOW)
        f1 = db.one(self.conn, "SELECT * FROM findings WHERE rule_id = 'underperformer'")
        later = "2026-10-14T12:00:00Z"
        rc.analyze(self.conn, UID, later)
        f2 = db.one(self.conn, "SELECT * FROM findings WHERE finding_id = ?", (f1["finding_id"],))
        self.assertEqual(f2["first_seen_at"], NOW)
        self.assertEqual(f2["last_seen_at"], later)
        self.conn.execute("DELETE FROM media_snapshots WHERE media_id = ?", (f1["subject"],))
        self.conn.commit()
        rc.analyze(self.conn, UID, "2026-10-15T12:00:00Z")
        self.assertEqual(db.one(self.conn, "SELECT status FROM findings WHERE finding_id = ?", (f1["finding_id"],))["status"], "resolved")

    def test_dismissed_rec_stays_dismissed(self):
        rc.analyze(self.conn, UID, NOW)
        rid = db.one(self.conn, "SELECT rec_id FROM recommendations WHERE rule_id = 'underperformer'")["rec_id"]
        rc.set_status(self.conn, rid, "dismissed", "not relevant", NOW)
        rc.analyze(self.conn, UID, NOW)
        r = db.one(self.conn, "SELECT status, dismissed_reason FROM recommendations WHERE rec_id = ?", (rid,))
        self.assertEqual((r["status"], r["dismissed_reason"]), ("dismissed", "not relevant"))

    def test_add_notes_requires_source(self):
        with self.assertRaises(ValueError):
            rc.add_notes(self.conn, "Reels length", "short is good", None, now=NOW)
        with self.assertRaises(ValueError):
            rc.add_notes(self.conn, "Reels length", "short is good", "ftp://x", now=NOW)
        with self.assertRaises(ValueError):
            rc.add_notes(self.conn, "Reels length", "short is good", "https://x.com/a", confidence="sure", now=NOW)
        nid = rc.add_notes(self.conn, "Reels length", "short is good", "https://x.com/a", now=NOW)
        self.assertTrue(nid.startswith("n-"))
        self.assertEqual(nid, rc.add_notes(self.conn, "Reels length", "updated", "https://x.com/a", now=NOW))
        self.assertEqual(db.one(self.conn, "SELECT COUNT(*) AS n FROM market_notes")["n"], 1)

    def test_expired_notes_hidden_from_pack(self):
        rc.add_notes(self.conn, "old", "x", "https://x.com/old", ttl_days=1, now="2026-08-01T00:00:00Z")
        rc.add_notes(self.conn, "new", "y", "https://x.com/new", now=NOW)
        topics = [n["topic"] for n in rc.pack(self.conn, UID, NOW)["market"]["notes"]]
        self.assertEqual(topics, ["new"])

    def good(self, fid_, **kw):
        d = {"title": "Open with the hook line", "why": "w", "action": "Start on the chorus.", "expected_effect": "More watch time", "category": "hook", "priority": 1,
             "confidence": "medium", "finding_ids": [fid_]}
        d.update(kw)
        return d

    def test_add_recs_validation(self):
        rc.analyze(self.conn, UID, NOW)
        f = db.one(self.conn, "SELECT finding_id FROM findings WHERE rule_id = 'weak_hook'")["finding_id"]
        bad = [self.good(f, finding_ids=[], note_ids=[]), self.good(f, finding_ids=["nope"]), self.good(f, category="magic"), self.good(f, priority=9),
               self.good(f, title=""), self.good(f, confidence="sure"), self.good(f, action="x" * 600)]
        res = rc.add_recs(self.conn, UID, bad, NOW)
        self.assertEqual(res["stored"], [])
        self.assertEqual(len(res["rejected"]), len(bad))
        with self.assertRaises(ValueError):
            rc.add_recs(self.conn, UID, [], NOW)
        with self.assertRaises(ValueError):
            rc.add_recs(self.conn, UID, [self.good(f, title=f"t{i}") for i in range(9)], NOW)

    def test_add_recs_cites_notes_and_dedupes_titles(self):
        rc.analyze(self.conn, UID, NOW)
        nid = rc.add_notes(self.conn, "Hooks", "first 3 seconds matter", "https://x.com/h", now=NOW)
        res = rc.add_recs(self.conn, UID, [self.good(None, finding_ids=[], note_ids=[nid])], NOW)
        self.assertEqual(len(res["stored"]), 1)
        again = rc.add_recs(self.conn, UID, [self.good(None, finding_ids=[], note_ids=[nid], title="open with the HOOK line!")], NOW)
        self.assertEqual(again["stored"], [])
        self.assertIn("already exists", again["rejected"][0])

    def test_claude_rec_supersedes_rule_rec(self):
        rc.analyze(self.conn, UID, NOW)
        row = db.one(self.conn, "SELECT finding_id FROM findings WHERE rule_id = 'weak_hook'")
        rule_rec = db.one(self.conn, "SELECT rec_id FROM recommendations WHERE rule_id = 'weak_hook'")["rec_id"]
        res = rc.add_recs(self.conn, UID, [self.good(row["finding_id"])], NOW)
        self.assertEqual(len(res["stored"]), 1)
        self.assertEqual(db.one(self.conn, "SELECT status FROM recommendations WHERE rec_id = ?", (rule_rec,))["status"], "superseded")
        rc.analyze(self.conn, UID, NOW)  # must not bring the rule rec back
        self.assertEqual(db.one(self.conn, "SELECT status FROM recommendations WHERE rec_id = ?", (rule_rec,))["status"], "superseded")
        self.assertEqual(db.one(self.conn, "SELECT COUNT(*) AS n FROM recommendations WHERE rule_id = 'weak_hook' AND status = 'open'")["n"], 0)

    def test_status_transitions(self):
        rc.analyze(self.conn, UID, NOW)
        rid = db.one(self.conn, "SELECT rec_id FROM recommendations")["rec_id"]
        rc.set_status(self.conn, rid, "done", None, NOW)
        r = db.one(self.conn, "SELECT * FROM recommendations WHERE rec_id = ?", (rid,))
        self.assertEqual(r["status"], "done")
        self.assertEqual(r["done_at"], NOW)
        self.assertIn("median_views", json.loads(r["baseline_json"]))
        rc.set_status(self.conn, rid, "open", None, NOW)
        r = db.one(self.conn, "SELECT * FROM recommendations WHERE rec_id = ?", (rid,))
        self.assertEqual((r["status"], r["done_at"]), ("open", None))
        with self.assertRaises(ValueError):
            rc.set_status(self.conn, rid, "maybe")
        with self.assertRaises(ValueError):
            rc.set_status(self.conn, "missing", "done")

    def outcome_for(self, new_views, new_saved, count):
        rc.analyze(self.conn, UID, NOW)
        rid = db.one(self.conn, "SELECT rec_id FROM recommendations")["rec_id"]
        rc.set_status(self.conn, rid, "done", None, NOW)
        later = "2026-10-30T12:00:00Z"
        for a in range(count):
            self.n += 1
            mid = f"after{self.n}"
            posted = (rc.parse_ts(NOW) + datetime.timedelta(days=2 + 3 * a)).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.conn.execute("INSERT INTO media (media_id, ig_user_id, posted_at, first_seen_at, last_seen_at) VALUES (?,?,?,?,?)", (mid, UID, posted, later, later))
            self.conn.execute("INSERT INTO media_snapshots (media_id, captured_at, like_count, comments_count, reach, views, saved, shares) VALUES (?,?,?,?,?,?,?,?)", (mid, later, 100, 10, 800, new_views, new_saved, 10))
        self.conn.commit()
        rc.outcomes(self.conn, later)
        return json.loads(db.one(self.conn, "SELECT outcome_json FROM recommendations WHERE rec_id = ?", (rid,))["outcome_json"])

    def test_outcome_too_early(self):
        self.assertEqual(self.outcome_for(5000, 200, 1)["verdict"], "too early")

    def test_outcome_improved(self):
        o = self.outcome_for(3000, 240, 3)
        self.assertEqual(o["verdict"], "improved")
        self.assertGreater(o["change_pct"]["median_views"], 100)

    def test_outcome_worse(self):
        self.assertEqual(self.outcome_for(300, 5, 3)["verdict"], "worse")

    def test_outcome_flat(self):
        self.assertEqual(self.outcome_for(1000, 40, 3)["verdict"], "flat")

    def test_pack_shape(self):
        rc.analyze(self.conn, UID, NOW)
        p = rc.pack(self.conn, UID, NOW)
        for k in ("account", "top_posts", "findings", "recommendations_so_far", "market", "rules_for_the_advisor", "settings"):
            self.assertIn(k, p)
        self.assertTrue(all("finding_id" in x for x in p["findings"]))
        json.dumps(p)
        self.assertEqual(p["findings"][0]["severity"] in ("high", "medium", "low", "info"), True)

    def test_every_rule_has_advice(self):
        D = rc.load(self.conn, UID, NOWDT)
        for rid in ("data_stale", "data_thin", "posting_gap", "cadence_low", "follower_stall", "views_decline", "engagement_decline", "underperformer", "weak_hook",
                    "best_post_pattern", "passive_likes", "low_conversation", "low_distribution", "timing_mismatch", "language_gap", "genre_gap", "comments_unanswered",
                    "caption_traits", "audience_split", "peer_engagement_gap", "peer_cadence_gap", "hashtag_overlap"):
            a = rc.advice({"rule_id": rid, "evidence": {}, "detail": "d", "title": "t"})
            self.assertTrue(a and a["title"] and a["action"], rid)


class TestPortalApi(Base):
    def setUp(self):
        super().setUp()
        import analytics_api as api
        self.api = api
        self.path = os.path.join(self.tmp.name, "t.db")
        self.collected()
        for a in (1, 4, 8, 11, 15, 19):
            self.post(a)
        self.post(6, views=200, watch_ms=3000)

    def test_overview_before_and_after_analysis(self):
        o = self.api.overview("all", 30, self.path)
        self.assertTrue(o["reco"]["ready"])
        self.assertEqual(o["reco"]["open"], [])
        res = self.api.analyze_now("all", self.path)
        self.assertEqual(res[0]["label"], "music")
        o = self.api.overview("all", 30, self.path)
        self.assertTrue(o["reco"]["open"])
        r = o["reco"]["open"][0]
        self.assertTrue(r["evidence"])
        self.assertEqual(r["account"], "music")
        json.dumps(o)

    def test_old_database_without_reco_tables_does_not_break_overview(self):
        self.conn.execute("DROP TABLE recommendations")
        self.conn.commit()
        o = self.api.overview("all", 30, self.path)
        self.assertFalse(o["empty"])
        self.assertFalse(o["reco"]["ready"])

    def test_status_endpoint_helpers(self):
        self.api.analyze_now("all", self.path)
        rid = self.api.overview("all", 30, self.path)["reco"]["open"][0]["rec_id"]
        self.api.set_rec_status(rid, "dismissed", "not for me", self.path)
        o = self.api.overview("all", 30, self.path)["reco"]
        self.assertEqual([r["rec_id"] for r in o["dismissed"]], [rid])
        self.assertEqual(o["dismissed"][0]["dismissed_reason"], "not for me")
        self.api.set_rec_status(rid, "done", None, self.path)
        self.assertEqual([r["rec_id"] for r in self.api.overview("all", 30, self.path)["reco"]["done"]], [rid])
        for bad in ("x", "r-zz", "../etc"):
            with self.assertRaises(ValueError):
                self.api.set_rec_status(bad, "done", None, self.path)
        with self.assertRaises(ValueError):
            self.api.set_rec_status(rid, "weird", None, self.path)

    def test_analyze_rejects_bad_account_and_empty_db(self):
        with self.assertRaises(ValueError):
            self.api.analyze_now("a b; rm", self.path)
        empty = os.path.join(self.tmp.name, "empty.db")
        db.connect(empty).close()
        with self.assertRaises(ValueError):
            self.api.analyze_now("all", empty)

    def test_ask_runs_headless_command_once(self):
        import time
        old = {k: os.environ.get(k) for k in ("NAVAAN_CLAUDE_CMD", "NAVAAN_CLAUDE_FLAGS")}
        os.environ["NAVAAN_CLAUDE_CMD"], os.environ["NAVAAN_CLAUDE_FLAGS"] = "echo", ""
        try:
            self.assertTrue(self.api.start_ask("music"))
            self.assertFalse(self.api.start_ask("music"))
            for _ in range(50):
                if not self.api.ASK["running"]:
                    break
                time.sleep(0.1)
            self.assertEqual(self.api.ASK["rc"], 0)
            self.assertIn("growth-advice", self.api.ASK["tail"])
            self.assertIn("Organic growth only", self.api.ASK["tail"])
            with self.assertRaises(ValueError):
                self.api.start_ask("bad name")
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_ask_missing_claude_reports_clearly(self):
        import time
        old = os.environ.get("NAVAAN_CLAUDE_CMD")
        os.environ["NAVAAN_CLAUDE_CMD"] = "definitely-not-a-real-claude-binary"
        try:
            self.assertTrue(self.api.start_ask("all"))
            for _ in range(50):
                if not self.api.ASK["running"]:
                    break
                time.sleep(0.1)
            self.assertEqual(self.api.ASK["rc"], 127)
            self.assertIn("not found", self.api.ASK["tail"])
        finally:
            if old is None:
                os.environ.pop("NAVAAN_CLAUDE_CMD", None)
            else:
                os.environ["NAVAAN_CLAUDE_CMD"] = old


class TestPerContent(Base):
    def setUp(self):
        super().setUp()
        import analytics_api as api
        self.api = api
        self.path = os.path.join(self.tmp.name, "t.db")
        self.collected()
        for a in (3, 8, 12, 16):
            self.post(a, views=1000 + a * 10)
        self.target = self.post(5, views=3000, slug="moh", lang="Hindi", genre="Pop")
        self.conn.execute("INSERT INTO media_snapshots (media_id, captured_at, views, reach, saved, shares, like_count, comments_count) VALUES (?,?,?,?,?,?,?,?)",
                          (self.target, "2026-10-12T00:00:00Z", 2000, 1500, 50, 20, 150, 20))
        self.conn.execute("INSERT INTO comments (comment_id, media_id, username, text, posted_at, first_seen_at, last_seen_at) VALUES ('cx', ?, 'fan', 'lovely', ?, ?, ?)", (self.target, ts(2), NOW, NOW))
        self.conn.commit()

    def test_song_view_compares_with_account(self):
        v = self.api.song_view("moh", self.path)
        self.assertFalse(v["empty"])
        p = v["posts"][0]
        self.assertEqual(p["media_id"], self.target)
        self.assertEqual(p["views"], 3000)
        self.assertEqual(p["compare"]["views_rank"], 1)
        self.assertGreater(p["compare"]["views_vs_median"], 2)
        self.assertEqual(len(p["history"]), 2)
        self.assertEqual(len(p["comments_waiting"]), 1)
        self.assertEqual(v["totals"]["views"], 3000)
        json.dumps(v)

    def test_song_view_carries_findings_and_recs_for_the_post(self):
        self.post(6, views=100, watch_ms=1000, slug="weak")
        rc.analyze(self.conn, UID, NOW)
        v = self.api.song_view("weak", self.path)
        self.assertTrue(any(f["rule_id"] == "underperformer" for f in v["posts"][0]["findings"]))
        self.assertTrue(v["posts"][0]["recommendations"])

    def test_unlinked_song_offers_candidates(self):
        v = self.api.song_view("not-posted-yet", self.path)
        self.assertEqual(v["posts"], [])
        self.assertEqual(len(v["unlinked"]), 4)

    def test_manual_link_and_unlink(self):
        free = self.post(2, views=500)
        self.api.link_post(free, "new-song", self.path)
        self.assertEqual(self.api.song_view("new-song", self.path)["posts"][0]["media_id"], free)
        self.assertEqual(self.api.by_song(self.path)["new-song"]["views"], 500)
        self.api.link_post(free, "", self.path)
        self.assertEqual(self.api.song_view("new-song", self.path)["posts"], [])
        for bad in (("../x", "s"), (free, "bad slug!"), ("nope", "s")):
            with self.assertRaises(ValueError):
                self.api.link_post(bad[0], bad[1], self.path)

    def test_manual_link_survives_collect_relinking(self):
        import ig_collect as ig
        free = self.post(2, views=500)
        self.api.link_post(free, "hand", self.path)
        ig.link_songs(self.conn)
        self.assertEqual(db.one(self.conn, "SELECT slug FROM media WHERE media_id = ?", (free,))["slug"], "hand")

    def test_by_song_and_bad_input(self):
        b = self.api.by_song(self.path)
        self.assertEqual(b["moh"]["posts"], 1)
        self.assertEqual(self.api.by_song(os.path.join(self.tmp.name, "missing.db")), {})
        with self.assertRaises(ValueError):
            self.api.song_view("../etc/passwd", self.path)
        self.assertTrue(self.api.song_view("x", os.path.join(self.tmp.name, "missing.db"))["empty"])


if __name__ == "__main__":
    unittest.main()
