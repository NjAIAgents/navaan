"""NAV-14: what the Schedule screen is told -- one row per publish step with its state (scheduled, done, missed, blocked), nothing for an unscheduled item."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import publish_schedule as PS


class Entries(unittest.TestCase):
    def test_states_of_the_two_steps(self):
        m = {"type": "music", "schedule": {"youtube_at": "2026-11-01T10:00:00Z", "instagram_at": "2026-11-01T11:00:00Z", "done": False, "missed": {"go_public": 1}, "blocked": {"publish_instagram": "waiting for approval: instagram_caption"}}}
        e = PS.entries("song-001", m, "One")
        self.assertEqual([(x["platform"], x["state"], x["at"]) for x in e], [("YouTube", "missed", "2026-11-01T10:00:00Z"), ("Instagram", "blocked", "2026-11-01T11:00:00Z")])
        self.assertEqual(e[1]["reason"], "waiting for approval: instagram_caption"); self.assertEqual((e[0]["slug"], e[0]["title"], e[0]["type"]), ("song-001", "One", "music"))

    def test_done_and_scheduled_and_unscheduled(self):
        s = {"youtube_at": "2026-11-01T10:00:00Z", "instagram_at": "2026-11-01T11:00:00Z"}
        self.assertEqual({x["state"] for x in PS.entries("a", {"type": "music", "schedule": {**s, "done": True}})}, {"done"})
        self.assertEqual({x["state"] for x in PS.entries("a", {"type": "music", "schedule": {**s, "done": False}})}, {"scheduled"})
        self.assertEqual(PS.entries("a", {"type": "music"}), [])
        self.assertEqual([x["platform"] for x in PS.entries("a", {"type": "inspiration", "schedule": {"instagram_at": "2026-11-01T11:00:00Z"}})], ["Instagram"])   # a schedule may have one platform only


if __name__ == "__main__":
    unittest.main()
