"""NAV-67: The Aha-lorithm, a YouTube-Shorts-only channel built on the inspiration pipeline: no Instagram, its own account, its own look."""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401


class Aha(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = self.tmp.name
        tok = os.path.join(self.tmp.name, "yt_aha.json"); open(tok, "w").write("{}")
        json.dump({"accounts": {"aha": {"instagram_handle": "", "youtube_channel": "@TheAhalorithm", "youtube_token": tok}}}, open(os.path.join(self.tmp.name, "navaan.config.json"), "w"))
        import navaan_common as C, navaan as N, inspire_prep as P
        self.C, self.N, self.P = C, N, P
        if hasattr(C, "_CFG"): C._CFG = None
        self.D = os.path.join(C.songs_root(), "aha-001"); os.makedirs(self.D)
        json.dump({"slug": "aha-001", "type": "aha", "state": "draft", "approvals": {}}, open(os.path.join(self.D, "meta.json"), "w"))

    def tearDown(self):
        os.environ.pop("NAVAAN_ROOT", None); self.tmp.cleanup()

    def test_its_gates_and_steps_have_no_instagram_and_the_writers_know_the_channel(self):
        self.assertNotIn("instagram_caption", self.C.type_gates("aha")); self.assertNotIn("publish_instagram", self.C.type_gates("aha"))
        ids = [s["id"] for s in self.N.steps("aha-001", self.D)]
        self.assertIn("publish_youtube", ids); self.assertIn("go_public", ids)
        self.assertNotIn("instagram_caption", ids); self.assertNotIn("publish_instagram", ids)
        meta_step = next(s for s in self.N.steps("aha-001", self.D) if s["id"] == "youtube_meta"); self.assertIn("The Aha-lorithm", meta_step["hint"]); self.assertIn("AI awareness", meta_step["hint"])
        self.assertFalse(self.N.ig_enabled({"type": "aha"})); self.assertTrue(self.C.is_short("aha")); self.assertEqual(self.C.TYPE_PREFIX["aha"], "aha")

    def test_a_youtube_login_alone_makes_its_account_ready(self):
        a = self.C.account("aha"); self.assertTrue(a["configured"]); self.assertEqual(a["youtube_channel"], "@TheAhalorithm")

    def test_without_its_account_it_still_ends_on_its_own_handle_never_navaan(self):
        json.dump({"accounts": {}}, open(os.path.join(self.tmp.name, "navaan.config.json"), "w"))
        if hasattr(self.C, "_CFG"): self.C._CFG = None
        self.assertEqual(self.P.handle("aha"), "TheAhalorithm"); self.assertEqual(self.P.watermark("aha-001"), "@TheAhalorithm"); self.assertEqual(self.P.brand_name("aha-001"), "TheAhalorithm")
        self.assertEqual(self.P.handle("inspiration"), "")   # an inspiration item without its account: no NAVAAN mark either (watermark is empty, checked on music below)

    def test_its_look_and_mark_are_its_own(self):
        self.assertEqual(self.P.handle("aha"), "TheAhalorithm"); self.assertEqual(self.P.watermark("aha-001"), "@TheAhalorithm")
        self.assertEqual(self.P.LOOKS["aha"]["font"], "sans"); self.assertNotEqual(self.P.LOOKS["aha"]["accent"], self.P.LOOKS["inspiration"]["accent"])

    def script(self, n=3):
        json.dump({"text": "x", "lines": [f"Beat {i} is spoken in full here." for i in range(n)], "captions": [f"Beat {i} *key*" for i in range(n)], "aha": n - 1,
                   "pictures": [f"a cinematic picture number {i} of a glowing brain" for i in range(n)]},
                  open(os.path.join(self.D, "quote.json"), "w"))

    def test_it_is_a_scene_short_with_its_own_script_check_and_pictures(self):
        st = {s["id"]: s for s in self.N.steps("aha-001", self.D)}
        self.assertEqual(st["quote"]["skill"], "aha-script"); self.assertEqual(st["originality"]["skill"], "aha-check")
        self.assertNotIn("background_prompt", st); self.assertEqual(st["background"]["before"], "credits"); self.assertIn("aha_pictures.py", " ".join(st["background"]["cmds"][0]))
        self.assertIn("narrate", st)   # ElevenLabs reads the script

    def test_pictures_one_per_beat_resume_without_paying_twice(self):
        import aha_pictures as A, image_openai as I, media_cfg
        from PIL import Image; import io
        self.script(3); os.makedirs(os.path.join(self.D, "scenes"))
        Image.new("RGB", (8, 8)).save(A.beat_file(self.D, 0))   # beat 1 was made before a failure
        buf = io.BytesIO(); Image.new("RGB", (1152, 2048), "teal").save(buf, "PNG"); calls = []
        old = (I.request_image, media_cfg.get_key, media_cfg.add_usage)
        I.request_image = lambda p, *a, **k: calls.append(p) or buf.getvalue(); media_cfg.get_key = lambda n: "k"; media_cfg.add_usage = lambda **k: None
        try: self.assertEqual(A.main(["aha-001"]), 0)
        finally: I.request_image, media_cfg.get_key, media_cfg.add_usage = old
        self.assertEqual(len(calls), 2); self.assertTrue(all("No words" in p for p in calls))   # the text is never asked of the picture
        self.assertTrue(os.path.exists(A.beat_file(self.D, 2))); self.assertTrue(os.path.exists(os.path.join(self.D, "background.png")))
        self.assertTrue(self.N.aha_beats_done(self.D))

    def test_a_script_without_a_picture_per_beat_is_refused(self):
        import aha_pictures as A
        json.dump({"lines": ["a", "b"], "pictures": ["only one prompt for two beats here"]}, open(os.path.join(self.D, "quote.json"), "w"))
        with self.assertRaises(ValueError): A.prompts(self.D)

    def test_marks_are_drawn_not_spoken_and_the_voice_is_normal_speed(self):
        import narrate_eleven as E
        self.script(2); self.assertNotIn("*", E.quote_text(self.D)); self.assertEqual(E.chosen_pace(self.D), "normal")
        self.assertEqual(self.C.plain("AI can be *wrong*."), "AI can be wrong.")

    def test_its_quiet_bed_comes_from_its_own_library_even_under_a_voice(self):
        self.assertEqual(self.P.narrated_music(True, "auto", "/lib/a.mp3", "library", library_ok=True), ("/lib/a.mp3", "library"))
        self.assertEqual(self.P.narrated_music(True, "auto", "/lib/a.mp3", "library"), (None, "none"))   # inspiration: only the owner's own track under a voice
        self.assertEqual(self.P.MUSIC_LIB["aha"], "aha_music"); self.assertTrue(0.2 <= self.P.LOOKS["aha"]["music"] <= 0.35)   # under the voice, yet audible on a phone (0.12 was not)

    def test_the_channel_music_is_fitted_and_its_beats_found_under_the_beat_pictures(self):
        import subprocess, shutil
        from PIL import Image
        if not shutil.which("ffmpeg"): self.skipTest("ffmpeg is not installed")
        self.script(2); os.makedirs(os.path.join(self.D, "scenes"))
        for i in range(2): Image.new("RGB", (8, 8)).save(os.path.join(self.D, "scenes", "beat_%02d.png" % (i + 1)))
        Image.new("RGB", (8, 8)).save(os.path.join(self.D, "background.png"))
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=20", os.path.join(self.D, "music_src.mp3")], check=True)
        self.P.main("aha-001")   # the beat finder ran on the bed (it was shadowed by the picture list once)
        T = json.load(open(os.path.join(self.D, "timing.json"))); self.assertEqual(T["music"], "music.mp3"); self.assertEqual([l["bg"] for l in T["lines"]], ["scenes/beat_01.png", "scenes/beat_02.png"])

    def test_a_narrated_scene_short_is_rendered_with_its_pictures_not_the_lyrics_template(self):
        import inspire_render as R
        from unittest import mock
        T = {"narration": True, "duration": 25, "background": "background.png", "voiceover": "narration.mp3", "music": "music.mp3",
             "lines": [{"text": "A", "start": 0, "end": 3, "bg": "scenes/beat_01.png"}, {"text": "B", "start": 3, "end": 6, "bg": "scenes/beat_02.png"}], "style": {}}
        with mock.patch.object(R, "remotion_dir", return_value=self.tmp.name), mock.patch.object(R.subprocess, "run") as run:
            R.render_remotion(self.D, T, os.path.join(self.D, "out.mp4"))
        cmd = run.call_args[0][0]; self.assertIn("Quote", cmd); self.assertNotIn("Lyrics", cmd); self.assertIn("--props=" + os.path.join(self.D, "timing.json"), cmd)
        T["lines"] = [{k: v for k, v in l.items() if k != "bg"} for l in T["lines"]]   # a narrated inspiration quote keeps the lyrics template
        with mock.patch.object(R, "remotion_dir", return_value=self.tmp.name), mock.patch.object(R.subprocess, "run") as run:
            R.render_remotion(self.D, T, os.path.join(self.D, "out.mp4"))
        self.assertIn("Lyrics", run.call_args[0][0])

    def test_redoing_a_step_that_an_approval_follows_keeps_the_new_output(self):   # the video was put back to the old one when it waited for approval
        from unittest import mock
        N = self.N; dest = os.path.join(self.tmp.name, "prev"); os.makedirs(dest); open(os.path.join(dest, "old.mp4"), "w").write("old")
        with mock.patch.object(N, "steps", return_value=[{"id": "render"}]), mock.patch.object(N, "redo", return_value=dest), mock.patch.object(N, "run", return_value=0), \
             mock.patch.object(N, "plan", return_value=([{"id": "render", "done": True, "status": "waiting for approval"}], None)), mock.patch.object(N, "restore") as back:
            self.assertEqual(N.redo_run("aha-001", "render"), 0); back.assert_not_called()
        with mock.patch.object(N, "steps", return_value=[{"id": "render"}]), mock.patch.object(N, "redo", return_value=dest), mock.patch.object(N, "run", return_value=0), \
             mock.patch.object(N, "plan", return_value=([{"id": "render", "done": False, "status": "ready"}], None)), mock.patch.object(N, "restore") as back:
            self.assertEqual(N.redo_run("aha-001", "render"), 1); back.assert_called_once_with("aha-001", dest)   # a real failure still puts the old files back

    def test_each_line_gets_its_beat_picture_and_keeps_its_marks(self):
        from PIL import Image
        self.script(3); os.makedirs(os.path.join(self.D, "scenes"))
        for i in range(3): Image.new("RGB", (8, 8)).save(os.path.join(self.D, "scenes", "beat_%02d.png" % (i + 1)))
        Image.new("RGB", (8, 8)).save(os.path.join(self.D, "background.png"))
        open(os.path.join(self.D, "brief.md"), "w").write("- music: none\n")
        self.P.main("aha-001"); T = json.load(open(os.path.join(self.D, "timing.json")))
        self.assertEqual([l["bg"] for l in T["lines"]], ["scenes/beat_01.png", "scenes/beat_02.png", "scenes/beat_03.png"])
        self.assertEqual(T["lines"][0]["text"], "Beat 0 *key*"); self.assertTrue(T["lines"][2]["aha"]); self.assertNotIn("aha", T["lines"][0])   # the caption is shown, the full line spoken
        self.assertEqual(T["style"]["place"], "center")


if __name__ == "__main__":
    unittest.main()
