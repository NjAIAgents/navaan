"""A scheduled step fires once: not again after it succeeded, retried only after the back-off, and never past MAX_TRIES.
Run: python3 -W ignore -m unittest test_scheduler_once"""
import datetime, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
H = datetime.timedelta
iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")


class Once(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["NAVAAN_ROOT"] = self.tmp.name
        import navaan_common as C, navaan as N, publish_schedule as PS
        self.C, self.N, self.PS = C, N, PS
        self.slug = "s1"; self.D = os.path.join(C.songs_root(), self.slug); os.makedirs(self.D)
        open(os.path.join(self.D, "instagram.txt"), "w").write("caption")
        sha = N.file_sha(self.D, "instagram.txt")
        self.save({"slug": "s1", "type": "music",
                   "published": {"youtube_items": [{"id": "v", "privacy": "public"}]},   # YouTube already public, only Instagram is left
                   "approvals": {"publish_instagram": {"at": "x"}, "instagram_caption": {"at": "x", "sha": sha}},
                   "schedule": {"instagram_at": iso(NOW - H(minutes=5))}})
        self.calls = []

    def tearDown(self): self.tmp.cleanup()

    def save(self, m): json.dump(m, open(os.path.join(self.D, "meta.json"), "w"))
    def meta(self): return json.load(open(os.path.join(self.D, "meta.json")))

    def ok(self, slug, sid):  # a real publish records the post in meta
        self.calls.append(sid); m = self.meta(); m["published"]["instagram"] = {"id": "ig1"}; self.save(m); return 0

    def bad(self, slug, sid): self.calls.append(sid); return 1

    def test_fires_once_then_never_again(self):
        self.PS.tick(self.ok, at=NOW)
        self.PS.tick(self.ok, at=NOW + H(minutes=1))
        self.PS.tick(self.ok, at=NOW + H(days=1))
        self.assertEqual(self.calls, ["publish_instagram"])
        self.assertTrue(self.meta()["schedule"]["done"])

    def test_failed_step_waits_for_backoff_and_stops_at_max_tries(self):
        for i in range(20): self.PS.tick(self.bad, at=NOW + H(minutes=i * self.PS.BACKOFF_MIN))
        self.assertEqual(len(self.calls), self.PS.MAX_TRIES)

    def test_no_second_attempt_inside_backoff(self):
        self.PS.tick(self.bad, at=NOW); self.PS.tick(self.bad, at=NOW + H(minutes=1))
        self.assertEqual(len(self.calls), 1)

    def test_unapproved_step_never_fires(self):
        m = self.meta(); m["approvals"].pop("publish_instagram"); self.save(m)
        self.PS.tick(self.ok, at=NOW)
        self.assertEqual(self.calls, [])
        self.assertIn("waiting for approval", self.meta()["schedule"]["blocked"]["publish_instagram"])

    def test_too_late_is_missed_not_fired(self):
        self.PS.tick(self.ok, at=NOW + H(hours=self.PS.GRACE_H + 1))
        self.assertEqual(self.calls, [])
        self.assertTrue(self.meta()["schedule"]["missed"]["publish_instagram"])


if __name__ == "__main__":
    unittest.main()
