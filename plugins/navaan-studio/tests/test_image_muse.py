import os, sys, io, json, base64, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import media_cfg as M
import image_openai as I
from PIL import Image

KEY = "LLM|" + "a" * 30


def img(fmt):
    b = io.BytesIO(); Image.new("RGB", (64, 114), (10, 90, 160)).save(b, fmt); return b.getvalue()


class Resp(io.BytesIO):
    def __init__(self, raw): super().__init__(json.dumps({"data": [{"b64_json": base64.b64encode(raw).decode()}]}).encode())
    def __enter__(self): return self
    def __exit__(self, *a): return False


class Muse(unittest.TestCase):
    def setUp(self):
        self.conf = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"NAVAAN_CONF_DIR": self.conf}, clear=False); self.env.start()
        for v in ("OPENAI_API_KEY", "MUSE_API_KEY"): os.environ.pop(v, None)

    def tearDown(self): self.env.stop()

    def test_openai_stays_the_default(self):
        self.assertEqual(I.engine(), "openai"); self.assertEqual(I.model_name(), "gpt-image-2.5-flare")

    def test_muse_is_flat_one_cent_whatever_the_quality_or_references(self):
        M.save({"image_engine": "muse"})
        self.assertEqual(I.model_name(), "muse-image-1.0")
        self.assertEqual((I.estimate("max", "1792x1008"), I.estimate("low", "1152x2048", refs=5)), (0.01, 0.01))
        self.assertEqual(I.check_cap("high"), 0.01)

    def test_generation_request_and_webp_is_saved_as_png(self):
        with mock.patch("urllib.request.urlopen", return_value=Resp(img("WEBP"))) as u:
            raw = I.request_image("a bench", "high", KEY, "1152x2048", I.MUSE_MODEL)
        req = u.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.meta.ai/v1/images/generations")
        self.assertEqual(req.get_header("Authorization"), "Bearer " + KEY)
        body = json.loads(req.data)
        self.assertEqual(body, {"model": "muse-image-1.0", "prompt": "a bench", "size": "1152x2048", "n": 1})  # no quality: Muse rejects unknown fields
        self.assertEqual(Image.open(io.BytesIO(raw)).format, "PNG")

    def test_edit_sends_references_as_data_urls(self):
        ref = img("PNG")
        with mock.patch("urllib.request.urlopen", return_value=Resp(img("PNG"))) as u:
            I.request_edit("same people, new scene", [ref, ref], "high", KEY, "1792x1008", I.MUSE_MODEL)
        req = u.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.meta.ai/v1/images/edits")
        self.assertEqual(req.get_header("Content-type"), "application/json")
        body = json.loads(req.data)
        self.assertEqual(len(body["images"]), 2)
        self.assertEqual(base64.b64decode(body["images"][0]["image_url"].split(",", 1)[1]), ref)
        self.assertNotIn("quality", body)

    def test_openai_requests_are_unchanged(self):
        with mock.patch("urllib.request.urlopen", return_value=Resp(img("PNG"))) as u:
            I.request_image("a bench", "high", "sk-" + "a" * 30, "1152x2048", "gpt-image-2.5-flare")
        req = u.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.openai.com/v1/images/generations")
        self.assertEqual(json.loads(req.data)["quality"], "high")

    def test_error_names_muse_and_hides_the_key(self):
        import urllib.error
        err = urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO(json.dumps({"error": {"message": "bad " + KEY}}).encode()))
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(RuntimeError) as c: I.request_image("x", "high", KEY, model=I.MUSE_MODEL)
        self.assertIn("Muse refused the picture (HTTP 400)", str(c.exception)); self.assertNotIn(KEY, str(c.exception))

    def test_key_is_saved_to_muse_env_and_picked_by_the_engine(self):
        M.save({"image_engine": "muse"})
        self.assertEqual(I.key_for(), "")
        M.key_save("muse", KEY)
        self.assertEqual(I.key_for(), KEY)
        self.assertTrue(M.key_state()["muse"]); self.assertFalse(M.key_state()["openai"])
        self.assertEqual(oct(os.stat(os.path.join(self.conf, "muse.env")).st_mode & 0o777), "0o600")

    def test_bad_engine_is_refused(self):
        with self.assertRaises(ValueError): M.save({"image_engine": "midjourney"})


if __name__ == "__main__":
    unittest.main()
