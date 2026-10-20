"""Author: Navjyot Nishant
Created: 2026-10-20
Last updated: 2026-10-20
Description: NAV-137, the last step (cleanup) waits for Instagram only when an item is meant to go to Instagram: not an Aha-lorithm short (YouTube only), not an item whose Instagram was skipped.
"""
import contextlib, io, json, os, sys, tempfile, unittest
from unittest import mock
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import _pgenv  # noqa: F401


class Cleanup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name; self.addCleanup(lambda: os.environ.pop("NAVAAN_ROOT", None))
        json.dump({"storage": {"cloud_provider": "s3", "cloud_bucket": "b"}, "publish": {"instagram_handle": "@navaan_music"}}, open(os.path.join(self.tmp.name, "navaan.config.json"), "w"))
        import navaan_common as C
        if hasattr(C, "_CFG"): C._CFG = None

    def item(self, slug, type_, **extra):
        D = os.path.join(self.tmp.name, "songs", slug); os.makedirs(D)
        json.dump({"type": type_, "state": "published", "cloud": {"uploaded_at": "2026-10-20T10:00:00Z", "verified": True}, "published": {"youtube_items": [{"id": "x", "privacy": "public"}]}, **extra}, open(os.path.join(D, "meta.json"), "w"))

    def run_cleanup(self, slug):
        import cleanup, storage
        out = io.StringIO()
        with mock.patch.object(storage, "compare", side_effect=RuntimeError("bucket unreachable in this test")), contextlib.redirect_stdout(out): rc = cleanup.main([slug, "--yes"])
        return rc, out.getvalue()

    def test_an_aha_short_is_not_held_for_an_instagram_post_it_can_never_have(self):
        self.item("aha-001", "aha"); rc, said = self.run_cleanup("aha-001")
        self.assertNotIn("Instagram is set up", said); self.assertIn("cannot check the bucket", said, "it went on to the bucket check")

    def test_an_item_with_instagram_skipped_goes_on_too(self):
        self.item("insp-001", "inspiration", skip={"instagram": True}); rc, said = self.run_cleanup("insp-001"); self.assertNotIn("Instagram is set up", said); self.assertIn("cannot check the bucket", said)

    def test_an_item_meant_for_instagram_still_waits_for_its_post(self):
        for slug, t in (("song-001", "music"), ("insp-002", "inspiration"), ("reel-001", "reel")):
            self.item(slug, t); rc, said = self.run_cleanup(slug); self.assertEqual(rc, 4, t); self.assertIn("Instagram is set up but the Reel is not posted yet", said, t)
        self.item("song-002", "music", published={"youtube_items": [{"id": "x", "privacy": "public"}], "instagram": {"id": "1"}}); rc, said = self.run_cleanup("song-002"); self.assertNotIn("Instagram is set up", said)


if __name__ == "__main__":
    unittest.main()
