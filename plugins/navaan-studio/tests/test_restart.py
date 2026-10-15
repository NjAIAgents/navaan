import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))


class Restart(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = self.tmp.name
        import navaan as N, navaan_common as C
        self.N = N; self.D = os.path.join(C.songs_root(), "s1"); os.makedirs(os.path.join(self.D, "images"))
        for f in ("prompt_pack.json", "images/pic_01.png", "shots.json", "final_16x9.mp4", "youtube.json"): open(os.path.join(self.D, f), "w").write("x")
        json.dump({"slug": "s1", "type": "music", "state": "approved", "approvals": {"credits": {"at": "t"}, "shots": {"at": "t"}, "media": {"at": "t"}, "listen": {"at": "t"}}}, open(os.path.join(self.D, "meta.json"), "w"))
        self.real = N.steps
        N.steps = lambda slug, D: [
            dict(id="prompts", outputs=["prompt_pack.json"], label="plan", kind="script", done=lambda m: True),
            dict(id="pictures", outputs=["images/*"], label="pictures", kind="script", before="credits", done=lambda m: True),
            dict(id="shots", outputs=["shots.json"], label="shots", kind="claude", after="shots", done=lambda m: True),
            dict(id="video", outputs=["final_16x9.mp4"], label="video", kind="script", after="media", done=lambda m: True),
            dict(id="youtube_meta", outputs=["youtube.json"], label="meta", kind="claude", done=lambda m: True)]

    def tearDown(self):
        self.N.steps = self.real; os.environ.pop("NAVAAN_ROOT", None); self.tmp.cleanup()

    def test_range_runs_from_the_step_through_the_render_only(self):
        self.assertEqual(self.N.redo_range("s1", "prompts"), ["prompts", "pictures", "shots", "video"])
        self.assertEqual(self.N.redo_range("s1", "shots"), ["shots", "video"])
        self.assertEqual(self.N.redo_range("s1", "youtube_meta"), ["youtube_meta"])   # outside the chain: just itself

    def test_restart_moves_files_aside_and_clears_the_three_gates(self):
        self.assertEqual(self.N.redo_from("s1", "prompts"), ["prompts", "pictures", "shots", "video"])
        for f in ("prompt_pack.json", "images/pic_01.png", "shots.json", "final_16x9.mp4"): self.assertFalse(os.path.exists(os.path.join(self.D, f)), f)
        self.assertTrue(os.path.exists(os.path.join(self.D, "youtube.json")))   # later steps are not touched
        prev = os.path.join(self.D, "_prev"); moved = [os.path.join(r, f) for r, _, fs in os.walk(prev) for f in fs]
        self.assertEqual(len(moved), 4)   # nothing deleted
        m = json.load(open(os.path.join(self.D, "meta.json")))
        self.assertEqual(sorted(m["approvals"]), ["listen"]); self.assertEqual(m["state"], "accepted"); self.assertNotIn("redo_pending", m)

    def test_restart_from_a_later_step_keeps_the_earlier_files(self):
        self.N.redo_from("s1", "shots")
        self.assertTrue(os.path.exists(os.path.join(self.D, "images", "pic_01.png"))); self.assertFalse(os.path.exists(os.path.join(self.D, "shots.json")))
        m = json.load(open(os.path.join(self.D, "meta.json"))); self.assertIn("credits", m["approvals"]); self.assertNotIn("shots", m["approvals"])

    def test_wiring(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
        self.assertIn("restartFrom(", open(os.path.join(root, "ui.html"), encoding="utf-8").read())
        self.assertIn("/api/restart", open(os.path.join(root, "navaan_ui.py"), encoding="utf-8").read())


class StepsLookFresh(unittest.TestCase):
    """The picture steps must read the song folder when asked, not when the step list was built (a finished step was run again 3 times)."""
    def test_done_follows_the_folder_after_the_list_was_built(self):
        with tempfile.TemporaryDirectory() as root:
            os.environ["NAVAAN_ROOT"] = root
            try:
                import navaan as N, media_cfg, visuals_cfg
                D = os.path.join(root, "songs", "s9"); os.makedirs(os.path.join(D, "images"))
                st = {s["id"]: s for s in N.song_picture_steps("s9", D, media_cfg.load())}
                self.assertFalse(st["prompts"]["done"]({})); self.assertFalse(st["pictures"]["done"]({}))
                json.dump({"prompts": [{"prompt": "p"}], "style_line": "s"}, open(os.path.join(D, "prompt_pack.json"), "w"))
                self.assertTrue(st["prompts"]["done"]({}))   # same step object, folder changed
                for i in range(visuals_cfg.MIN_VIDEO): open(os.path.join(D, "images", "pic_%02d.png" % (i + 1)), "wb").write(b"x")
                self.assertTrue(st["pictures"]["done"]({}))
            finally: os.environ.pop("NAVAAN_ROOT", None)

    def test_running_row_has_a_progress_bar(self):
        ui = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "ui.html"), encoding="utf-8").read()
        self.assertIn("rbar", ui); self.assertIn("pictures made", ui)


if __name__ == "__main__":
    unittest.main()
