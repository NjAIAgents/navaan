"""Tests for the YouTube collector. Run: python3 -W ignore -m unittest test_yt_collect (from this folder). No network: a fake opener answers.."""
import io, json, os, sys, tempfile, unittest, urllib.error, urllib.parse

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
sys.path.insert(0, SCRIPTS)
import analytics_db as db
import yt_collect as yt

CH = "UCabc123"
SECRET = "SECRET-REFRESH-TOKEN"
ANA = yt.SCOPE_ANALYTICS


class Err(Exception):
    def __init__(self, status, reason, msg):
        self.status, self.reason, self.msg = status, reason, msg


def video(vid, title, dur, views=100, likes=10, comments=2, pub="2026-10-01T10:00:00Z"):
    return {"id": vid, "snippet": {"title": title, "publishedAt": pub, "thumbnails": {"medium": {"url": f"https://i/{vid}.jpg"}}},
            "statistics": {"viewCount": str(views), "likeCount": str(likes), "commentCount": str(comments)}, "contentDetails": {"duration": dur}, "status": {"privacyStatus": "public"}}


def routes(state):
    def fn(method, url, params, headers):
        path = url.replace(yt.API + "/", "").replace(yt.ANA, "reports")
        if url == yt.TOKEN_URI:
            if state.get("bad_grant"):
                raise Err(400, None, "invalid_grant")
            return {"access_token": "ACCESS-1", "expires_in": 3600}
        if state.get("expired_once") and not state.get("_retried") and headers.get("Authorization") == "Bearer ACCESS-1":
            state["_retried"] = True
            raise Err(401, "authError", "Invalid Credentials ACCESS-1")
        if state.get("quota") and path != "channels":
            raise Err(403, "quotaExceeded", "quota")
        if path == "channels":
            return {"items": [{"id": CH, "snippet": {"title": "NAVAAN", "customUrl": "@navaan"}, "statistics": {"subscriberCount": "120", "viewCount": "5000", "videoCount": "2"},
                               "contentDetails": {"relatedPlaylists": {"uploads": "UUabc"}}}]}
        if path == "playlistItems":
            return {"items": [{"contentDetails": {"videoId": v["id"]}} for v in state["videos"]]}
        if path == "videos":
            ids = params["id"].split(",")
            return {"items": [v for v in state["videos"] if v["id"] in ids]}
        if path == "commentThreads":
            vid = params["videoId"]
            if vid in state.get("disabled", ()):
                raise Err(403, "commentsDisabled", "disabled")
            return {"items": state["threads"].get(vid, [])}
        if path == "comments":
            return {"items": state.get("more_replies", [])}
        if path == "reports":
            d = params.get("dimensions")
            if d == "day":
                return {"columnHeaders": [{"name": n} for n in ("day", "views", "estimatedMinutesWatched", "averageViewDuration", "subscribersGained", "subscribersLost", "likes", "comments", "shares")],
                        "rows": [["2026-10-11", 50, 120, 40, 2, 0, 5, 1, 1], ["2026-10-12", 70, 150, 45, 1, 1, 6, 2, 0]]}
            if d == "video":
                return {"columnHeaders": [{"name": n} for n in ("video", "views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage", "subscribersGained", "subscribersLost", "shares")],
                        "rows": [["vFull", 100, 300.5, 95, 47.5, 3, 0, 4], ["vShort", 4000, 80, 12, 85.0, 5, 1, 9], ["notmine", 1, 1, 1, 1, 0, 0, 0]]}
            if d == "insightTrafficSourceType":
                return {"columnHeaders": [{"name": n} for n in ("insightTrafficSourceType", "views", "estimatedMinutesWatched")], "rows": [["SHORTS", 300, 10], ["YT_SEARCH", 40, 20]]}
            if d == "ageGroup,gender":
                return {"columnHeaders": [{"name": n} for n in ("ageGroup", "gender", "viewerPercentage")], "rows": [["age18-24", "male", 30.0], ["age18-24", "female", 20.0], ["age25-34", "male", 50.0]]}
            if d == "country":
                return {"columnHeaders": [{"name": n} for n in ("country", "views")], "rows": [["IN", 900], ["US", 100]]}
            if d == "elapsedVideoTimeRatio":
                if state.get("no_retention"):
                    raise Err(400, "badRequest", "unsupported")
                return {"columnHeaders": [{"name": n} for n in ("elapsedVideoTimeRatio", "audienceWatchRatio", "relativeRetentionPerformance")], "rows": [[0.01, 1.0, 0.6], [0.5, 0.4, 0.5], [1.0, 0.2, 0.4]]}
        raise Err(404, "notFound", "unknown " + path)
    return fn


def fake_opener(fn, log):
    def opener(req, timeout=0):
        u = urllib.parse.urlparse(req.full_url)
        base = f"{u.scheme}://{u.netloc}{u.path}"
        params = dict(urllib.parse.parse_qsl(u.query))
        headers = {k.capitalize(): v for k, v in req.header_items()}
        log.append((base, params))
        try:
            return io.BytesIO(json.dumps(fn(req.get_method(), base, params, headers)).encode())
        except Err as e:
            body = {"error": e.reason or "invalid_grant", "error_description": "bad"} if base == yt.TOKEN_URI else {"error": {"code": e.status, "message": e.msg, "errors": [{"reason": e.reason}]}}
            raise urllib.error.HTTPError(req.full_url, e.status, "err", {}, io.BytesIO(json.dumps(body).encode()))
    return opener


def reply(cid, parent, text, ach, name):
    return {"id": cid, "snippet": {"parentId": parent, "textDisplay": text, "authorDisplayName": name, "authorChannelId": {"value": ach}, "publishedAt": "2026-10-12T10:00:00Z", "likeCount": 0}}


def thread(cid, text, ach, name, replies=None, total=None):
    top = {"id": cid, "snippet": {"textDisplay": text, "authorDisplayName": name, "authorChannelId": {"value": ach}, "publishedAt": "2026-10-11T10:00:00Z", "likeCount": 1}}
    t = {"snippet": {"topLevelComment": top, "totalReplyCount": total if total is not None else len(replies or [])}}
    if replies:
        t["replies"] = {"comments": replies}
    return t


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["NAVAAN_ROOT"] = self.tmp
        sd = os.path.join(self.tmp, "songs", "song-001")
        os.makedirs(sd)
        with open(os.path.join(sd, "meta.json"), "w") as f:
            json.dump({"slug": "song-001", "published": {"youtube_items": [{"id": "vFull"}], "youtube_short": {"id": "vShort"}}}, f)
        with open(os.path.join(sd, "tags.json"), "w") as f:
            json.dump({"title": "Chaan", "language": "Maithili", "genre": "Lo-fi"}, f)
        self.conn = db.connect(os.path.join(self.tmp, "t.db"))
        self.log, self.sleeps, self.n = [], [], 0
        self._ts = db.utcnow

        def tick():
            self.n += 1
            return f"2026-10-13T08:00:{self.n:02d}Z"
        db.utcnow = tick

    def tearDown(self):
        db.utcnow = self._ts
        os.environ.pop("NAVAAN_ROOT", None)

    def auth(self, analytics=True):
        p = os.path.join(self.tmp, "tok.json")
        json.dump({"refresh_token": SECRET, "client_id": "cid", "client_secret": "csec", "token_uri": yt.TOKEN_URI, "scopes": ["https://www.googleapis.com/auth/youtube.readonly"] + ([ANA] if analytics else [])}, open(p, "w"))
        return p

    def state(self, **kw):
        s = {"videos": [video("vFull", "Chaan full song", "PT3M20S", 100, 10, 2), video("vShort", "Chaan #Shorts", "PT45S", 4000, 300, 3, "2026-10-05T10:00:00Z")],
             "threads": {"vFull": [thread("k1", "waah", "UCfan1", "fan1", [reply("k2", "k1", "thanks", CH, "NAVAAN")]), thread("k3", "more please", "UCfan2", "fan2")], "vShort": [thread("k4", "nice", "UCfan3", "fan3")]}}
        s.update(kw)
        return s

    def client(self, state, analytics=True):
        a = yt.Auth(self.auth(analytics), opener=fake_opener(routes(state), self.log))
        return yt.Client(a, opener=fake_opener(routes(state), self.log), sleep=self.sleeps.append)

    def run_collect(self, state, only=yt.ALL_COLLECTORS, analytics=True, **opts):
        return yt.collect(self.conn, self.client(state, analytics), "music", only, opts)

    def count(self, table):
        return db.one(self.conn, f"SELECT COUNT(*) AS n FROM {table}")["n"]


class CollectTests(Base):
    def test_full_run_stores_everything(self):
        r = self.run_collect(self.state())
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertEqual(self.count("yt_channels"), 1)
        self.assertEqual(self.count("yt_videos"), 2)
        full = db.one(self.conn, "SELECT * FROM yt_snapshots WHERE video_id = 'vFull'")
        self.assertEqual((full["views"], full["likes"], full["comments"]), (100, 10, 2))
        self.assertEqual((full["avg_view_pct"], full["avg_view_s"], full["subs_gained"], full["shares"]), (47.5, 95, 3, 4))
        self.assertEqual(db.one(self.conn, "SELECT value FROM yt_daily WHERE metric = 'subscribers_count'")["value"], 120)
        self.assertEqual(db.one(self.conn, "SELECT value FROM yt_daily WHERE metric = 'views' AND period_end = '2026-10-12'")["value"], 70)
        self.assertEqual(self.count("yt_traffic"), 2)
        self.assertEqual({r["bucket"]: r["value"] for r in db.rows(self.conn, "SELECT * FROM yt_audience WHERE breakdown = 'gender'")}, {"male": 80.0, "female": 20.0})
        self.assertEqual(db.one(self.conn, "SELECT bucket FROM yt_audience WHERE breakdown = 'country' ORDER BY value DESC")["bucket"], "IN")
        self.assertEqual(db.one(self.conn, "SELECT COUNT(*) AS n FROM yt_retention WHERE video_id = 'vFull'")["n"], 3)
        self.assertEqual(self.count("yt_comments"), 4)
        self.assertEqual(db.one(self.conn, "SELECT is_own FROM yt_comments WHERE comment_id = 'k2'")["is_own"], 1)
        self.assertEqual(db.one(self.conn, f"SELECT COUNT(*) AS n FROM ({yt.WAITING_SQL.replace('COUNT(*) AS n', 'c.comment_id')})", (CH,))["n"], 2)
        self.assertEqual(db.one(self.conn, "SELECT analytics_ok FROM yt_channels")["analytics_ok"], 1)

    def test_kinds_and_links(self):
        self.run_collect(self.state())
        k = {r["video_id"]: (r["kind"], r["slug"]) for r in db.rows(self.conn, "SELECT * FROM yt_videos")}
        self.assertEqual(k, {"vFull": ("video", "song-001"), "vShort": ("short", "song-001")})
        self.assertEqual(db.one(self.conn, "SELECT title FROM songs WHERE slug = 'song-001'")["title"], "Chaan")

    def test_short_guess_without_meta(self):
        st = self.state(videos=[video("x1", "quick", "PT30S"), video("x2", "long", "PT10M")])
        self.run_collect(st, only=("videos",))
        self.assertEqual({r["video_id"]: r["kind"] for r in db.rows(self.conn, "SELECT * FROM yt_videos")}, {"x1": "short", "x2": "video"})

    def test_idempotent_and_growth_kept(self):
        st = self.state()
        self.run_collect(st)
        n = (self.count("yt_videos"), self.count("yt_comments"), self.count("yt_daily"))
        st["videos"][0]["statistics"]["viewCount"] = "150"
        self.run_collect(st)
        self.assertEqual((self.count("yt_videos"), self.count("yt_comments"), self.count("yt_daily")), n)
        self.assertEqual([r["views"] for r in db.rows(self.conn, "SELECT views FROM yt_snapshots WHERE video_id = 'vFull' ORDER BY captured_at")], [100, 150])

    def test_basic_login_skips_analytics_without_failing(self):
        r = self.run_collect(self.state(), analytics=False)
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertIn("unavailable", r["stats"]["analytics"])
        self.assertIn("unavailable", r["stats"]["retention"])
        self.assertEqual(self.count("yt_traffic"), 0)
        self.assertEqual(db.one(self.conn, "SELECT views FROM yt_snapshots WHERE video_id = 'vFull'")["views"], 100)
        self.assertEqual(db.one(self.conn, "SELECT analytics_ok FROM yt_channels")["analytics_ok"], 0)
        self.assertFalse([c for c in self.log if c[0] == yt.ANA])

    def test_refresh_failure_is_auth_failure_without_secret(self):
        r = self.run_collect(self.state(bad_grant=True))
        self.assertEqual(r["status"], "failed")
        self.assertEqual(r["errors"][0]["where"], "auth")
        self.assertIn("auth", r["errors"][0]["where"])
        self.assertNotIn(SECRET, json.dumps(r))

    def test_expired_access_token_refreshes_and_retries(self):
        r = self.run_collect(self.state(expired_once=True))
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertGreaterEqual(len([c for c in self.log if c[0] == yt.TOKEN_URI]), 2)

    def test_quota_stops_run_with_clear_note_and_no_retry(self):
        r = self.run_collect(self.state(quota=True))
        self.assertEqual(r["status"], "failed")
        self.assertEqual(r["errors"][0]["where"], "quota")
        self.assertEqual(self.sleeps, [])

    def test_comments_disabled_is_not_an_error(self):
        r = self.run_collect(self.state(disabled=("vShort",)))
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertEqual(db.one(self.conn, "SELECT COUNT(*) AS n FROM yt_comments WHERE video_id = 'vShort'")["n"], 0)

    def test_missing_retention_is_a_note_not_a_failure_of_the_run(self):
        r = self.run_collect(self.state(no_retention=True))
        self.assertEqual(r["status"], "partial")
        self.assertTrue(any("retention" in e["where"] for e in r["errors"]))
        self.assertEqual(self.count("yt_videos"), 2)

    def test_truncated_replies_are_fetched(self):
        st = self.state()
        st["threads"]["vFull"] = [thread("k1", "waah", "UCfan1", "fan1", [reply("k2", "k1", "a", "UCx", "x")], total=2)]
        st["more_replies"] = [reply("k2", "k1", "a", "UCx", "x"), reply("k9", "k1", "mine", CH, "NAVAAN")]
        self.run_collect(st, only=("comments",))
        self.assertEqual(db.one(self.conn, "SELECT is_own FROM yt_comments WHERE comment_id = 'k9'")["is_own"], 1)

    def test_deleted_video_is_marked(self):
        st = self.state()
        self.run_collect(st)
        st["videos"] = st["videos"][:1]
        self.run_collect(st)
        self.assertIsNotNone(db.one(self.conn, "SELECT deleted_at FROM yt_videos WHERE video_id = 'vShort'")["deleted_at"])
        self.assertIsNone(db.one(self.conn, "SELECT deleted_at FROM yt_videos WHERE video_id = 'vFull'")["deleted_at"])

    def test_only_comments_still_loads_videos(self):
        r = self.run_collect(self.state(), only=("comments",))
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertEqual(self.count("yt_videos"), 2)
        self.assertEqual(self.count("yt_comments"), 4)
        self.assertEqual(self.count("yt_traffic"), 0)

    def test_token_never_stored_in_database(self):
        self.run_collect(self.state())
        dump = " ".join(str(v) for t in ("yt_runs", "yt_channels", "yt_videos") for r in db.rows(self.conn, f"SELECT * FROM {t}") for v in r.values())
        self.assertNotIn(SECRET, dump)
        self.assertNotIn("ACCESS-1", dump)

    def test_helpers(self):
        self.assertEqual(yt.iso_duration_s("PT1M30S"), 90)
        self.assertEqual(yt.iso_duration_s("PT1H"), 3600)
        self.assertEqual(yt.iso_duration_s("P0D"), None)
        self.assertIsNone(yt.iso_duration_s(None))
        self.assertEqual(yt.norm_ts("2026-10-12T14:05:00.123Z"), "2026-10-12T14:05:00Z")

    def test_schema_version_and_added_column(self):
        self.assertEqual(db.one(self.conn, "SELECT MAX(version) AS v FROM schema_version")["v"], 3)
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(market_notes)").fetchall()}
        self.assertIn("platform", cols)


if __name__ == "__main__":
    unittest.main()
