"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: an inspiration short with the owner's own scene video (NAV-126): the length rules, the working copy, the steps that change, the timing and the render, and that a short without a scene is untouched.
"""
import io, json, os, shutil, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import _pgenv  # noqa: F401  (a throwaway database schema per path, for the items made below)
HAVE_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def ff(*a):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *a], check=True)


def probe(path):
    j = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:format=duration", "-of", "json", path]))
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    return v["width"], v["height"], float(j["format"]["duration"]), any(s["codec_type"] == "audio" for s in j["streams"])


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name
        self.songs = os.path.join(self.tmp.name, "songs"); self.D = os.path.join(self.songs, "insp-001"); os.makedirs(os.path.join(self.D, ".cache"))

    def scene(self, secs, name, size="640x360", audio=False):
        a = ["-f", "lavfi", "-i", f"anoisesrc=d={secs}:c=pink:a=0.05"] if audio else []
        ff("-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration={secs}", *a, "-c:v", "libx264", "-pix_fmt", "yuv420p", *(["-c:a", "aac"] if audio else []), "-shortest", name)
        return name


class Plan(unittest.TestCase):
    def test_a_small_gap_holds_the_last_frame_at_normal_speed(self):
        import inspire_scene as S
        p = S.plan(10.0, 12.5); self.assertEqual((p["stretch"], p["play"], p["hold"], p["cut"]), (1.0, 10.0, 2.5, False))
        p = S.plan(10.0, 13.0); self.assertEqual((p["stretch"], p["hold"]), (1.0, 3.0), "3 s is still a small gap")

    def test_a_big_gap_slows_the_scene_down_and_holds_the_rest(self):
        import inspire_scene as S
        p = S.plan(10.0, 20.0); self.assertEqual((p["stretch"], p["play"], p["hold"]), (1.5, 15.0, 5.0))   # slowed at most 1.5 times, then held
        p = S.plan(10.0, 14.0); self.assertEqual((p["stretch"], p["hold"]), (1.4, 0.0), "slowed just enough to fill it: no hold needed")

    def test_a_longer_scene_is_cut(self):
        import inspire_scene as S
        p = S.plan(20.0, 12.0); self.assertEqual((p["stretch"], p["hold"], p["cut"]), (1.0, 0.0, True))
        self.assertFalse(S.plan(12.0, 12.0)["cut"])

    def test_the_limits_come_from_the_profile(self):
        import inspire_scene as S
        self.assertEqual(S.plan(10.0, 20.0, small_gap=12, max_slow=2.0)["stretch"], 1.0)
        self.assertEqual(S.plan(10.0, 20.0, small_gap=1, max_slow=2.0)["stretch"], 2.0)


@unittest.skipUnless(HAVE_FF, "ffmpeg not installed")
class Fit(Env):
    def test_fit_makes_a_9x16_video_of_exactly_the_length_asked(self):
        import inspire_scene as S
        for src, total, hold, stretch in ((3, 5.0, 2.0, 1.0), (4, 9.0, 3.0, 1.5), (8, 5.0, 0.0, 1.0)):
            self.scene(src, os.path.join(self.D, "scene_src.mp4"))
            info = S.fit(self.D, total); w, h, dur, has_a = probe(os.path.join(self.D, "scene_bg.mp4"))
            self.assertEqual((w, h, has_a), (1080, 1920, False)); self.assertAlmostEqual(dur, total, delta=0.2)
            self.assertAlmostEqual(info["hold"], hold, delta=0.05); self.assertEqual(info["stretch"], stretch)

    def test_ingest_shrinks_the_upload_drops_its_sound_and_deletes_the_original(self):
        import inspire_scene as S
        raw = self.scene(6, os.path.join(self.D, ".cache", "raw.mp4"), size="1280x720", audio=True)
        for stale in ("scene_bg.mp4", "timing.json"): open(os.path.join(self.D, stale), "w").write("old")
        S.ingest(self.D)
        self.assertFalse(os.path.exists(raw), "the big original is removed once the copy is checked")
        w, h, dur, has_a = probe(os.path.join(self.D, "scene_src.mp4")); self.assertFalse(has_a, "the scene's own sound is dropped"); self.assertAlmostEqual(dur, 6.0, delta=0.6)
        self.assertFalse(os.path.exists(os.path.join(self.D, "scene_bg.mp4")) or os.path.exists(os.path.join(self.D, "timing.json")), "what was made from an older scene is stale")
        S.ingest(self.D)   # nothing waiting: the existing copy is kept

    def test_an_mpeg_file_is_accepted(self):
        import inspire_scene as S
        ff("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=3", "-c:v", "mpeg2video", "-q:v", "4", os.path.join(self.D, ".cache", "raw.mpg"))
        S.ingest(self.D); w, h, dur, has_a = probe(os.path.join(self.D, "scene_src.mp4")); self.assertAlmostEqual(dur, 3.0, delta=0.5)

    def test_ingest_without_any_video_says_so(self):
        import inspire_scene as S
        with self.assertRaises(SystemExit): S.ingest(self.D)


class Steps(Env):
    def ids(self, fn=None, **kw):
        import navaan
        return [s["id"] for s in (fn or navaan.inspiration_steps)("insp-001", self.D, **kw)]

    def test_without_a_scene_the_steps_are_exactly_what_they_were(self):
        ids = self.ids(); self.assertIn("background", ids); self.assertNotIn("scene", ids)
        self.assertEqual(ids[:3], ["quote", "originality", "background"] if "background_prompt" not in ids else ["quote", "originality", "background_prompt"])

    def test_with_a_scene_the_background_step_is_replaced(self):
        open(os.path.join(self.D, "scene_src.mp4"), "wb").write(b"x")
        ids = self.ids(); self.assertIn("scene", ids); self.assertNotIn("background", ids); self.assertNotIn("background_prompt", ids)
        self.assertLess(ids.index("originality"), ids.index("scene")); self.assertLess(ids.index("scene"), ids.index("typeset"))

    def test_an_upload_waiting_to_be_prepared_also_counts_and_a_half_upload_does_not(self):
        open(os.path.join(self.D, ".cache", "raw.part"), "wb").write(b"half"); self.assertNotIn("scene", self.ids())
        open(os.path.join(self.D, ".cache", "raw.mp4"), "wb").write(b"x"); self.assertIn("scene", self.ids())

    def test_the_aha_lorithm_never_uses_a_scene(self):
        import navaan
        open(os.path.join(self.D, "scene_src.mp4"), "wb").write(b"x")
        ids = self.ids(navaan.aha_steps); self.assertNotIn("scene", ids)

    def test_a_new_scene_makes_the_typography_and_the_render_stale(self):
        import navaan
        open(os.path.join(self.D, "scene_src.mp4"), "wb").write(b"x")
        steps = {s["id"]: s for s in navaan.inspiration_steps("insp-001", self.D)}
        self.assertTrue(steps["scene"]["done"]({}))
        for n in ("quote.json", "timing.json", "final_reel_9x16.mp4"): open(os.path.join(self.D, n), "w").write("{}")
        old = os.path.getmtime(os.path.join(self.D, "scene_src.mp4")) - 50
        for n in ("quote.json", "timing.json", "final_reel_9x16.mp4"): os.utime(os.path.join(self.D, n), (old, old))   # all made before the scene arrived
        self.assertFalse(steps["typeset"]["done"]({}), "a scene newer than timing.json: the typography is made again")
        now = old + 100; open(os.path.join(self.D, "scene_bg.mp4"), "wb").write(b"x"); os.utime(os.path.join(self.D, "scene_bg.mp4"), (now, now))
        self.assertFalse(steps["render"]["done"]({}), "a scene background newer than the video: it is rendered again")


class Upload(Env):
    def test_a_scene_replaces_an_older_one_only_when_the_caller_asks(self):
        import reel_upload as U
        open(os.path.join(self.D, "scene_src.mp4"), "wb").write(b"old")
        with self.assertRaises(U.Refused) as cm: U.save(io.BytesIO(b"abc"), 3, self.D, "a.mp4", "scene_src.mp4")
        self.assertEqual(cm.exception.code, 409)
        self.assertEqual(U.save(io.BytesIO(b"abc"), 3, self.D, "a.mp4", "no-such-file"), 3)


@unittest.skipUnless(HAVE_FF, "ffmpeg not installed")
class Short(Env):
    """A whole short: the real prep and the ffmpeg renderer over a scene video, with the quote, the end card and no generated picture."""
    def make(self):
        import new_song
        shutil.rmtree(self.D)   # setUp made an empty folder; the real item is made by new_song so its meta is in the database too
        slug = new_song.create(None, "inspiration", "")
        self.assertEqual(slug, "insp-001"); self.D = os.path.join(self.songs, slug)
        json.dump({"text": "You spend so much time waiting. You are living it now.", "lines": ["You spend so much time waiting.", "You are living it now."], "author": "", "kind": "original", "language": "en"}, open(os.path.join(self.D, "quote.json"), "w"))
        import narration; narration.set_options(self.D, {"duration": "12", "music": "none", "narrate": "none"})   # replaces the template's own option lines
        return slug

    def test_prep_and_render_use_the_scene_not_a_picture(self):
        import inspire_prep, inspire_render
        slug = self.make(); self.scene(8, os.path.join(self.D, "scene_src.mp4"), size="1280x720")   # no background.* picture exists at all
        inspire_prep.main(slug)
        T = json.load(open(os.path.join(self.D, "timing.json")))
        self.assertEqual((T["background"], T["background_video"]), ("scene_bg.mp4", True)); self.assertEqual(T["scene"]["src_seconds"], 8.0)
        w, h, dur, _ = probe(os.path.join(self.D, "scene_bg.mp4")); self.assertEqual((w, h), (1080, 1920)); self.assertAlmostEqual(dur, T["duration"], delta=0.2)
        inspire_render.main(slug, "ffmpeg")
        w, h, dur, _ = probe(os.path.join(self.D, "final_reel_9x16.mp4")); self.assertEqual((w, h), (1080, 1920)); self.assertAlmostEqual(dur, T["duration"], delta=0.3)
        self.assertTrue(os.path.exists(os.path.join(self.D, "thumb_9x16.jpg")))

    def test_without_a_scene_the_prep_still_needs_its_picture(self):
        import inspire_prep
        slug = self.make()
        with self.assertRaises(SystemExit) as cm: inspire_prep.main(slug)
        self.assertIn("no background image", str(cm.exception))

    def test_the_remotion_engine_is_given_the_video_as_its_background(self):
        import inspire_render as R
        from unittest import mock
        slug = self.make(); T = {"width": 1080, "height": 1920, "fps": 30, "duration": 12, "background": "scene_bg.mp4", "background_video": True, "voiceover": None, "narration": False,
                                 "lines": [{"text": "a", "start": 1, "end": 5}], "brand": None, "style": {"color": "#FFFFFF", "accent": "#FF4D7E", "dim": 0.4}}
        with mock.patch.object(R.subprocess, "run") as run:
            R.render_remotion(self.D, T, os.path.join(self.D, "out.mp4"))
        props = json.load(open(os.path.join(self.D, "narration_props.json")))
        self.assertIs(props["bg_is_image"], False); self.assertEqual(props["bg"], "scene_bg.mp4")
        self.assertIn("Lyrics", run.call_args[0][0], "the composition that can play a video background")
        T2 = {**T, "background": "background.png", "background_video": False, "narration": True}
        with mock.patch.object(R.subprocess, "run"): R.render_remotion(self.D, T2, os.path.join(self.D, "out.mp4"))
        self.assertIs(json.load(open(os.path.join(self.D, "narration_props.json")))["bg_is_image"], True, "a picture background is as before")


if __name__ == "__main__":
    unittest.main()
