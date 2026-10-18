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
    def walk(self, done=(), approved=(), media=True, posted=False, published=None):
        """plan_lanes over a song whose steps in `done` are finished and whose gates in `approved` are approved."""
        ids = ["video", "youtube_meta", "publish_youtube", "youtube_short", "go_public", "instagram_caption", "publish_instagram", "archive", "cleanup"]
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


if __name__ == "__main__":
    unittest.main()
