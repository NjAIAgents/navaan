"""Author: Navjyot Nishant
Created: 2026-10-23
Last updated: 2026-10-23
Description: the video QA of an inspiration or Aha-lorithm short (NAV-147): the free checks, the verdict, the steps' place before the media approval, and that the approval is never made for the owner while the QA has not passed.

The caption sync check is tested on the two real narrations that drifted (tests/fixtures/narration): the times the published videos used fail it, the recognised times pass.
"""
import json, os, shutil, subprocess, sys, tempfile, time, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import inspire_qa as Q

FIX = os.path.join(HERE, "fixtures", "narration")
TRUTH = json.load(open(os.path.join(FIX, "truth.json"), encoding="utf-8"))
HEARD = json.load(open(os.path.join(FIX, "vosk_heard.json"), encoding="utf-8"))
FF = shutil.which("ffmpeg")


def ff(*args): subprocess.run([FF, "-y", "-v", "error", *args], check=True)


class Sync(unittest.TestCase):
    def lines(self, name, starts, at=None):
        L = TRUTH[name]["lines"]; return [{"text": t, "start": round(s - 0.1, 2), **({"at": a} if at else {})} for t, s, a in zip(L, starts, at or [None] * len(L))]

    def test_the_times_the_published_videos_used_fail_and_the_recognised_times_pass(self):
        for name, key in (("insp-008", "008"), ("insp-009", "009")):
            old = Q.sync_drift(self.lines(name, TRUTH[name]["used_by_the_video_at"]), HEARD[key])
            self.assertGreater(max(old), 1.5, name)
            self.assertFalse(Q.sync_check(old, TRUTH[name]["lines"])["ok"])
            import word_align as W
            res = W.match(TRUTH[name]["lines"], HEARD[key])
            good = Q.sync_drift(self.lines(name, [l["start"] for l in res["lines"]], at=[l["at"] for l in res["lines"]]), HEARD[key])
            self.assertLess(max(good), 0.1, name); self.assertTrue(Q.sync_check(good, TRUTH[name]["lines"])["ok"])

    def test_the_worst_line_is_named_and_a_check_that_cannot_run_is_skipped_not_failed(self):
        c = Q.sync_check([0.1, 1.9, 0.2], ["one", "two words", "three"]); self.assertFalse(c["ok"]); self.assertIn("line 2", c["note"]); self.assertIn("1.9 s", c["note"])
        c = Q.sync_check(None, []); self.assertIsNone(c["ok"]); self.assertIn("not checked", c["note"])
        self.assertIsNone(Q.sync_drift([{"text": "completely different words", "start": 0}], [{"word": "nothing", "start": 0, "end": 1}]), "too few words heard right")


@unittest.skipUnless(FF, "ffmpeg not installed")
class Detectors(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)

    def video(self, name, black):
        p = os.path.join(self.tmp.name, name)
        ff("-f", "lavfi", "-i", "testsrc=d=2:s=180x320:r=10", "-f", "lavfi", "-i", "color=c=black:d=%s:s=180x320:r=10" % black, "-f", "lavfi", "-i", "testsrc=d=2:s=180x320:r=10",
           "-filter_complex", "concat=n=3:v=1:a=0", "-pix_fmt", "yuv420p", p); return p

    def test_a_long_black_stretch_in_the_middle_fails_and_a_dip_between_pictures_does_not(self):
        p = self.video("long.mp4", 2); s = Q.black_stretches(p, 6); c = Q.black_check(s, 6)
        self.assertFalse(c["ok"]); self.assertAlmostEqual(c["at"], 2.0, delta=0.3)
        p = self.video("dip.mp4", 0.6); s = Q.black_stretches(p, 4.6); self.assertTrue(s, "the dip is seen"); self.assertTrue(Q.black_check(s, 4.6)["ok"])
        self.assertTrue(Q.black_check([(0.0, 1.0)], 10)["ok"], "the fade in"); self.assertTrue(Q.black_check([(9.2, 10.0)], 10)["ok"], "the fade out")

    def test_clipping_and_a_nearly_silent_sound_fail_and_a_normal_level_passes(self):
        for vol, ok in (("2", True), ("8", False), ("0.02", False)):
            p = os.path.join(self.tmp.name, "s%s.mp4" % vol)
            ff("-f", "lavfi", "-i", "testsrc=d=2:s=180x320:r=10", "-f", "lavfi", "-i", "sine=frequency=440:d=2", "-af", "volume=%s" % vol, "-pix_fmt", "yuv420p", "-shortest", p)
            self.assertEqual(Q.sound_check(Q.sound(p))["ok"], ok, "volume %s: %s" % (vol, Q.sound(p)))
        p = os.path.join(self.tmp.name, "mute.mp4"); ff("-f", "lavfi", "-i", "testsrc=d=1:s=180x320:r=10", "-pix_fmt", "yuv420p", p)
        self.assertIsNone(Q.sound(p)); self.assertFalse(Q.sound_check(None)["ok"])


@unittest.skipUnless(FF, "ffmpeg not installed")
class Run(unittest.TestCase):
    """A whole short in a folder: the verdict, the files written, and the Claude look only when the free checks pass."""
    L = ["Maybe you are not behind", "Maybe you are just becoming"]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        os.environ["NAVAAN_ROOT"] = self.tmp.name; self.addCleanup(os.environ.pop, "NAVAAN_ROOT", None)
        self.D = os.path.join(self.tmp.name, "songs", "insp-001"); os.makedirs(self.D)
        ff("-f", "lavfi", "-i", "testsrc2=d=12:s=1080x1920:r=5", "-f", "lavfi", "-i", "sine=frequency=330:d=12", "-af", "volume=2", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "40", "-shortest",
           os.path.join(self.D, Q.FINAL))
        self.timing([1.0, 6.0])

    def timing(self, starts):
        T = {"duration": 12, "narration": True, "lines": [{"text": t, "start": round(s - 0.1, 2), "end": s + 4, "at": [s + 0.4 * i for i in range(len(t.split()))]} for t, s in zip(self.L, starts)]}
        json.dump(T, open(os.path.join(self.D, "timing.json"), "w"))

    def heard(self, starts):
        return lambda path: [{"word": w, "start": s + 0.4 * i, "end": s + 0.4 * i + 0.3} for t, s in zip(self.L, starts) for i, w in enumerate(t.split())]

    def test_a_short_whose_words_are_lit_when_they_are_spoken_passes(self):
        res = Q.run(self.D, FF, recognise=self.heard([1.0, 6.0]))
        self.assertEqual(res["verdict"], "pass", res["checks"]); self.assertEqual([c["ok"] for c in res["checks"]], [True, True, True, True])

    def test_a_short_whose_captions_are_early_fails_and_says_which_line(self):
        res = Q.run(self.D, FF, recognise=self.heard([1.0, 8.5]))   # spoken at 8.5, lit at 6.0
        self.assertEqual(res["verdict"], "fix"); bad = [c for c in res["checks"] if c["ok"] is False]
        self.assertEqual([c["name"] for c in bad], ["caption sync"]); self.assertIn("line 2", bad[0]["note"])

    def test_without_the_word_timing_tools_the_sync_is_skipped_and_the_rest_still_decides(self):
        def none(path): raise RuntimeError("the word timing tools are not installed")
        res = Q.run(self.D, FF, recognise=none)
        self.assertEqual(res["verdict"], "pass"); sync = [c for c in res["checks"] if c["name"] == "caption sync"][0]
        self.assertIsNone(sync["ok"]); self.assertIn("not installed", sync["note"])

    def test_a_missing_video_fails_without_crashing(self):
        os.remove(os.path.join(self.D, Q.FINAL)); res = Q.run(self.D, FF)
        self.assertEqual(res["verdict"], "fix"); self.assertIn("missing", res["checks"][0]["note"])

    def test_main_writes_the_checks_and_on_a_fail_the_verdict_for_the_owner_and_clears_it_when_fixed(self):
        import unittest.mock as mock
        with mock.patch.object(Q, "_recognise", self.heard([1.0, 8.5])), mock.patch("builtins.print"): Q.main("insp-001")
        qa = json.load(open(os.path.join(self.D, "qa.json"))); self.assertEqual((qa["verdict"], qa["source"]), ("fix", "checks")); self.assertTrue(qa["fixes"]); self.assertIn("insp-001", qa["notify"])
        self.assertTrue(os.path.exists(os.path.join(self.D, "qa_checks.json")))
        with mock.patch.object(Q, "_recognise", self.heard([1.0, 6.0])), mock.patch("builtins.print"): Q.main("insp-001")
        self.assertFalse(os.path.exists(os.path.join(self.D, "qa.json")), "an old failure from these checks goes, so the Claude look runs")
        json.dump({"verdict": "pass", "source": "look"}, open(os.path.join(self.D, "qa.json"), "w"))
        with mock.patch.object(Q, "_recognise", self.heard([1.0, 6.0])), mock.patch("builtins.print"): Q.main("insp-001")
        self.assertTrue(os.path.exists(os.path.join(self.D, "qa.json")), "Claude's own verdict is never deleted by the checks")


class Wiring(unittest.TestCase):
    def setUp(self):
        import _pgenv  # noqa: F401  (a throwaway database schema per path)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        os.environ["NAVAAN_ROOT"] = self.tmp.name; os.environ["NAVAAN_CONF_DIR"] = os.path.join(self.tmp.name, "conf")
        self.addCleanup(os.environ.pop, "NAVAAN_ROOT", None); self.addCleanup(os.environ.pop, "NAVAAN_CONF_DIR", None)

    def ids(self, fn):
        import navaan
        D = os.path.join(self.tmp.name, "x"); os.makedirs(D, exist_ok=True)
        return [(s["id"], s.get("after"), s["kind"]) for s in fn("insp-001", D)]

    def test_the_qa_comes_right_after_the_render_and_the_media_approval_comes_after_it_for_both_channels(self):
        import navaan
        for fn in (navaan.inspiration_steps, navaan.aha_steps):
            ids = [i for i, _, _ in self.ids(fn)]; r = ids.index("render")
            self.assertEqual(ids[r:r + 3], ["render", "qa_checks", "qa"], fn.__name__)
            self.assertEqual([i for i, a, _ in self.ids(fn) if a == "media"], ["qa"], "the media approval follows the QA, not the render")
        kinds = {i: k for i, _, k in self.ids(navaan.inspiration_steps)}; self.assertEqual((kinds["qa_checks"], kinds["qa"]), ("script", "claude"))
        self.assertTrue(os.path.isfile(os.path.join(HERE, "..", "skills", "inspiration-qa", "SKILL.md")))

    def test_a_reel_keeps_its_own_critique(self):
        import navaan
        self.assertEqual([i for i, a, _ in self.ids(navaan.reel_steps) if a == "media"], ["critique"])

    def test_the_media_approval_is_never_made_for_the_owner_unless_the_qa_passed(self):
        import gate_cfg as G, navaan as N, navaan_common as C
        D = os.path.join(C.songs_root(), "insp-001"); os.makedirs(D)
        json.dump({"slug": "insp-001", "type": "inspiration", "state": "rendered", "approvals": {}}, open(os.path.join(D, "meta.json"), "w"))
        open(os.path.join(D, "final_reel_9x16.mp4"), "w").write("v"); time.sleep(0.02)
        G.save({"media": False})
        self.assertEqual(N.auto_gates("insp-001"), [], "no QA yet")
        qa = lambda v: json.dump({"verdict": v, "source": "look"}, open(os.path.join(D, "qa.json"), "w"))
        qa("fix"); self.assertEqual(N.auto_gates("insp-001"), [], "QA says fix")
        qa("pass"); os.utime(os.path.join(D, "final_reel_9x16.mp4"), (time.time() + 5, time.time() + 5)); self.assertEqual(N.auto_gates("insp-001"), [], "the video was rendered again after the QA")
        os.utime(os.path.join(D, "final_reel_9x16.mp4"), None); os.utime(os.path.join(D, "qa.json"), (time.time() + 5, time.time() + 5)); self.assertEqual(N.auto_gates("insp-001"), ["media"])

    def test_other_content_types_are_not_held_by_the_qa(self):
        import gate_cfg as G, navaan as N, navaan_common as C
        D = os.path.join(C.songs_root(), "reel-001"); os.makedirs(D)
        json.dump({"slug": "reel-001", "type": "reel", "state": "rendered", "approvals": {}}, open(os.path.join(D, "meta.json"), "w"))
        G.save({"media": False}); self.assertEqual(N.auto_gates("reel-001"), ["media"])


if __name__ == "__main__":
    unittest.main()
