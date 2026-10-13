"""Tests for the schedule suggestion built from the analytics timing. Run: python3 -W ignore -m unittest test_schedule_suggest"""
import datetime, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
H = datetime.timedelta


class Suggest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["NAVAAN_ROOT"] = self.tmp.name
        import navaan_common as C, navaan as N, publish_schedule as PS, besttime as B
        self.C, self.N, self.PS, self.B = C, N, PS, B
        self.slug = "s1"
        self.meta({"slug": "s1", "type": "music"})
        self._f = (B.for_label, B.for_label_youtube)
        self.ig = {"empty": False, "slots": [], "basis": {"signals": ["followers online"]}}
        self.yt = {"empty": False, "kinds": {"video": {"empty": False, "confidence": "high", "slots": [], "basis": {"signals": ["your own videos"]}}}}
        B.for_label = lambda label, db=None: self.ig
        B.for_label_youtube = lambda label, db=None: self.yt

    def tearDown(self):
        self.B.for_label, self.B.for_label_youtube = self._f
        self.tmp.cleanup()

    def meta(self, m):
        d = os.path.join(self.C.songs_root(), self.slug); os.makedirs(d, exist_ok=True)
        json.dump(m, open(os.path.join(d, "meta.json"), "w"))

    def slots(self, ig=(), yt=()):
        self.ig["slots"] = [{"at": iso(t), "score": s} for t, s in ig]
        self.yt["kinds"]["video"]["slots"] = [{"at": iso(t), "score": s} for t, s in yt]

    def test_youtube_best_slot_then_reel_slot_after_it(self):
        y1, y2 = NOW + H(hours=20), NOW + H(hours=44)
        self.slots(yt=[(y1, 80), (y2, 100)], ig=[(y2 - H(hours=2), 100), (y2 + H(hours=3), 90), (y2 + H(hours=30), 100)])
        s = self.PS.suggest(self.slug, NOW)
        self.assertEqual(s["youtube_at"], iso(y2))
        self.assertEqual(s["instagram_at"], iso(y2 + H(hours=3)))   # before the video and 30 h later are both out of range
        self.assertEqual(s["confidence"], "high")

    def test_reel_defaults_to_an_hour_after_when_no_instagram_slot_fits(self):
        y = NOW + H(hours=20)
        self.slots(yt=[(y, 100)], ig=[(y - H(hours=3), 100)])
        s = self.PS.suggest(self.slug, NOW)
        self.assertEqual(s["instagram_at"], iso(y + H(minutes=60)))

    def test_without_youtube_data_only_the_reel_time_and_auto(self):
        self.yt["kinds"]["video"] = {"empty": True}
        self.slots(ig=[(NOW + H(hours=5), 70), (NOW + H(hours=30), 100)])
        s = self.PS.suggest(self.slug, NOW)
        self.assertIsNone(s["youtube_at"])
        self.assertEqual(s["instagram_at"], iso(NOW + H(hours=30)))
        self.assertTrue(s["note"])

    def test_no_data_or_already_posted_gives_none(self):
        self.ig, self.yt = {"empty": True}, {"empty": True}
        self.assertIsNone(self.PS.suggest(self.slug, NOW))
        self.ig = {"empty": False, "slots": [{"at": iso(NOW + H(hours=5)), "score": 70}], "basis": {"signals": []}}
        self.meta({"slug": "s1", "type": "music", "published": {"instagram": "https://i/x"}})
        self.assertIsNone(self.PS.suggest(self.slug, NOW))

    def test_slots_in_the_past_are_skipped(self):
        self.slots(yt=[(NOW + H(minutes=1), 100), (NOW + H(hours=30), 60)])
        self.assertEqual(self.PS.suggest(self.slug, NOW)["youtube_at"], iso(NOW + H(hours=30)))

    def test_already_public_suggests_only_the_reel(self):
        self.meta({"slug": "s1", "type": "music", "published": {"youtube_items": [{"id": "a", "url": "u", "privacy": "public"}]}})
        self.slots(ig=[(NOW + H(hours=6), 90)], yt=[(NOW + H(hours=3), 100)])
        s = self.PS.suggest(self.slug, NOW)
        self.assertIsNone(s["youtube_at"]); self.assertEqual(s["instagram_at"], iso(NOW + H(hours=6)))

    def test_accept_saves_a_schedule_and_never_approves(self):
        n = self.PS.now()
        y = n + H(hours=20)
        self.slots(yt=[(y, 100)], ig=[(y + H(hours=2), 100)])
        s = self.PS.accept(self.slug)
        self.assertEqual(s["youtube_at"], iso(y)); self.assertEqual(s["instagram_at"], iso(y + H(hours=2)))
        m = self.N.meta(self.slug)
        self.assertFalse(m.get("approvals"))
        self.slots()
        self.PS.clear(self.slug)
        with self.assertRaises(ValueError): self.PS.accept(self.slug)


if __name__ == "__main__":
    unittest.main()
