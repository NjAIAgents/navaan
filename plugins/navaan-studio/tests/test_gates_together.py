"""Back-to-back approvals given as one: the YouTube upload also approves the Short, and the archive also allows the clean-up (which checks the bucket itself)."""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401


class Together(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = self.tmp.name
        import navaan as N, navaan_common as C
        self.N = N
        for slug, kind in (("s1", "music"), ("i1", "inspiration")):
            D = os.path.join(C.songs_root(), slug); os.makedirs(D)
            json.dump({"slug": slug, "type": kind, "state": "approved", "approvals": {}}, open(os.path.join(D, "meta.json"), "w"))

    def tearDown(self):
        os.environ.pop("NAVAAN_ROOT", None); self.tmp.cleanup()

    def test_the_youtube_upload_approves_the_short_too_and_revoking_takes_both_back(self):
        self.N.set_gate("s1", "publish_youtube", True, "ui:owner"); ap = self.N.meta("s1")["approvals"]
        self.assertIn("publish_youtube", ap); self.assertEqual(ap["publish_short"]["via"], "ui:owner (with publish_youtube)")
        self.assertIn("gate publish_short approved with publish_youtube via ui:owner", "\n".join(self.N.meta("s1")["history"]))
        self.N.set_gate("s1", "publish_youtube", False, "ui:owner"); ap = self.N.meta("s1")["approvals"]
        self.assertNotIn("publish_short", ap); self.assertNotIn("publish_youtube", ap)

    def test_the_archive_also_allows_the_clean_up(self):
        self.N.set_gate("s1", "cloud_upload", True, "ui:owner"); self.assertIn("local_cleanup", self.N.meta("s1")["approvals"])

    def test_an_inspiration_has_no_short_so_nothing_extra_is_approved(self):
        self.N.set_gate("i1", "publish_youtube", True, "ui:owner"); self.assertEqual(set(self.N.meta("i1")["approvals"]), {"publish_youtube"})

    def test_the_short_alone_does_not_approve_the_video(self):
        self.N.set_gate("s1", "publish_short", True, "ui:owner"); self.assertEqual(set(self.N.meta("s1")["approvals"]), {"publish_short"})


if __name__ == "__main__":
    unittest.main()
