"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: where an item is published (the links shown as a publish stage's output), the published.json file, and the site address added to every description and caption.
"""
import json, os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import navaan_common as C

META = {"published": {"youtube_items": [{"id": "abc", "url": "https://youtu.be/abc", "privacy": "private", "file": "final_16x9.mp4"}, {"id": "sh1", "url": "https://youtube.com/shorts/sh1", "privacy": "public", "file": "final_reel_9x16.mp4"}],
                      "instagram": "https://www.instagram.com/reel/XYZ/"}}


class Links(unittest.TestCase):
    def test_each_place_it_is_published_names_the_step_that_made_it(self):
        got = C.published_links(META)
        self.assertEqual([(l["where"], l["step"]) for l in got], [("YouTube video", "publish_youtube"), ("YouTube Short", "youtube_short"), ("Instagram Reel", "publish_instagram")])
        self.assertEqual(got[0]["url"], "https://youtu.be/abc"); self.assertEqual(got[1]["privacy"], "public")
        self.assertEqual(C.published_links({}), []); self.assertEqual(C.published_links({"published": {"instagram": "17890"}})[0]["url"], "")   # an id without a link keeps no invented url
        self.assertEqual(C.published_links({"published": {"youtube_short": {"id": "q9"}}})[0]["url"], "https://youtube.com/shorts/q9")   # the older Short record

    def test_published_json_is_the_stage_s_own_file_and_is_not_written_for_nothing(self):
        d = tempfile.mkdtemp()
        with mock.patch.object(C, "item_load", lambda slug, default=None: META if slug == "s" else {}), mock.patch.object(C, "song_dir", lambda slug: d):
            p = C.write_published("s"); got = json.load(open(p))
            self.assertEqual([i["where"] for i in got["items"]], ["YouTube video", "YouTube Short", "Instagram Reel"]); self.assertTrue(all("step" not in i for i in got["items"])); self.assertTrue(got["updated_at"].endswith("Z"))
            os.remove(p); self.assertIsNone(C.write_published("none")); self.assertFalse(os.path.exists(p))


class Site(unittest.TestCase):
    def test_a_song_points_to_its_page_and_an_inspiration_to_the_site(self):
        self.assertEqual(C.with_site_link("A song about home.", "song-007"), "A song about home.\n\nHear the full song free: https://navaan.online/app/song/song-007")
        self.assertEqual(C.with_site_link("Stay soft.\n", None), "Stay soft.\n\nHear the full song free: https://navaan.online")
        self.assertEqual(C.with_site_link("", "song-007"), "Hear the full song free: https://navaan.online/app/song/song-007")
        self.assertEqual(C.with_site_link(None, None), "Hear the full song free: https://navaan.online")

    def test_instagram_gets_the_address_without_https_and_nothing_is_added_twice(self):
        self.assertEqual(C.with_site_link("Caption", "song-007", plain=True), "Caption\n\nHear the full song free: navaan.online/app/song/song-007")
        for t in ("Listen on navaan.online today", "https://navaan.online/app/song/song-007", "NAVAAN.ONLINE"): self.assertEqual(C.with_site_link(t, "song-007"), t)


if __name__ == "__main__":
    unittest.main()
