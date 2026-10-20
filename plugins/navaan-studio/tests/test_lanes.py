"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: once the videos are approved, YouTube and Instagram each have a lane of their own: neither waits for the other's approvals, and clean up waits for both.
"""
import os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import navaan as N


def step(sid, done=False, before=None, after=None): return {"id": sid, "label": sid, "kind": "script", "done": (lambda m, d=done: d), "before": before, "after": after}


class Lanes(unittest.TestCase):
    def walk(self, done=(), approved=(), media=True, posted=False, published=None, ids=("video", "youtube_meta", "publish_youtube", "youtube_short", "go_public", "instagram_caption", "publish_instagram", "archive", "cleanup")):
        """plan_lanes over a song whose steps in `done` are finished and whose gates in `approved` are approved (`ids` is the order of the steps)."""
        gates = {"video": (None, "media"), "publish_youtube": ("publish_youtube", None), "youtube_short": ("publish_short", None), "go_public": ("go_public", None), "instagram_caption": (None, "instagram_caption"),
                 "publish_instagram": ("publish_instagram", None), "archive": ("cloud_upload", None), "cleanup": ("local_cleanup", None)}
        st = [step(i, i in done, *gates.get(i, (None, None))) for i in ids]
        ap = {g: {"at": "x"} for g in approved}
        if media: ap["media"] = {"at": "x"}
        m = {"approvals": ap, "published": published or {}}
        with mock.patch.object(N, "steps", lambda slug, D: st), mock.patch.object(N, "meta", lambda s: m), mock.patch.object(N, "song_dir", lambda s: "/nowhere"), \
             mock.patch.object(N, "gate_ok", lambda D, ap_, g, published=False: g in ap_), mock.patch.object(N.PS, "when", lambda m_, sid: None), mock.patch.object(N, "ig_enabled", lambda m_: True):
            return N.plan_lanes("s")

    def status(self, rows): return {r["id"]: r["status"] for r in rows}

    def test_before_the_videos_are_approved_there_are_no_lanes_and_the_approval_is_next(self):
        rows, nxt, lanes = self.walk(done=("video",), media=False)
        self.assertEqual((nxt, lanes), ({"type": "gate", "step": "video", "gate": "media"}, {}))
        self.assertEqual(self.status(rows)["youtube_meta"], "blocked"); self.assertEqual(self.status(rows)["instagram_caption"], "blocked")   # both wait for the videos, as before

    def test_once_they_are_approved_each_lane_has_its_own_next_step_and_runnable_work_goes_first(self):
        rows, nxt, lanes = self.walk(done=("video",))
        self.assertEqual(lanes, {"youtube": {"type": "run", "step": "youtube_meta"}, "instagram": {"type": "run", "step": "instagram_caption"}})
        self.assertEqual(nxt, {"type": "run", "step": "youtube_meta"})   # a run is picked before an approval, YouTube first
        self.assertEqual({r["id"]: r.get("lane") for r in rows if r.get("lane")}, {"youtube_meta": "youtube", "publish_youtube": "youtube", "youtube_short": "youtube", "go_public": "youtube", "instagram_caption": "instagram", "publish_instagram": "instagram"})

    def test_the_lanes_do_not_wait_for_each_other(self):
        # YouTube is waiting for its upload approval; Instagram's caption can still be written and approved
        rows, nxt, lanes = self.walk(done=("video", "youtube_meta"))
        self.assertEqual(lanes["youtube"], {"type": "gate", "step": "publish_youtube", "gate": "publish_youtube"}); self.assertEqual(lanes["instagram"], {"type": "run", "step": "instagram_caption"})
        self.assertEqual(nxt, {"type": "run", "step": "instagram_caption"})   # the run goes on with Instagram instead of stopping at the YouTube approval
        self.assertEqual(self.status(rows)["instagram_caption"], "ready")
        # Instagram is waiting for the caption approval; YouTube can upload once its approval is given
        rows, nxt, lanes = self.walk(done=("video", "youtube_meta", "instagram_caption"), approved=("publish_youtube",))
        self.assertEqual(lanes["instagram"], {"type": "gate", "step": "instagram_caption", "gate": "instagram_caption"}); self.assertEqual(lanes["youtube"], {"type": "run", "step": "publish_youtube"})
        self.assertEqual(nxt, {"type": "run", "step": "publish_youtube"}); self.assertEqual(self.status(rows)["publish_youtube"], "ready")
        # both lanes are waiting for you: the run stops, and both approvals are shown
        rows, nxt, lanes = self.walk(done=("video", "youtube_meta", "instagram_caption"))
        self.assertEqual(nxt["type"], "gate"); self.assertEqual({l: n["gate"] for l, n in lanes.items()}, {"youtube": "publish_youtube", "instagram": "instagram_caption"})

    def test_the_reel_can_be_posted_before_the_youtube_video_is_public(self):
        rows, nxt, lanes = self.walk(done=("video", "youtube_meta", "instagram_caption"), approved=("instagram_caption", "publish_instagram"))
        self.assertEqual(lanes["instagram"], {"type": "run", "step": "publish_instagram"})   # YouTube has not even uploaded
        self.assertEqual(self.status(rows)["publish_instagram"], "ready")

    def test_a_finished_lane_drops_out_and_clean_up_waits_for_both(self):
        done = ("video", "youtube_meta", "publish_youtube", "youtube_short", "go_public")
        rows, nxt, lanes = self.walk(done=done, approved=("publish_youtube", "publish_short", "go_public"))
        self.assertEqual(list(lanes), ["instagram"]); self.assertEqual(nxt, {"type": "run", "step": "instagram_caption"})   # Instagram is not done, so clean up and archive are not next
        rows, nxt, lanes = self.walk(done=done + ("instagram_caption", "publish_instagram"), approved=("publish_youtube", "publish_short", "go_public", "instagram_caption", "publish_instagram"), published={"instagram": "x"})
        self.assertEqual(lanes, {}); self.assertEqual(nxt, {"type": "gate", "step": "archive", "gate": "cloud_upload"})   # both lanes finished: archive is next

    def test_a_song_goes_to_navaan_before_either_lane_and_the_lanes_wait_for_it(self):
        order = ("video", "archive", "youtube_meta", "publish_youtube", "youtube_short", "go_public", "instagram_caption", "publish_instagram", "cleanup")
        rows, nxt, lanes = self.walk(done=("video",), ids=order)
        self.assertEqual((nxt, lanes), ({"type": "gate", "step": "archive", "gate": "cloud_upload"}, {}))   # the archive approval is next, and it does not need Instagram (or YouTube) to be finished
        self.assertEqual((self.status(rows)["archive"], self.status(rows)["youtube_meta"], self.status(rows)["instagram_caption"]), ("waiting for approval", "blocked", "blocked"))
        rows, nxt, lanes = self.walk(done=("video",), approved=("cloud_upload",), ids=order)
        self.assertEqual(nxt, {"type": "run", "step": "archive"})
        rows, nxt, lanes = self.walk(done=("video", "archive"), approved=("cloud_upload",), ids=order)
        self.assertEqual(set(lanes), {"youtube", "instagram"}); self.assertEqual(nxt, {"type": "run", "step": "youtube_meta"})   # once it is there, both lanes open as before
        rows, nxt, lanes = self.walk(done=("video", "archive", "youtube_meta", "publish_youtube", "youtube_short", "go_public"), approved=("cloud_upload", "publish_youtube", "publish_short", "go_public"), ids=order)
        self.assertEqual(list(lanes), ["instagram"]); self.assertEqual(nxt, {"type": "run", "step": "instagram_caption"})   # clean up is not next: it still waits for Instagram, since it deletes what that lane needs

    def test_the_song_pipeline_archives_before_the_youtube_and_instagram_steps_and_marks_the_song_published(self):
        import tempfile
        with tempfile.TemporaryDirectory() as D: st = N.music_steps("song-001", D)
        ids = [x["id"] for x in st]
        self.assertLess(ids.index("archive"), ids.index("youtube_meta")); self.assertLess(ids.index("archive"), ids.index("instagram_caption")); self.assertEqual(ids[-1], "cleanup")
        self.assertEqual(next(x for x in st if x["id"] == "archive")["sets_after"], "published")


if __name__ == "__main__":
    unittest.main()
