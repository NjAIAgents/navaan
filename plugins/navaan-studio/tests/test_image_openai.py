import os, sys, io, json, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import media_cfg as M
import image_openai as I
import navaan

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def png(w, h):
    b = io.BytesIO(); Image.new("RGB", (w, h), (90, 120, 150)).save(b, "PNG"); return b.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.conf, self.songs = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"NAVAAN_CONF_DIR": self.conf}, clear=False)
        self.env.start()
        os.environ.pop("OPENAI_API_KEY", None)
        self.D = os.path.join(self.songs, "insp-009"); os.makedirs(os.path.join(self.D, "scenes"))
        self.sd = mock.patch.object(I.C, "song_dir", lambda slug: self.D); self.sd.start()

    def tearDown(self):
        self.sd.stop(); self.env.stop()


class Steps(Base):
    def ids(self):
        return [s["id"] for s in navaan.inspiration_steps("insp-009", self.D)]

    def test_flow_by_default(self):
        ids = self.ids()
        self.assertIn("background", ids); self.assertNotIn("background_prompt", ids)

    def test_openai_splits_prompt_and_picture(self):
        M.save({"image_provider": "openai"})
        st = {s["id"]: s for s in navaan.inspiration_steps("insp-009", self.D)}
        self.assertFalse(st["background_prompt"]["chrome"])
        self.assertIsNone(st["background_prompt"].get("before"))
        self.assertEqual(st["background"]["kind"], "script")
        self.assertEqual(st["background"]["before"], "credits")  # the spend gate stays on the picture step
        self.assertIn("OpenAI", st["background"]["label"])

    def test_own_background_never_spends(self):
        M.save({"image_provider": "openai"})
        open(os.path.join(self.D, "brief.md"), "w").write("- background: library\n")
        st = {s["id"]: s for s in navaan.inspiration_steps("insp-009", self.D)}
        self.assertNotIn("background_prompt", st); self.assertIsNone(st["background"].get("before"))


class Cap(Base):
    def test_estimate_and_cap(self):
        self.assertAlmostEqual(I.check_cap("high"), 0.0424, places=3)  # default model gpt-image-2.5-flare, default size 1152x2048, tokens times $30 per million
        M.save({"image_model": "gpt-image-2"})
        self.assertAlmostEqual(I.check_cap("medium"), 0.062)  # the older model keeps its price table
        self.assertAlmostEqual(I.check_cap("medium", size="1024x1536"), 0.041)
        M.save({"max_run_usd": 0.05})
        with self.assertRaises(ValueError): I.check_cap("high")

    def test_2_5_prices_follow_the_measured_tokens(self):
        self.assertAlmostEqual(I.estimate("high", "1792x1008"), 0.037, places=3)
        self.assertAlmostEqual(I.estimate("high", "1792x1008", refs=1), 0.049, places=3)
        self.assertAlmostEqual(I.estimate("high", "1152x2048", refs=1), 0.0545, places=3)
        q = [I.estimate(x, "1792x1008") for x in ("low", "medium", "high", "xhigh", "max")]
        self.assertEqual(q, sorted(q))  # a higher quality never costs less

    def test_model_comes_from_settings_and_env(self):
        self.assertEqual(I.model_name(), "gpt-image-2.5-flare")
        M.save({"image_model": "gpt-image-2.5-sunburst"}); self.assertEqual(I.model_name(), "gpt-image-2.5-sunburst")
        with mock.patch.dict(os.environ, {"NAVAAN_OPENAI_IMAGE_MODEL": "gpt-image-2"}): self.assertEqual(I.model_name(), "gpt-image-2")

    def test_estimate_flag_spends_nothing(self):
        with mock.patch.object(I, "request_image") as r:
            self.assertEqual(I.main(["insp-009", "--estimate"]), 0)
            r.assert_not_called()


@unittest.skipIf(Image is None, "pillow missing")
class Make(Base):
    def prep(self, prompt="A quiet riverside bench at dawn, soft mist, muted colours."):
        open(os.path.join(self.D, "scenes", "background.txt"), "w").write(prompt)
        open(os.path.join(self.conf, "openai.env"), "w").write("OPENAI_API_KEY=sk-" + "a" * 30 + "\n")

    def test_fit_is_cover_crop(self):
        out = I.fit_portrait(png(1024, 1536)); self.assertEqual(out.size, (1080, 1920))
        out = I.fit_portrait(png(1152, 2048)); self.assertEqual(out.size, (1080, 1920))  # exact 9:16, scaled down, nothing cropped

    def test_makes_background_and_counts_spend(self):
        self.prep()
        with mock.patch.object(I, "request_image", return_value=png(1024, 1536)) as r:
            self.assertEqual(I.main(["insp-009"]), 0)
            self.assertEqual(r.call_count, 1)
        self.assertEqual(Image.open(os.path.join(self.D, "background.png")).size, (1080, 1920))
        self.assertTrue(os.path.exists(os.path.join(self.D, "scenes", "background_openai.png")))
        self.assertAlmostEqual(M.usage()["openai_usd"], I.estimate("high", "1152x2048"))

    def test_existing_background_is_not_replaced_or_paid_for(self):
        self.prep(); open(os.path.join(self.D, "background.jpg"), "wb").write(b"x")
        with mock.patch.object(I, "request_image") as r:
            I.main(["insp-009"]); r.assert_not_called()
        self.assertEqual(M.usage()["openai_usd"], 0)

    def test_force_moves_old_aside(self):
        self.prep(); open(os.path.join(self.D, "background.jpg"), "wb").write(b"x")
        with mock.patch.object(I, "request_image", return_value=png(1024, 1536)):
            I.main(["insp-009", "--force"])
        self.assertFalse(os.path.exists(os.path.join(self.D, "background.jpg")))
        self.assertTrue(os.path.exists(os.path.join(self.D, "scenes", "background_prev.jpg")))

    def test_no_prompt_or_no_key_stops_before_paying(self):
        with mock.patch.object(I, "request_image") as r:
            with self.assertRaises(SystemExit): I.main(["insp-009"])
            self.prep(); os.remove(os.path.join(self.conf, "openai.env"))
            with self.assertRaises(SystemExit): I.main(["insp-009"])
            r.assert_not_called()

    def test_failed_request_costs_nothing_and_hides_key(self):
        self.prep()
        with mock.patch.object(I, "request_image", side_effect=RuntimeError("OpenAI refused the picture (HTTP 400).")):
            with self.assertRaises(RuntimeError): I.main(["insp-009"])
        self.assertEqual(M.usage()["openai_usd"], 0)
        self.assertFalse(os.path.exists(os.path.join(self.D, "background.png")))


class Wiring(unittest.TestCase):
    def test_ui_and_routes(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
        ui = open(os.path.join(root, "ui.html"), encoding="utf-8").read()
        for needle in ("Pictures and voice", "media_save", "media_key", "mediaKey("):
            self.assertIn(needle, ui)


if __name__ == "__main__":
    unittest.main()
