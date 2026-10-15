import os, sys, json, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import song_images_openai as S
import image_openai as IO


class T(unittest.TestCase):
    def test_full_prompt_joins_style_scene_and_rules(self):
        p = S.full_prompt({"style_line": "Warm dusk."}, {"prompt": "A chai stall in a lane.", "motion": "steam"})
        self.assertTrue(p.startswith("Warm dusk. A chai stall in a lane."))
        self.assertIn("No text", p); self.assertNotIn("steam", p)

    def test_cost_and_cap(self):
        self.assertAlmostEqual(S.total_cost(10, "medium", "1792x1008"), 0.48, places=2)
        self.assertEqual(S.check_total(10, "low", "1792x1008", {"max_run_usd": 0.5}), 0.07)
        with self.assertRaises(ValueError) as e: S.check_total(27, "medium", "1792x1008", {"max_run_usd": 0.5})
        self.assertIn("run cap", str(e.exception))

    def test_prices_known_for_both_landscape_sizes(self):
        for s in ("1792x1008", "1536x864"):
            for q in ("low", "medium", "high"): self.assertGreater(IO.estimate(q, s), 0)

    def test_sizes_are_valid_for_the_api(self):
        for s in ("1792x1008", "1536x864"):
            w, h = (int(x) for x in s.split("x")); self.assertEqual((w % 16, h % 16), (0, 0)); self.assertAlmostEqual(w / h, 16 / 9, places=2)

    def test_plan_limits_count(self):
        pk = {"prompts": [{"prompt": str(i)} for i in range(9)]}
        self.assertEqual(len(S.plan(pk)), 9); self.assertEqual(len(S.plan(pk, 4)), 4)

    def test_main_keeps_existing_pictures_and_makes_missing_ones(self):
        D = tempfile.mkdtemp(); os.makedirs(os.path.join(D, "images"))
        json.dump({"style_line": "s", "prompts": [{"n": i, "prompt": "p%d" % i} for i in (1, 2, 3)]}, open(os.path.join(D, "prompt_pack.json"), "w"))
        open(os.path.join(D, "images", "pic_02.png"), "wb").write(b"old")
        S.C.song_dir = lambda slug: D
        S.media_cfg.load = lambda: {"image_quality": "low", "image_size_landscape": "1792x1008", "max_run_usd": 5.0}
        S.media_cfg.get_key = lambda p: "sk-test"
        spent = []; S.media_cfg.add_usage = lambda openai_usd=0.0, eleven_seconds=0.0: spent.append(openai_usd)
        S.IO.request_image = lambda prompt, q, key, size: b"png:" + prompt.encode()
        self.assertEqual(S.main(["x"]), 0)
        self.assertEqual(open(os.path.join(D, "images", "pic_02.png"), "rb").read(), b"old")
        self.assertTrue(open(os.path.join(D, "images", "pic_01.png"), "rb").read().startswith(b"png:s p1"))
        self.assertEqual(len(spent), 2)

    def test_main_refuses_over_cap_before_spending(self):
        D = tempfile.mkdtemp()
        json.dump({"style_line": "s", "prompts": [{"n": i, "prompt": "p"} for i in range(20)]}, open(os.path.join(D, "prompt_pack.json"), "w"))
        S.C.song_dir = lambda slug: D
        S.media_cfg.load = lambda: {"image_quality": "medium", "image_size_landscape": "1792x1008", "max_run_usd": 0.5}
        called = []; S.IO.request_image = lambda *a: called.append(1) or b"x"
        with self.assertRaises(SystemExit) as e: S.main(["x"])
        self.assertIn("run cap", str(e.exception)); self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
