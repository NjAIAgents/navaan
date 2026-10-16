"""Tests for yt_hashtags.py and the YouTube peer signal in besttime.py. Fake API client, temporary database, no network."""
import os, sys, tempfile, unittest, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import _pgenv  # noqa: F401  (must come before analytics_db)
import analytics_db as db
import yt_hashtags as H
import besttime as B

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


class Fake:
    def __init__(self, posts): self.posts, self.calls, self.log = posts, 0, []
    def data(self, path, params=None):
        self.calls += 1; self.log.append((path, params))
        if path == "search":
            return {"items": [{"id": {"videoId": p["id"]}} for p in self.posts]}
        return {"items": [{"id": p["id"], "snippet": {"channelId": p.get("ch", "UCx"), "publishedAt": p["at"]},
                           "statistics": {"viewCount": str(p["views"])}, "contentDetails": {"duration": p.get("dur", "PT30S")}} for p in self.posts]}


class T(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(os.path.join(tempfile.mkdtemp(), "a.db"))
        H.ensure(self.conn)
        self.conn.execute("INSERT INTO yt_channels (channel_id, label, created_at) VALUES ('UCme','inspiration','x')"); self.conn.commit()

    def test_duration(self):
        self.assertEqual([H.parse_duration(x) for x in ("PT45S", "PT1M5S", "PT1H", "bad", None)], [45, 65, 3600, 0, 0])

    def test_collect_filters(self):
        posts = [{"id": "a", "at": "2026-10-10T18:05:00Z", "views": 1000}, {"id": "b", "at": "2026-10-10T18:05:00Z", "views": 5, "dur": "PT10M"},
                 {"id": "c", "at": "2026-10-10T18:05:00Z", "views": 5, "ch": "UCme"}]
        f = Fake(posts)
        r = H.collect(self.conn, f, "inspiration", "UCme", ["healing"], NOW)
        self.assertEqual(r["posts"], 1)
        self.assertEqual([x["video_id"] for x in db.rows(self.conn, "SELECT video_id FROM yt_hashtag_posts")], ["a"])
        s = f.log[0][1]
        self.assertEqual((s["q"], s["videoDuration"], s["type"]), ("#healing", "short", "video")); self.assertEqual(f.calls, 2)

    def test_weekly_guard_and_tags(self):
        self.assertFalse(H.recently_collected(self.conn, "inspiration", NOW))
        db.upsert(self.conn, "yt_hashtag_posts", {"video_id": "a", "label": "inspiration", "tag": "x", "captured_at": "2026-10-18T00:00:00Z"}, ("video_id",)); self.conn.commit()
        self.assertTrue(H.recently_collected(self.conn, "inspiration", NOW))
        self.assertEqual(H.pick_tags(self.conn, "inspiration", ["#Healing", "healing", "bad tag!", "Letting_Go"]), ["healing", "letting_go"])

    def test_brand_words_skipped(self):
        self.conn.execute("UPDATE yt_channels SET title = 'The Unsaid Within', handle = '@the.unsaidwithin' WHERE label = 'inspiration'"); self.conn.commit()
        self.assertEqual(H.brand_words(self.conn, "inspiration"), {"theunsaidwithin", "inspiration"})

    def test_besttime_peer_hours(self):
        for i in range(20):
            hr = 18 if i % 2 == 0 else 6
            db.upsert(self.conn, "yt_hashtag_posts", {"video_id": f"v{i}", "label": "inspiration", "tag": "x", "channel_id": "UCo", "published_at": f"2026-10-0{1 + i % 9}T{hr:02d}:10:00Z",
                                                       "duration_s": 30, "views": 5000 if hr == 18 else 100, "captured_at": "2026-10-19T00:00:00Z"}, ("video_id",))
        self.conn.commit()
        hour, n = B._yt_peers(self.conn, "inspiration", NOW)
        self.assertEqual(n, 20); self.assertEqual(max(range(24), key=lambda i: hour[i]), 18)
        self.assertIsNone(B._yt_peers(self.conn, "music", NOW)[0])


if __name__ == "__main__":
    unittest.main()
