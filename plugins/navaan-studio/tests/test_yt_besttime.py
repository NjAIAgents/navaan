"""Tests for the YouTube best time to publish. Run: python3 -W ignore -m unittest test_yt_besttime"""
import os, sys, unittest, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_yt_reco import Base, CH, NOW, NOWDT, ts, day
import besttime as bt


class BestTime(Base):
    def vid(self, age, hour, views, kind="video", pct=45.0, subs=3, privacy="public"):
        self.n += 1
        v = f"b{self.n}"
        self.conn.execute("INSERT INTO yt_videos (video_id, channel_id, kind, title, published_at, duration_s, privacy, first_seen_at, last_seen_at) VALUES (?,?,?,?,?,?,?,?,?)",
                          (v, CH, kind, "t", ts(age, hour), 200, privacy, NOW, NOW))
        self.conn.execute("INSERT INTO yt_snapshots (video_id, captured_at, views, likes, comments, minutes_watched, avg_view_s, avg_view_pct, subs_gained, subs_lost, shares) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (v, NOW, views, 5, 1, 30.0, 60.0, pct, subs, 0, 0))
        self.conn.commit()

    def country(self, **c):
        for k, v in c.items():
            self.conn.execute("INSERT INTO yt_audience (channel_id, captured_on, breakdown, bucket, value) VALUES (?,?,?,?,?)", (CH, "2026-10-13", "country", k, v))
        self.conn.commit()

    def traffic(self, **t):
        for k, v in t.items():
            self.conn.execute("INSERT INTO yt_traffic (channel_id, captured_on, source, views, minutes) VALUES (?,?,?,?,?)", (CH, "2026-10-13", k, v, 1.0))
        self.conn.commit()

    def run_bt(self):
        return bt.analyze_youtube(self.conn, "music", NOWDT)

    def test_unknown_channel(self):
        self.assertTrue(bt.analyze_youtube(self.conn, "nope", NOWDT)["empty"])

    def test_no_signal(self):
        r = self.run_bt()
        self.assertTrue(r["empty"])
        self.assertEqual(r["reason"], "no_signal")

    def test_countries_alone_peak_in_local_evening(self):
        self.country(IN=90, US=10)
        r = self.run_bt()
        k = r["kinds"]["video"]
        self.assertFalse(k["empty"])
        self.assertEqual(k["confidence"], "low")
        self.assertEqual(r["countries"][0], ("IN", 90))
        # India 20 to 21 local is 14:30 to 15:30 UTC, posting one hour earlier
        best = max(range(24), key=lambda i: k["hours"][i])
        self.assertIn(best, (13, 14))
        self.assertEqual(max(k["hours"]), 100)
        self.assertEqual(k["basis"]["signals"], ["viewer countries (evening listening assumed)"])

    def test_shorts_post_at_the_peak_not_before(self):
        self.country(IN=100)
        r = self.run_bt()
        hv, hs = r["kinds"]["video"]["hours"], r["kinds"]["short"]["hours"]
        self.assertEqual(max(range(24), key=lambda i: hs[i]), (max(range(24), key=lambda i: hv[i]) + 1) % 24)
        self.assertEqual(r["kinds"]["short"]["basis"]["lead_hours"], 0)

    def test_own_videos_pull_toward_their_hour(self):
        self.country(IN=100)
        for a in (10, 14, 18, 22, 26, 30, 34, 38):
            self.vid(a, 16, 5000)          # good ones at 16 UTC
        for a in (11, 15, 19, 23, 27, 31, 35, 39):
            self.vid(a, 3, 200)            # weak ones at 3 UTC
        r = self.run_bt()
        k = r["kinds"]["video"]
        self.assertEqual(k["basis"]["own_videos"], 16)
        self.assertEqual(k["confidence"], "high" if len(k["basis"]["signals"]) >= 2 else "medium")
        self.assertGreater(k["hours"][15], k["hours"][2])   # posting hour is one before the 16 UTC viewing hour
        self.assertEqual(max(range(24), key=lambda i: k["hours"][i]) in (14, 15), True)
        self.assertEqual(r["kinds"]["short"]["basis"]["own_videos"], 0)   # no shorts, short falls back to countries

    def test_too_few_or_too_young_videos_do_not_count(self):
        self.country(IN=100)
        for a in range(1, 7):
            self.vid(a, 5, 9000)           # younger than a week
        self.vid(20, 5, 9000, privacy="private")
        r = self.run_bt()
        self.assertEqual(r["kinds"]["video"]["basis"]["own_videos"], 0)
        self.assertTrue(any("needed" in n for n in r["kinds"]["video"]["notes"]))

    def test_instagram_online_hours_join_in(self):
        self.country(IN=100)
        self.conn.execute("INSERT INTO accounts (ig_user_id, label, username, created_at) VALUES ('1','music','navaan_p5l',?)", (NOW,))
        for h in range(24):
            self.conn.execute("INSERT INTO online_hours (ig_user_id, captured_on, hour, followers) VALUES ('1', ?, ?, ?)", (day(0), h, 500 if h == 2 else 5))
        self.conn.commit()
        k = self.run_bt()["kinds"]["video"]
        self.assertIn("Instagram followers online", k["basis"]["signals"])
        self.assertGreater(k["hours"][1], 40)   # pulled toward 02 UTC (post hour 01)

    def test_traffic_sensitivity_notes(self):
        self.country(IN=100)
        self.traffic(YT_SEARCH=95, SUBSCRIBER=5)
        r = self.run_bt()
        self.assertEqual(r["traffic"]["sensitivity"], "low")
        self.assertTrue(any("matters less" in n for n in r["kinds"]["video"]["notes"]))
        self.conn.execute("DELETE FROM yt_traffic"); self.conn.commit()
        self.traffic(SUBSCRIBER=30, NOTIFICATION=10, SHORTS=60)
        r = self.run_bt()
        self.assertEqual(r["traffic"]["sensitivity"], "high")
        self.assertTrue(any("Shorts feed" in n for n in r["kinds"]["short"]["notes"]))

    def test_slots_future_spaced_and_capped(self):
        self.country(IN=100)
        k = self.run_bt()["kinds"]["video"]
        s = k["slots"]
        self.assertTrue(1 <= len(s) <= 5)
        ts_ = [bt._ts(x["at"]) for x in s]
        for t in ts_:
            self.assertGreaterEqual((t - NOWDT).total_seconds(), bt.LEAD_MIN * 60)
        for d in {t.date() for t in ts_}:
            self.assertLessEqual(sum(1 for t in ts_ if t.date() == d), 2)
        self.assertEqual(s[0]["score"], 100)

    def test_for_label_youtube_reads_db_file(self):
        self.country(IN=100)
        self.conn.commit()
        r = bt.for_label_youtube("music", self.path)
        self.assertFalse(r["empty"])
        self.assertTrue(bt.for_label_youtube("music", os.path.join(self.tmp.name, "missing.db"))["empty"])


if __name__ == "__main__":
    unittest.main()
