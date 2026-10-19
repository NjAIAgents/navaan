"""NAV-33: visitor analytics of the public site, first-party and cookieless. Views, plays with seconds and pitch clicks are counted per song, source and
device; unique visitors per day come from a hash whose key is never stored; no address, cookie or browser string reaches the database."""
import datetime, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401

PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile/15E148 Safari/604.1"
MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 Safari/605.1.15"


class Visits(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name; self.addCleanup(os.environ.pop, "NAVAAN_ROOT", None)
        import catalog_store as K, site_visits as V
        self.K, self.V = K, V; K._LOCAL.conn = None; self.addCleanup(lambda: getattr(K._LOCAL, "conn", None) and K._LOCAL.conn.close())

    def test_the_source_comes_from_our_tag_first_then_the_referrer(self):
        S = self.V.source
        self.assertEqual(S("yt", ""), "youtube"); self.assertEqual(S("IG", "https://www.google.com/"), "instagram"); self.assertEqual(S("wa", None), "whatsapp")
        self.assertEqual(S("", "https://www.google.com/search?q=navaan"), "search"); self.assertEqual(S(None, "https://l.instagram.com/"), "instagram")
        self.assertEqual(S("", ""), "direct"); self.assertEqual(S("", "https://navaan.online/song/a", "navaan.online"), "direct"); self.assertEqual(S("nonsense", "https://blog.example/"), "other")

    def test_device_and_bots(self):
        D = self.V.device
        self.assertEqual(D(PHONE), "mobile"); self.assertEqual(D(MAC), "desktop"); self.assertEqual(D("Mozilla/5.0 (iPad; CPU OS 17_0)"), "tablet")
        for ua in ("Googlebot/2.1", "facebookexternalhit/1.1", "WhatsApp/2.23", "", None): self.assertIsNone(D(ua))   # link previews and crawlers are not visitors

    def test_a_visitor_is_the_same_on_one_day_only(self):
        d = datetime.date(2026, 10, 18)
        a = self.V.visitor("1.2.3.4", PHONE, d)
        self.assertEqual(a, self.V.visitor("1.2.3.4", PHONE, d)); self.assertNotEqual(a, self.V.visitor("1.2.3.5", PHONE, d)); self.assertEqual(len(a), 16)
        self.assertNotEqual(a, self.V.visitor("1.2.3.4", PHONE, d + datetime.timedelta(days=1)))   # a new key every day
        self.assertNotIn("1.2.3.4", a)

    def test_counts_per_song_source_and_device_and_nothing_personal_is_stored(self):
        R = self.V.record
        R("view", "song-001", "yt", "", PHONE, "1.2.3.4"); R("view", "song-001", "yt", "", PHONE, "1.2.3.4")   # one visitor, two views
        R("play", "song-001", "yt", "", PHONE, "1.2.3.4", seconds=95.6)
        R("view", None, "", "https://www.google.com/", MAC, "9.9.9.9"); R("pitch", None, "", "https://www.google.com/", MAC, "9.9.9.9")
        self.assertFalse(R("view", "song-001", "", "", "Googlebot/2.1", "6.6.6.6"))
        with self.assertRaises(ValueError): R("play", None, "", "", PHONE, "1.2.3.4")
        with self.assertRaises(ValueError): R("download", "song-001", "", "", PHONE, "1.2.3.4")
        s = self.V.summary(7); t = s["totals"]["today"]
        self.assertEqual((t["visitors"], t["views"], t["plays"], t["seconds"], t["pitch"]), (2, 3, 1, 96, 1))
        self.assertEqual([(r["slug"], r["views"], r["plays"], r["seconds"]) for r in s["songs"]], [("song-001", 2, 1, 96)])
        self.assertEqual({r["name"]: r["visitors"] for r in s["sources"]}, {"youtube": 1, "search": 1})   # ?src=yt counts under YouTube
        self.assertEqual({r["name"]: r["visitors"] for r in s["devices"]}, {"mobile": 1, "desktop": 1})
        rows = self.K._tx(lambda c: [dict(r) for r in c.execute("SELECT * FROM site_events").fetchall()])
        flat = " ".join(str(v) for r in rows for v in r.values())
        for personal in ("1.2.3.4", "9.9.9.9", "iPhone", "Macintosh", "Mozilla"): self.assertNotIn(personal, flat)
        cols = self.K._tx(lambda c: [r["column_name"] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'site_events' AND table_schema = current_schema()").fetchall()])
        self.assertEqual(sorted(cols), sorted(["id", "day", "kind", "slug", "source", "device", "visitor", "seconds", "created_at"]))


if __name__ == "__main__":
    unittest.main()
