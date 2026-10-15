import os, sys, json, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import song_images_openai as S
import image_openai as IO

GEN = lambda prompt, q, key, size, model=None: b"png:" + prompt.encode()
EDIT = lambda prompt, refs, q, key, size, model=None: b"edit:" + prompt.encode()


def pack(n, character="A man in a grey sweater."):
    return {"style_line": "s", "character": character, "prompts": [{"n": i, "prompt": "p%d" % i} for i in range(1, n + 1)]}


class T(unittest.TestCase):
    def setUp(self):
        self.saved = (S.C.song_dir, S.media_cfg.load, S.media_cfg.get_key, S.media_cfg.add_usage, S.IO.request_image, S.IO.request_edit)
        self.D = tempfile.mkdtemp(); os.makedirs(os.path.join(self.D, "images"))
        S.C.song_dir = lambda slug: self.D
        S.media_cfg.load = lambda: {"image_quality": "low", "image_size_landscape": "1792x1008", "max_run_usd": 5.0}
        S.media_cfg.get_key = lambda p: "sk-test"
        self.spent = []; S.media_cfg.add_usage = lambda openai_usd=0.0, eleven_seconds=0.0: self.spent.append(openai_usd)
        S.IO.request_image, S.IO.request_edit = GEN, EDIT

    def tearDown(self):
        (S.C.song_dir, S.media_cfg.load, S.media_cfg.get_key, S.media_cfg.add_usage, S.IO.request_image, S.IO.request_edit) = self.saved

    def put(self, pk): json.dump(pk, open(os.path.join(self.D, "prompt_pack.json"), "w"))

    def test_first_prompt_has_look_people_scene_and_allows_faces(self):
        p = S.full_prompt({"style_line": "Warm dusk.", "character": "A man, 30."}, {"prompt": "A chai stall in a lane.", "motion": "steam"})
        self.assertTrue(p.startswith("Photorealistic cinematic still"))
        for needle in ("Warm dusk.", "A man, 30.", "A chai stall in a lane.", "No text"): self.assertIn(needle, p)
        self.assertNotIn("steam", p); self.assertNotIn("no close up of a face", p)
        self.assertIn("readable faces", S.anchor_prompt({"style_line": "x"}, {"prompt": "y"}))

    def test_scene_prompt_uses_the_reference_and_keeps_the_people(self):
        p = S.scene_prompt({"style_line": "Warm dusk."}, {"prompt": "He waits at a bus stop."})
        for needle in ("uploaded image", "facial identity", "He waits at a bus stop.", "Warm dusk."): self.assertIn(needle, p)

    def test_cost_is_one_new_picture_and_the_rest_edits(self):
        gen, edit = IO.estimate("high", "1792x1008"), IO.estimate("high", "1792x1008", refs=1)
        self.assertAlmostEqual(S.total_cost(16, "high", "1792x1008"), gen + 15 * edit, places=3)
        self.assertLessEqual(S.total_cost(16, "high", "1792x1008"), 0.8)   # 16 pictures at high fit the default run cap
        self.assertAlmostEqual(S.total_cost(4, "high", "1792x1008", anchor=False), 4 * edit, places=3)
        self.assertEqual(S.total_cost(0, "high", "1792x1008"), 0.0)

    def test_cap(self):
        self.assertLess(S.check_total(10, "low", "1792x1008", {"max_run_usd": 0.5}), 0.5)
        with self.assertRaises(ValueError) as e: S.check_total(27, "high", "1792x1008", {"max_run_usd": 0.5})
        self.assertIn("run cap", str(e.exception))

    def test_prices_known_for_both_landscape_sizes_and_every_quality(self):
        for s in ("1792x1008", "1536x864"):
            for q in ("low", "medium", "high", "xhigh", "max"): self.assertGreater(IO.estimate(q, s), 0)

    def test_sizes_are_valid_for_the_api(self):
        for s in ("1792x1008", "1536x864", S.VERT_SIZE):
            w, h = (int(x) for x in s.split("x")); self.assertEqual((w % 16, h % 16), (0, 0))
        self.assertAlmostEqual(1792 / 1008, 16 / 9, places=2); self.assertAlmostEqual(1152 / 2048, 9 / 16, places=2)

    def test_plan_limits_count(self):
        pk = {"prompts": [{"prompt": str(i)} for i in range(9)]}
        self.assertEqual(len(S.plan(pk)), 9); self.assertEqual(len(S.plan(pk, 4)), 4)

    def test_main_makes_picture_1_from_words_then_edits_it_for_the_rest(self):
        self.put(pack(3))
        open(os.path.join(self.D, "images", "pic_02.png"), "wb").write(b"old")
        self.assertEqual(S.main(["x"]), 0)
        im = lambda n: open(os.path.join(self.D, "images", n), "rb").read()
        self.assertEqual(im("pic_02.png"), b"old")
        self.assertTrue(im("pic_01.png").startswith(b"png:Photorealistic") and b"p1" in im("pic_01.png"))
        self.assertTrue(im("pic_03.png").startswith(b"edit:") and b"p3" in im("pic_03.png"))
        self.assertEqual(len(self.spent), 2)

    def test_retry_with_picture_1_present_only_edits(self):
        self.put(pack(3)); open(os.path.join(self.D, "images", "pic_01.png"), "wb").write(b"anchor")
        gens = []; S.IO.request_image = lambda *a, **k: gens.append(1) or b"x"
        self.assertEqual(S.main(["x"]), 0)
        self.assertEqual(gens, []); self.assertEqual(open(os.path.join(self.D, "images", "pic_01.png"), "rb").read(), b"anchor")

    def test_refused_edit_falls_back_to_words(self):
        self.put(pack(2))
        def bad(*a, **k): raise RuntimeError("OpenAI refused the picture (HTTP 400).")
        S.IO.request_edit = bad
        self.assertEqual(S.main(["x"]), 0)
        self.assertTrue(open(os.path.join(self.D, "images", "pic_02.png"), "rb").read().startswith(b"png:"))

    def test_first_picture_failing_stops_before_the_others(self):
        self.put(pack(3)); calls = []
        def bad(*a, **k): raise RuntimeError("OpenAI refused the picture (HTTP 400).")
        S.IO.request_image = bad; S.IO.request_edit = lambda *a, **k: calls.append(1) or b"x"
        with self.assertRaises(SystemExit) as e: S.main(["x"])
        self.assertIn("first picture failed", str(e.exception)); self.assertEqual(calls, []); self.assertEqual(self.spent, [])

    def test_try_makes_two_and_the_second_is_an_edit_of_the_first(self):
        self.put(pack(5)); self.assertEqual(S.main(["x", "--try"]), 0)
        t = lambda n: open(os.path.join(self.D, n), "rb").read()
        self.assertTrue(t("try_01.png").startswith(b"png:")); self.assertTrue(t("try_02.png").startswith(b"edit:"))
        self.assertFalse(os.path.exists(os.path.join(self.D, "images", "pic_01.png")))

    def test_vertical_recomposes_chosen_pictures_once(self):
        self.put(pack(3)); open(os.path.join(self.D, "images", "pic_02.png"), "wb").write(b"wide")
        self.assertEqual(S.main(["x", "--vertical", "2,3"]), 0)   # 3 has no 16:9 picture yet, so it is skipped
        v = os.path.join(self.D, "images", "vert", "pic_02.png")
        self.assertTrue(open(v, "rb").read().startswith(b"edit:") and b"9:16" in open(v, "rb").read())
        self.assertFalse(os.path.exists(os.path.join(self.D, "images", "vert", "pic_03.png")))
        n = len(self.spent); self.assertEqual(S.main(["x", "--vertical", "2"]), 0); self.assertEqual(len(self.spent), n)   # already made, not paid for again
        self.assertEqual(S.V.own_images(self.D), ["images/pic_02.png"])   # verticals never count as song pictures

    def test_main_refuses_over_cap_before_spending(self):
        self.put(pack(20))
        S.media_cfg.load = lambda: {"image_quality": "high", "image_size_landscape": "1792x1008", "max_run_usd": 0.5}
        called = []; S.IO.request_image = lambda *a, **k: called.append(1) or b"x"
        with self.assertRaises(SystemExit) as e: S.main(["x"])
        self.assertIn("run cap", str(e.exception)); self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
