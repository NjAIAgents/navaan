"""Tests for the analytics collector. Run: python3 -m unittest discover -s plugins/navaan-studio/tests
No network: a fake opener answers the Instagram calls."""
import io, json, os, sys, tempfile, unittest, urllib.error, urllib.parse

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
sys.path.insert(0, SCRIPTS)
import analytics_db as db
import ig_collect as ig

TOKEN = "SECRET-TOKEN-123"
UID = "1784"


class Err(Exception):
    def __init__(self, status, code, msg):
        self.status, self.code, self.msg = status, code, msg


def fake_opener(fn, log):
    def opener(req, timeout=0):
        u = urllib.parse.urlparse(req.full_url)
        q = dict(urllib.parse.parse_qsl(u.query))
        path = "/".join(u.path.split("/")[2:]) if u.path.count("/") >= 2 else u.path.strip("/")
        log.append((path, q))
        try:
            return io.BytesIO(json.dumps(fn(path, q)).encode())
        except Err as e:
            body = io.BytesIO(json.dumps({"error": {"code": e.code, "message": e.msg + " " + q.get("access_token", "")}}).encode())
            raise urllib.error.HTTPError(req.full_url, e.status, "err", {}, body)
    return opener


def routes(state):
    def fn(path, q):
        m = q.get("metric", "")
        if path == UID:
            return {"username": "navaan_p5l", "name": "NAVAAN", "followers_count": 120, "follows_count": 3, "media_count": 2}
        if path == f"{UID}/media":
            if "after" not in q and state.get("page2"):
                return {"data": state["media"][:1], "paging": {"next": f"https://graph.instagram.com/v23.0/{UID}/media?after=x&access_token={TOKEN}"}}
            if "after" in q:
                return {"data": state["media"][1:]}
            return {"data": state["media"]}
        if path.endswith("/insights") and path != f"{UID}/insights":
            mid = path.split("/")[0]
            if state.get("batch_fail") and "," in m:
                raise Err(400, 100, "unsupported metric combination")
            if m.startswith("reach") or "," in m or m:
                names = m.split(",")
                bad = state.get("bad_metric")
                if bad and bad in names and len(names) == 1:
                    raise Err(400, 100, f"{bad} not supported")
                if bad and bad in names:
                    raise Err(400, 100, "batch rejected")
                return {"data": [{"name": n, "period": "lifetime", "values": [{"value": state["insights"].get(n, 1)}]} for n in names]}
        if path.endswith("/comments"):
            return {"data": state["comments"].get(path.split("/")[0], [])}
        if path == f"{UID}/tags":
            return {"data": [{"id": "t1", "caption": "love @navaan", "permalink": "https://instagram.com/p/T1/", "timestamp": "2026-10-12T10:00:00+0000", "username": "fan1"}]}
        if path == f"{UID}/insights":
            if m == "reach" or m == "follower_count":
                if state.get("no_follower_count") and m == "follower_count":
                    raise Err(400, 100, "needs 100 followers")
                return {"data": [{"name": m, "values": [{"value": 10, "end_time": "2026-10-12T07:00:00+0000"}]}]}
            if "total_value" == q.get("metric_type") and q.get("metric") == "follower_demographics":
                return {"data": [{"name": "follower_demographics", "total_value": {"breakdowns": [{"results": [{"dimension_values": ["Patna, Bihar"], "value": 40}]}]}}]}
            if m == "online_followers":
                return {"data": [{"name": m, "values": [{"value": {"0": 5, "18": 30}}]}]}
            if q.get("metric_type") == "total_value":
                return {"data": [{"name": n, "total_value": {"value": 7}} for n in m.split(",")]}
        raise Err(404, 100, "unknown " + path)
    return fn


def media(mid, ptype="REELS", ts="2026-10-13T07:01:06+0000", comments=2, short="DebOMYkiYNb"):
    return {"id": mid, "caption": "cap", "media_type": "VIDEO", "media_product_type": ptype, "permalink": f"https://www.instagram.com/reel/{short}/",
            "shortcode": short, "timestamp": ts, "like_count": 9, "comments_count": comments}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["NAVAAN_ROOT"] = self.tmp
        sd = os.path.join(self.tmp, "songs", "song-001")
        os.makedirs(sd)
        for name, data in (("meta.json", {"slug": "song-001", "published": {"instagram": "https://www.instagram.com/reel/DebOMYkiYNb/"}}),
                           ("tags.json", {"title": "Chaan", "genre": "Lo-fi and chill", "language": "Maithili", "album": "Chaan"})):
            with open(os.path.join(sd, name), "w") as f:
                json.dump(data, f)
        self.conn = db.connect(os.path.join(self.tmp, "t.db"))
        self.log = []
        self.sleeps = []
        self.n = 0
        self._ts = db.utcnow

        def tick():
            self.n += 1
            return f"2026-10-13T08:00:{self.n:02d}Z"
        db.utcnow = tick

    def tearDown(self):
        db.utcnow = self._ts
        os.environ.pop("NAVAAN_ROOT", None)

    def client(self, state):
        return ig.Client(UID, TOKEN, opener=fake_opener(routes(state), self.log), sleep=self.sleeps.append)

    def state(self, **kw):
        s = {"media": [media("m1")], "insights": {"reach": 100, "views": 400, "saved": 5, "shares": 3, "ig_reels_avg_watch_time": 8000},
             "comments": {"m1": [{"id": "c1", "text": "waah", "username": "fan1", "timestamp": "2026-10-13T09:00:00+0000", "like_count": 1,
                                  "replies": {"data": [{"id": "c2", "text": "thanks", "username": "navaan_p5l", "timestamp": "2026-10-13T09:05:00+0000"}]}},
                                 {"id": "c3", "text": "more please", "username": "fan2", "timestamp": "2026-10-13T09:10:00+0000"}]}}
        s.update(kw)
        return s

    def run_collect(self, state, only=ig.ALL_COLLECTORS, **opts):
        return ig.collect(self.conn, self.client(state), UID, "music", only, opts)

    def count(self, table):
        return db.one(self.conn, f"SELECT COUNT(*) AS n FROM {table}")["n"]


class CollectTests(Base):
    def test_full_run_stores_everything(self):
        r = self.run_collect(self.state())
        self.assertEqual(r["status"], "ok", r["errors"])
        m = db.one(self.conn, "SELECT * FROM media WHERE media_id = 'm1'")
        self.assertEqual(m["slug"], "song-001")
        self.assertEqual(m["posted_at"], "2026-10-13T07:01:06Z")
        s = db.one(self.conn, "SELECT * FROM media_snapshots WHERE media_id = 'm1'")
        self.assertEqual((s["reach"], s["views"], s["saved"], s["avg_watch_time_ms"], s["like_count"]), (100, 400, 5, 8000, 9))
        self.assertEqual(self.count("comments"), 3)
        own = db.one(self.conn, "SELECT is_own, parent_id FROM comments WHERE comment_id = 'c2'")
        self.assertEqual((own["is_own"], own["parent_id"]), (1, "c1"))
        self.assertEqual(db.one(self.conn, db.UNREPLIED_COUNT_SQL, (UID,))["n"], 1)  # c1 was answered, c3 was not
        self.assertEqual(db.one(self.conn, "SELECT value FROM audience WHERE breakdown = 'city'")["value"], 40)
        self.assertEqual(self.count("online_hours"), 2)
        self.assertEqual(self.count("mentions"), 1)
        self.assertEqual(db.one(self.conn, "SELECT title, language FROM songs WHERE slug = 'song-001'")["language"], "Maithili")
        self.assertGreater(self.count("account_daily"), 3)
        self.assertEqual(db.one(self.conn, "SELECT COUNT(*) AS n FROM account_daily WHERE metric = 'followers_count'")["n"], 1)

    def test_rerun_is_idempotent_and_adds_a_snapshot(self):
        st = self.state()
        self.run_collect(st)
        self.conn.execute("UPDATE comments SET category = 'praise' WHERE comment_id = 'c1'"); self.conn.commit()
        self.run_collect(st)
        self.assertEqual((self.count("media"), self.count("comments"), self.count("mentions")), (1, 3, 1))
        self.assertEqual(self.count("media_snapshots"), 2)
        self.assertEqual(db.one(self.conn, "SELECT category FROM comments WHERE comment_id = 'c1'")["category"], "praise")  # tags survive a re-collect
        self.assertEqual(db.one(self.conn, "SELECT first_seen_at FROM comments WHERE comment_id = 'c1'")["first_seen_at"] < db.one(self.conn, "SELECT last_seen_at FROM comments WHERE comment_id = 'c1'")["last_seen_at"], True)

    def test_unsupported_metric_is_skipped_not_fatal(self):
        r = self.run_collect(self.state(bad_metric="reels_skip_rate"), only=("media",))
        self.assertEqual(r["status"], "ok")
        s = db.one(self.conn, "SELECT reach, skip_rate, raw_json FROM media_snapshots")
        self.assertEqual(s["reach"], 100)
        self.assertIsNone(s["skip_rate"])
        self.assertIn("reels_skip_rate", json.loads(s["raw_json"])["errors"])

    def test_missing_follower_count_is_a_note_not_a_failure(self):
        r = self.run_collect(self.state(no_follower_count=True), only=("account",))
        self.assertEqual(r["status"], "partial")
        self.assertTrue(any("follower_count" in e["where"] for e in r["errors"]))
        self.assertGreater(self.count("account_daily"), 0)

    def test_auth_error_fails_run_and_hides_token(self):
        def fn(path, q):
            raise Err(400, 190, "token expired")
        c = ig.Client(UID, TOKEN, opener=fake_opener(fn, self.log), sleep=self.sleeps.append)
        r = ig.collect(self.conn, c, UID, "music", ig.ALL_COLLECTORS, {})
        self.assertEqual(r["status"], "failed")
        blob = json.dumps(r) + json.dumps(db.rows(self.conn, "SELECT * FROM collector_runs"))
        self.assertNotIn(TOKEN, blob)
        self.assertIn("refresh", blob)
        self.assertEqual(self.sleeps, [])  # auth errors are not retried

    def test_transient_error_retries_with_backoff(self):
        seen = {"n": 0}
        base = routes(self.state())

        def fn(path, q):
            if path == UID and seen["n"] < 2:
                seen["n"] += 1
                raise Err(400, 4, "rate limit")
            return base(path, q)
        c = ig.Client(UID, TOKEN, opener=fake_opener(fn, self.log), sleep=self.sleeps.append)
        r = ig.collect(self.conn, c, UID, "music", ("account",), {})
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertEqual(self.sleeps, [5, 10])

    def test_paging_follows_next_and_deleted_media_is_flagged(self):
        st = self.state(media=[media("m1"), media("m2", short="ZZZ", comments=0)], page2=True)
        self.run_collect(st, only=("media",))
        self.assertEqual(self.count("media"), 2)
        st2 = self.state(media=[media("m1")])
        self.run_collect(st2, only=("media",))
        self.assertIsNotNone(db.one(self.conn, "SELECT deleted_at FROM media WHERE media_id = 'm2'")["deleted_at"])
        self.assertIsNone(db.one(self.conn, "SELECT deleted_at FROM media WHERE media_id = 'm1'")["deleted_at"])

    def test_old_media_is_not_resnapshotted_every_run(self):
        st = self.state(media=[media("m1", ts="2026-01-01T00:00:00+0000")])
        self.run_collect(st, only=("media",))
        self.run_collect(st, only=("media",))
        self.assertEqual(self.count("media_snapshots"), 1)
        self.run_collect(st, only=("media",), force=True)
        self.assertEqual(self.count("media_snapshots"), 2)

    def test_comments_skipped_when_count_unchanged_and_post_is_old(self):
        st = self.state(media=[media("m1", ts="2026-01-01T00:00:00+0000")])
        self.run_collect(st, only=("media", "comments"))
        before = len([1 for p, q in self.log if p.endswith("/comments")])
        self.run_collect(st, only=("media", "comments"))
        self.assertEqual(len([1 for p, q in self.log if p.endswith("/comments")]), before)

    def test_mention_ingest(self):
        base = routes(self.state())

        def fn(path, q):
            if path == UID and "mentioned_media" in q.get("fields", ""):
                return {"mentioned_media": {"id": "mm1", "caption": "hi @navaan", "permalink": "https://instagram.com/p/MM/", "username": "fan9", "timestamp": "2026-10-13T01:00:00+0000"}}
            return base(path, q)
        c = ig.Client(UID, TOKEN, opener=fake_opener(fn, self.log), sleep=self.sleeps.append)
        ctx = ig.Ctx(c, self.conn, UID, "music", {})
        ig.ingest_mention(ctx, media_id="mm1")
        self.assertEqual(db.one(self.conn, "SELECT kind, username FROM mentions WHERE mention_id = 'media:mm1'")["kind"], "mention_media")


class MarketTests(Base):
    def _client(self, fn):
        return ig.Client(UID, TOKEN, opener=fake_opener(fn, self.log), sleep=self.sleeps.append)

    def test_peers_are_stored_when_available(self):
        base = routes(self.state())

        def fn(path, q):
            if path == UID and "business_discovery" in q.get("fields", ""):
                return {"business_discovery": {"followers_count": 5000, "media_count": 80, "media": {"data": [
                    {"id": "p1", "caption": "new song #lofi", "media_type": "VIDEO", "media_product_type": "REELS", "permalink": "https://instagram.com/reel/P1/",
                     "timestamp": "2026-10-10T10:00:00+0000", "like_count": 300, "comments_count": 12}]}}}
            return base(path, q)
        db.upsert(self.conn, "peers", {"username": "peer_one", "added_at": "x"}, ("username",)); self.conn.commit()
        r = ig.collect(self.conn, self._client(fn), UID, "music", ("peers",), {})
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertEqual(db.one(self.conn, "SELECT followers_count FROM peers WHERE username = 'peer_one'")["followers_count"], 5000)
        self.assertEqual(db.one(self.conn, "SELECT like_count FROM peer_media WHERE media_id = 'p1'")["like_count"], 300)

    def test_peers_unavailable_is_a_state_not_a_failure(self):
        base = routes(self.state())

        def fn(path, q):
            if path == UID and "business_discovery" in q.get("fields", ""):
                raise Err(400, 10, "Application does not have permission for this action")
            return base(path, q)
        for u in ("a", "b", "c"):
            db.upsert(self.conn, "peers", {"username": u, "added_at": "x"}, ("username",))
        self.conn.commit()
        r = ig.collect(self.conn, self._client(fn), UID, "music", ("peers",), {})
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["stats"]["peers"].startswith("unavailable"))
        self.assertEqual(len([1 for p, q in self.log if "business_discovery" in q.get("fields", "")]), 2)  # stops after two failures

    def test_hashtag_quota_and_free_repeats(self):
        st = self.state(media=[media("m1")])
        st["media"][0]["caption"] = "new #a #b #c #d #e"
        for i in range(26):
            db.upsert(self.conn, "hashtag_queries", {"hashtag": f"old{i}", "hashtag_id": str(i), "queried_at": "2026-10-12T00:00:00Z"}, ("hashtag",))
        db.upsert(self.conn, "hashtag_queries", {"hashtag": "a", "hashtag_id": "ha", "queried_at": "2026-10-12T00:00:00Z"}, ("hashtag",))  # 27 used, #a is a free repeat
        self.conn.commit()
        base = routes(st)

        def fn(path, q):
            if path == "ig_hashtag_search":
                return {"data": [{"id": "h-" + q["q"]}]}
            if path.endswith("/top_media") or path.endswith("/recent_media"):
                return {"data": [{"id": path.split("/")[0] + path[-3:], "caption": "x", "like_count": 5, "comments_count": 1, "timestamp": "2026-10-12T10:00:00+0000"}]}
            return base(path, q)
        r = ig.collect(self.conn, self._client(fn), UID, "music", ("media", "hashtags"), {})
        self.assertEqual(r["status"], "ok", r["errors"])
        searched = [q["q"] for p, q in self.log if p == "ig_hashtag_search"]
        self.assertEqual(len(searched), 1)  # 27 used + 1 new = 28, the other three are deferred, #a needs no search
        self.assertEqual(r["stats"]["hashtags_deferred"], 3)
        self.assertGreater(self.count("hashtag_media"), 0)

    def test_schema_is_version_2(self):
        self.assertEqual(db.one(self.conn, "SELECT MAX(version) AS v FROM schema_version")["v"], 3)


class DashboardApiTests(Base):
    def test_overview_after_a_run(self):
        import analytics_api as api
        self.run_collect(self.state())
        self.conn.commit()
        o = api.overview("all", 30, os.path.join(self.tmp, "t.db"))
        self.assertFalse(o["empty"])
        self.assertEqual(o["kpis"]["followers"], 120)
        self.assertEqual(o["kpis"]["waiting"], 1)
        self.assertEqual(len(o["posts"]), 1)
        p = o["posts"][0]
        self.assertEqual((p["slug"], p["title"], p["language"], p["views"]), ("song-001", "Chaan", "Maithili", 400))
        self.assertEqual(p["save_rate"], 5.0)
        self.assertEqual(p["avg_watch_s"], 8.0)
        self.assertEqual(o["patterns"]["language"][0]["name"], "Maithili")
        self.assertEqual(o["waiting"][0]["username"], "fan2")
        self.assertEqual(o["audience"]["city"][0], ["Patna, Bihar", 40])
        self.assertEqual(o["runs"][0]["status"], "ok")
        self.assertEqual(api.overview("nope", 30, os.path.join(self.tmp, "t.db"))["accounts"][0]["label"], "music")

    def test_empty_states(self):
        import analytics_api as api
        self.assertEqual(api.overview("all", 30, os.path.join(self.tmp, "missing.db"))["reason"], "no_database")
        self.assertEqual(api.overview("all", 30, os.path.join(self.tmp, "t.db"))["reason"], "no_data")

    def test_collect_job_rejects_bad_account_name(self):
        import analytics_api as api
        with self.assertRaises(ValueError):
            api.start_collect("../etc")


class HelperTests(unittest.TestCase):
    def test_timestamps(self):
        self.assertEqual(ig.norm_ts("2026-10-12T14:05:00+0000"), "2026-10-12T14:05:00Z")
        self.assertEqual(ig.norm_ts("2026-10-12T14:05:00-0700"), "2026-10-12T21:05:00Z")
        self.assertIsNone(ig.norm_ts(None))

    def test_ig_ref(self):
        self.assertEqual(ig.ig_ref("https://www.instagram.com/reel/DebOMYkiYNb/"), (None, "DebOMYkiYNb"))
        self.assertEqual(ig.ig_ref("https://www.instagram.com/navaan_p5l/reel/AbC_1-x/?igsh=1"), (None, "AbC_1-x"))
        self.assertEqual(ig.ig_ref("18156611239556637"), ("18156611239556637", None))
        self.assertEqual(ig.ig_ref(""), (None, None))

    def test_bare_filename_database_path(self):
        d = tempfile.mkdtemp(); old = os.getcwd(); os.chdir(d)
        try:
            c = db.connect("plain.db"); c.close()
            self.assertTrue(os.path.exists(os.path.join(d, "plain.db")))
        finally:
            os.chdir(old)

    def test_schema_has_no_engine_specific_sql(self):
        with open(db.SCHEMA_FILE, encoding="utf-8") as f:
            sql = " ".join(db._statements(f.read())).upper()
        for bad in ("AUTOINCREMENT", "PRAGMA", "WITHOUT ROWID", "TRIGGER"):
            self.assertNotIn(bad, sql)


if __name__ == "__main__":
    unittest.main()
