import os, sys, json, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import narrate_eleven as N, narration, tts_eleven as T, media_cfg as M


class Base(unittest.TestCase):
    def setUp(self):
        self.D = tempfile.mkdtemp(); self.conf = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"NAVAAN_CONF_DIR": self.conf, "NAVAAN_CACHE_DIR": tempfile.mkdtemp()}); self.env.start()
        json.dump({"text": "Stay soft. Stay.", "lines": ["Stay soft.", "Stay."], "author": "Someone Famous"}, open(os.path.join(self.D, "quote.json"), "w"))
        open(os.path.join(self.D, "brief.md"), "w").write("# Inspiration short\n\n## Idea\n\nx\n\n## Options\n\n- music: auto\n")
        self.song = mock.patch.object(N.C, "song_dir", lambda slug: self.D); self.song.start()

    def tearDown(self): self.env.stop(); self.song.stop()


class Narrate(Base):
    def test_only_the_quote_is_spoken_never_the_author(self):
        self.assertEqual(N.quote_text(self.D), "Stay soft.\n\nStay.")   # a blank line between lines is a pause
        os.remove(os.path.join(self.D, "quote.json"))
        with self.assertRaises(ValueError): N.quote_text(self.D)

    def test_voice_is_frank_by_default_and_the_brief_can_pick_nj(self):
        self.assertEqual(N.chosen_voice(self.D), "frank")
        narration.set_options(self.D, {"voice": "nj"}); self.assertEqual(N.chosen_voice(self.D), "nj")
        narration.set_options(self.D, {"voice": "bogus"}); self.assertEqual(N.chosen_voice(self.D), "frank")

    def test_run_writes_the_voiceover_sets_the_options_and_drops_stale_timing(self):
        open(os.path.join(self.D, "voiceover.srt"), "w").write("old"); open(os.path.join(self.D, "narration_sync.json"), "w").write("{}")
        seen = {}
        def fake(text, out, voice=None, model=None, force=False, speed=None): seen.update(text=text, voice=voice, speed=speed); open(out, "wb").write(b"mp3"); return {"file": out, "cached": False, "seconds": 3.0, "voice": voice, "model": "m", "spent_seconds": 3.0}
        narration.set_options(self.D, {"voice": "nj"})
        with mock.patch.object(T, "synth", fake): r = N.run("s")
        self.assertEqual(seen, {"text": "Stay soft.\n\nStay.", "voice": "nj", "speed": T.PACES["slow"]})   # slow unless the brief says otherwise
        self.assertTrue(os.path.isfile(os.path.join(self.D, "voiceover.mp3"))); self.assertFalse(os.path.exists(os.path.join(self.D, "voiceover.srt"))); self.assertFalse(os.path.exists(os.path.join(self.D, "narration_sync.json")))
        self.assertEqual((narration.get_option(self.D, "voiceover"), narration.get_option(self.D, "music")), ("file", "none"))

    def test_info_shows_the_estimate_and_the_month_without_spending(self):
        self.assertTrue(N.info(self.D)["on"])   # on unless skipped
        narration.set_options(self.D, {"voice": "nj"})
        i = N.info(self.D)
        self.assertEqual((i["on"], i["voice"], sorted(i["voices"])), (True, "nj", ["frank", "nj"])); self.assertGreater(i["estimate_s"], 0); self.assertEqual(i["cap_s"], M.load()["eleven_monthly_seconds"])

    def test_pace_is_slow_by_default_the_brief_can_change_it_and_a_slower_pace_means_a_longer_estimate(self):
        self.assertEqual(N.chosen_pace(self.D), "slow"); slow = N.info(self.D)["estimate_s"]
        narration.set_options(self.D, {"pace": "normal"}); self.assertEqual(N.chosen_pace(self.D), "normal"); self.assertLess(N.info(self.D)["estimate_s"], slow)
        narration.set_options(self.D, {"pace": "bogus"}); self.assertEqual(N.chosen_pace(self.D), "slow")
        self.assertEqual(sorted(N.info(self.D)["paces"]), ["calm", "normal", "slow"])

    def test_the_audio_cache_is_not_in_the_small_config_folder(self):
        self.assertFalse(T.cache_dir().startswith(self.conf))

    def test_removing_the_narration_also_turns_the_step_off(self):
        narration.set_options(self.D, {"narrate": "eleven"}); narration.remove(self.D)
        self.assertEqual(narration.get_option(self.D, "narrate"), "none")


class Speed(Base):
    def take(self, speed, errors=()):
        """one synth call with the network faked; returns the request bodies sent"""
        import io, urllib.error
        sent = []
        def fake_open(req, timeout=0):
            sent.append(json.loads(req.data))
            if errors and len(sent) == 1: raise urllib.error.HTTPError(req.full_url, errors[0], "bad", {}, io.BytesIO(b"no speed"))
            r = mock.Mock(); r.read.return_value = b"mp3"; return r
        out = os.path.join(self.D, "o.mp3")
        with mock.patch.object(T.urllib.request, "urlopen", fake_open), mock.patch.object(T.M, "get_key", lambda p: "k"), mock.patch.object(T, "_seconds", lambda p: 2.0):
            T.synth("Stay soft.", out, voice="frank", speed=speed, force=True)
        return sent

    def test_the_request_carries_the_speed_and_a_slow_pace_is_below_one(self):
        self.assertLess(T.PACES["slow"], T.PACES["calm"]); self.assertLess(T.PACES["calm"], T.PACES["normal"])
        sent = self.take(T.PACES["slow"]); self.assertEqual(sent[0]["voice_settings"]["speed"], 0.75)
        self.assertNotIn("voice_settings", self.take(None)[0])   # no pace asked: the model's own

    def test_a_take_at_another_speed_is_not_served_from_the_cache(self):
        self.assertNotEqual(T._key("x", "v", "m", 0.75), T._key("x", "v", "m", 1.0))

    def test_a_model_that_refuses_the_speed_setting_is_asked_again_without_it(self):
        sent = self.take(0.75, errors=(400,)); self.assertEqual(len(sent), 2); self.assertNotIn("voice_settings", sent[1])
        with self.assertRaises(Exception): self.take(0.75, errors=(401,))   # any other refusal still fails

    def test_a_speed_outside_what_the_service_takes_is_clamped(self):
        self.assertEqual(self.take(0.1)[0]["voice_settings"]["speed"], 0.7); self.assertEqual(self.take(5)[0]["voice_settings"]["speed"], 1.2)


class Pipeline(Base):
    def steps(self):
        import navaan
        with mock.patch.object(navaan, "song_dir", lambda slug: self.D): return navaan.inspiration_steps("s", self.D)

    def test_narration_is_a_standard_step_before_the_timing_step_and_behind_the_credits_approval(self):
        got = [s["id"] for s in self.steps()]   # nothing was chosen: the default is narrated
        self.assertIn("narrate", got); self.assertLess(got.index("narrate"), got.index("narration")); self.assertLess(got.index("narration"), got.index("typeset"))
        self.assertEqual(next(s for s in self.steps() if s["id"] == "narrate")["before"], "credits")   # the spend is approved first

    def test_a_short_can_skip_it_and_a_voice_that_already_exists_makes_the_step_done(self):
        narration.set_options(self.D, {"narrate": "none"}); self.assertNotIn("narrate", [s["id"] for s in self.steps()])
        narration.set_options(self.D, {"narrate": "eleven"}); open(os.path.join(self.D, "voiceover.mp3"), "wb").write(b"x")
        step = next(s for s in self.steps() if s["id"] == "narrate"); self.assertTrue(step["done"](None))   # an uploaded or made voice is not made again
        os.remove(os.path.join(self.D, "voiceover.mp3")); step = next(s for s in self.steps() if s["id"] == "narrate")
        self.assertFalse(step["done"]({})); self.assertTrue(step["done"]({"approvals": {"media": {"at": "x"}}}))   # a short whose video is already approved is not reopened for a voice

    def test_without_a_key_the_step_says_how_to_skip(self):
        narration.set_options(self.D, {"narrate": "eleven"})
        with mock.patch.object(T.M, "get_key", lambda p: ""), self.assertRaises(RuntimeError) as c: N.run("s")
        self.assertIn("skip narration", str(c.exception))


if __name__ == "__main__":
    unittest.main()
