import os, sys, json, stat, tempfile, unittest, urllib.error
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import media_cfg as M
import tts_eleven as T
import settings_api


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"NAVAAN_CONF_DIR": self.d, "NAVAAN_CACHE_DIR": tempfile.mkdtemp()}, clear=False)   # the audio cache is not in the config folder, so each test gets its own
        self.env.start()
        for k in ("OPENAI_API_KEY", "ELEVENLABS_API_KEY"):
            os.environ.pop(k, None)

    def tearDown(self):
        self.env.stop()


class Cfg(Base):
    def test_defaults(self):
        s = M.load()
        self.assertEqual((s["voice"], s["image_provider"], s["narration_source"], s["image_quality"]), ("suno1", "flow", "upload", "high"))
        self.assertEqual(s["image_model"], "gpt-image-2.5-flare")
        self.assertEqual({k: M.VOICES[k]["id"] for k in ("suno1", "suno2", "suno3")}, {"suno1": "RolbsV2FrXoOuw9WMoGA", "suno2": "bPnfgYfv98trOeQJkL0s", "suno3": "neLkJ2FTGxCOW53t1Gsi"})
        self.assertEqual(next(iter(M.VOICES)), "suno1")   # first in the list: the default
        self.assertEqual(M.VOICES["frank"]["id"], "V2bPluzT7MuirpucVAKH")
        self.assertEqual(M.VOICES["nj"]["id"], "r3RejoyX9duc0wFH79cE")

    def test_save_and_reload(self):
        M.save({"voice": "nj", "image_provider": "openai"})
        s = M.load()
        self.assertEqual((s["voice"], s["image_provider"], s["image_quality"]), ("nj", "openai", "high"))

    def test_refuses_bad_values(self):
        for bad in ({"voice": "bob"}, {"nope": 1}, {"max_run_usd": 500}, {"max_run_usd": "x"}):
            with self.assertRaises(ValueError):
                M.save(bad)
        self.assertEqual(M.load()["voice"], "suno1")

    def test_corrupt_file_falls_back(self):
        open(os.path.join(self.d, "media.json"), "w").write('{"voice": "zzz", "eleven_monthly_seconds": "abc"')
        self.assertEqual(M.load()["voice"], "suno1")
        open(os.path.join(self.d, "media.json"), "w").write('{"voice": "zzz", "eleven_monthly_seconds": "abc"}')
        s = M.load()
        self.assertEqual((s["voice"], s["eleven_monthly_seconds"]), ("suno1", 1500))


class Keys(Base):
    GOOD = "sk-" + "a" * 40

    def test_key_saved_after_live_test_and_not_returned(self):
        with mock.patch("urllib.request.urlopen") as u:
            u.return_value.read.return_value = b"x"
            r = settings_api.media_key_save("openai", self.GOOD)
        self.assertNotIn(self.GOOD, json.dumps(r))
        self.assertTrue(r["keys"]["openai"])
        p = os.path.join(self.d, "openai.env")
        self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)
        self.assertEqual(open(p).read().strip(), "OPENAI_API_KEY=" + self.GOOD)

    def test_pasted_assignment_line_is_accepted(self):
        with mock.patch("urllib.request.urlopen") as u:
            u.return_value.read.return_value = b"x"
            M.key_save("elevenlabs", "ELEVENLABS_API_KEY=sk_" + "b" * 40)
        self.assertEqual(M.get_key("elevenlabs"), "sk_" + "b" * 40)

    @staticmethod
    def _http(code, body):
        import io
        return urllib.error.HTTPError("u", code, "no", {}, io.BytesIO(json.dumps(body).encode()))

    def test_eleven_key_without_user_read_is_saved_with_a_note(self):
        key = "sk_" + "c" * 40
        err = self._http(401, {"detail": {"status": "missing_permissions", "message": "needs user_read"}})
        with mock.patch("urllib.request.urlopen", side_effect=err):
            r = M.key_save("elevenlabs", key)
        self.assertEqual(M.get_key("elevenlabs"), key)
        self.assertIn("Text to Speech", r["note"])

    def test_eleven_invalid_key_says_so_in_words(self):
        err = self._http(401, {"detail": {"status": "invalid_api_key", "message": "Invalid API key"}})
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(ValueError) as c:
                M.key_save("elevenlabs", "sk_" + "d" * 40)
        self.assertIn("not a valid key", str(c.exception))
        self.assertFalse(M.get_key("elevenlabs"))

    def test_rejected_key_keeps_the_old_one(self):
        with mock.patch("urllib.request.urlopen") as u:
            u.return_value.read.return_value = b"x"
            M.key_save("openai", self.GOOD)
        err = urllib.error.HTTPError("u", 401, "no", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(ValueError) as c:
                M.key_save("openai", "sk-" + "z" * 40)
        self.assertNotIn("zzzz", str(c.exception))
        self.assertEqual(M.get_key("openai"), self.GOOD)

    def test_bad_shape_never_reaches_the_network(self):
        with mock.patch("urllib.request.urlopen") as u:
            for bad in ("", "short", "has space " + "x" * 40):
                with self.assertRaises(ValueError):
                    M.key_save("openai", bad)
            with self.assertRaises(ValueError):
                M.key_save("other", self.GOOD)
            u.assert_not_called()

    def test_status_never_contains_a_key(self):
        with mock.patch("urllib.request.urlopen") as u:
            u.return_value.read.return_value = b"x"
            M.key_save("openai", self.GOOD)
        self.assertNotIn(self.GOOD, json.dumps(settings_api.media_save({"voice": "nj"})))


def fake_resp(data=b"MP3DATA"):
    r = mock.MagicMock()
    r.read.return_value = data
    return r


class Tts(Base):
    def setUp(self):
        super().setUp()
        os.environ["ELEVENLABS_API_KEY"] = "sk_" + "c" * 40
        self.out = os.path.join(self.d, "v.mp3")
        self.sec = mock.patch.object(T, "_seconds", return_value=10.0)
        self.sec.start()

    def tearDown(self):
        self.sec.stop()
        super().tearDown()

    def test_first_take_calls_once_with_the_default_voice_and_counts_usage(self):
        with mock.patch("urllib.request.urlopen", return_value=fake_resp()) as u:
            r = T.synth("Maybe you're not falling behind.", self.out)
        req = u.call_args[0][0]
        self.assertIn("RolbsV2FrXoOuw9WMoGA", req.full_url)
        self.assertEqual(req.headers["Xi-api-key"], "sk_" + "c" * 40)
        self.assertEqual(json.loads(req.data)["model_id"], "eleven_v4")
        self.assertFalse(r["cached"])
        self.assertEqual(open(self.out, "rb").read(), b"MP3DATA")
        self.assertEqual(M.usage()["eleven_seconds"], 10.0)

    def test_same_text_is_never_generated_twice(self):
        with mock.patch("urllib.request.urlopen", return_value=fake_resp()) as u:
            T.synth("Same line.", self.out)
            r = T.synth("Same line.", self.out)
            self.assertEqual(u.call_count, 1)
        self.assertTrue(r["cached"])
        self.assertEqual(M.usage()["eleven_seconds"], 10.0)

    def test_other_voice_or_text_is_a_new_take(self):
        with mock.patch("urllib.request.urlopen", return_value=fake_resp()) as u:
            T.synth("Line.", self.out)
            T.synth("Line.", self.out, voice="nj")
            T.synth("Line two.", self.out)
            self.assertEqual(u.call_count, 3)
        self.assertIn("r3RejoyX9duc0wFH79cE", u.call_args_list[1][0][0].full_url)

    def test_monthly_cap_stops_before_any_spend(self):
        M.save({"eleven_monthly_seconds": 60})
        M.add_usage(eleven_seconds=55)
        with mock.patch("urllib.request.urlopen") as u:
            with self.assertRaises(RuntimeError) as c:
                T.synth("x" * 240, self.out)
            u.assert_not_called()
        self.assertIn("monthly", str(c.exception))

    def test_no_key_and_empty_text_and_bad_voice(self):
        os.environ.pop("ELEVENLABS_API_KEY")
        with self.assertRaises(RuntimeError):
            T.synth("Hello.", self.out)
        with self.assertRaises(ValueError):
            T.synth("   ", self.out)
        with self.assertRaises(ValueError):
            T.synth("Hello.", self.out, voice="bob")

    def test_error_body_does_not_leak_the_key(self):
        err = urllib.error.HTTPError("u", 401, "no", {}, None)
        err.read = lambda: ("bad key " + os.environ["ELEVENLABS_API_KEY"]).encode()
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(RuntimeError) as c:
                T.synth("Hello.", self.out)
        self.assertNotIn("ccccc", str(c.exception))

    def test_estimate(self):
        self.assertAlmostEqual(T.estimate("x" * 240), 20.0)


class Wiring(unittest.TestCase):
    def test_media_files_go_to_vault_and_the_route_exists(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
        vs = open(os.path.join(root, "deploy", "vault_sync.py"), encoding="utf-8").read()
        for n in ("openai.env", "elevenlabs.env", "media.json"):
            self.assertIn('"%s"' % n, vs)
        ui = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "navaan_ui.py"), encoding="utf-8").read()
        self.assertIn('act == "media_save"', ui)
        self.assertIn('act == "media_key"', ui)


if __name__ == "__main__":
    unittest.main()
