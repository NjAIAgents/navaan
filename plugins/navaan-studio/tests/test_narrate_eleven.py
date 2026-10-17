import os, sys, json, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import narrate_eleven as N, narration, tts_eleven as T, media_cfg as M
REAL_LOAD = M.load   # the patched M.load calls this, not itself


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

    def test_a_quote_kept_as_one_run_of_sentences_gets_a_pause_after_each_sentence(self):
        json.dump({"text": "You are allowed. Still be grateful, truly. Why?", "author": ""}, open(os.path.join(self.D, "quote.json"), "w"))
        self.assertEqual(N.quote_text(self.D), "You are allowed.\n\nStill be grateful, truly.\n\nWhy?")

    def test_voice_is_suno1_by_default_and_the_brief_can_pick_another(self):
        self.assertEqual(N.chosen_voice(self.D), "suno1")
        narration.set_options(self.D, {"voice": "nj"}); self.assertEqual(N.chosen_voice(self.D), "nj")
        narration.set_options(self.D, {"voice": "bogus"}); self.assertEqual(N.chosen_voice(self.D), "suno1")

    def test_run_writes_the_voiceover_sets_the_options_and_drops_stale_timing(self):
        open(os.path.join(self.D, "voiceover.srt"), "w").write("old"); open(os.path.join(self.D, "narration_sync.json"), "w").write("{}")
        seen = {}
        def fake(text, out, voice=None, model=None, force=False, speed=None, raw=False): seen.update(text=text, voice=voice, speed=speed); open(out, "wb").write(b"mp3"); return {"file": out, "cached": False, "seconds": 3.0, "voice": voice, "model": "m", "spent_seconds": 3.0}
        narration.set_options(self.D, {"voice": "nj"})
        with mock.patch.object(T, "synth", fake): r = N.run("s")
        self.assertEqual((seen["voice"], seen["speed"]), ("nj", T.PACES["slow"]))   # slow unless the brief says otherwise
        self.assertEqual(seen["text"], N.script_text(self.D)); self.assertTrue(seen["text"].startswith("[warmly] [softly] [slowly] Stay soft."))   # the script is what is spoken
        self.assertTrue(os.path.isfile(os.path.join(self.D, "voiceover.mp3"))); self.assertFalse(os.path.exists(os.path.join(self.D, "voiceover.srt"))); self.assertFalse(os.path.exists(os.path.join(self.D, "narration_sync.json")))
        self.assertEqual((narration.get_option(self.D, "voiceover"), narration.get_option(self.D, "music")), ("file", "none"))

    def test_info_shows_the_estimate_and_the_month_without_spending(self):
        self.assertTrue(N.info(self.D)["on"])   # on unless skipped
        narration.set_options(self.D, {"voice": "nj"})
        i = N.info(self.D)
        self.assertEqual((i["on"], i["voice"], sorted(i["voices"])), (True, "nj", ["frank", "nj", "suno1", "suno2", "suno3"])); self.assertGreater(i["estimate_s"], 0); self.assertEqual(i["cap_s"], M.load()["eleven_monthly_seconds"])

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


class Script(Base):
    def v4(self): return mock.patch.object(N.M, "load", lambda: {**REAL_LOAD(), "eleven_model": "eleven_v4"})

    def test_the_suggested_script_is_the_quote_with_the_tags_and_pauses_of_the_pace_on_v4_and_plain_on_other_models(self):
        narration.set_options(self.D, {"pace": "slow"})
        with self.v4(): self.assertTrue(N.script_text(self.D).startswith("[warmly] [softly] [slowly] Stay soft."))
        with mock.patch.object(N.M, "load", lambda: {**REAL_LOAD(), "eleven_model": "eleven_multilingual_v2"}): self.assertEqual(N.script_text(self.D), "Stay soft.\n\nStay.")   # that model takes the speed setting, not tags

    def test_an_edited_script_wins_is_spoken_as_it_is_and_empty_goes_back_to_the_suggestion(self):
        seen = {}
        def fake(text, out, voice=None, model=None, force=False, speed=None, raw=False): seen.update(text=text, raw=raw); open(out, "wb").write(b"mp3"); return {"file": out, "cached": False, "seconds": 3.0, "voice": voice, "model": "m", "spent_seconds": 3.0}
        with self.v4():
            N.save_script(self.D, "  [warmly] Stay... SOFT.  "); self.assertEqual(N.script_text(self.D), "[warmly] Stay... SOFT.")
            self.assertEqual((N.info(self.D)["script"], N.info(self.D)["script_custom"]), ("[warmly] Stay... SOFT.", True))
            with mock.patch.object(T, "synth", fake): N.run("s")
            self.assertEqual(seen, {"text": "[warmly] Stay... SOFT.", "raw": True})   # no second pass of tags over the owner's words
            N.save_script(self.D, ""); self.assertFalse(N.info(self.D)["script_custom"]); self.assertIn("[slowly]", N.script_text(self.D)) if N.chosen_pace(self.D) == "slow" else None
        with self.assertRaises(ValueError): N.save_script(self.D, "x" * (N.MAX_SCRIPT + 1))

    def test_a_script_sent_raw_to_v4_is_not_given_tags_again(self):
        sent = []
        def fake_open(req, timeout=0): sent.append(json.loads(req.data)); r = mock.Mock(); r.read.return_value = b"mp3"; return r
        with mock.patch.object(T.urllib.request, "urlopen", fake_open), mock.patch.object(T.M, "get_key", lambda p: "k"), mock.patch.object(T, "_seconds", lambda p: 2.0), mock.patch.object(T.M, "load", lambda: {**REAL_LOAD(), "eleven_model": "eleven_v4"}):
            T.synth("[softly] Already written.", os.path.join(self.D, "o.mp3"), voice="frank", speed=0.75, force=True, raw=True)
        self.assertEqual(sent[0]["text"], "[softly] Already written."); self.assertNotIn("voice_settings", sent[0])


class Speed(Base):
    def take(self, speed, errors=(), model="eleven_multilingual_v2", text="Stay soft. Stay."):
        """one synth call with the network faked and the Settings model chosen; returns the request bodies sent"""
        import io, urllib.error
        sent = []
        def fake_open(req, timeout=0):
            sent.append(json.loads(req.data))
            if errors and len(sent) == 1: raise urllib.error.HTTPError(req.full_url, errors[0], "bad", {}, io.BytesIO(b"no speed"))
            r = mock.Mock(); r.read.return_value = b"mp3"; return r
        out = os.path.join(self.D, "o.mp3"); real = M.load
        with mock.patch.object(T.urllib.request, "urlopen", fake_open), mock.patch.object(T.M, "get_key", lambda p: "k"), mock.patch.object(T, "_seconds", lambda p: 2.0), mock.patch.object(T.M, "load", lambda: {**real(), "eleven_model": model}):
            T.synth(text, out, voice="frank", speed=speed, force=True)
        return sent

    def test_a_model_that_obeys_the_speed_setting_gets_it_and_a_slow_pace_is_below_one(self):
        self.assertLess(T.PACES["slow"], T.PACES["calm"]); self.assertLess(T.PACES["calm"], T.PACES["normal"])
        sent = self.take(T.PACES["slow"]); self.assertEqual(sent[0]["voice_settings"]["speed"], 0.75); self.assertEqual(sent[0]["text"], "Stay soft. Stay.")   # no tags: it would speak them
        self.assertNotIn("voice_settings", self.take(None)[0])   # no pace asked: the model's own

    def test_v4_and_v3_are_paced_by_direction_tags_not_by_the_speed_setting_they_ignore(self):
        for m in ("eleven_v4", "eleven_v3"):
            b = self.take(0.75, model=m, text="Stay soft, stay.\n\nStay kind.")[0]
            self.assertNotIn("voice_settings", b); self.assertEqual(b["model_id"], m)   # the chosen model stays
            self.assertEqual(b["text"], "[warmly] [softly] [slowly] Stay soft... stay. [pause] Stay kind.")
        self.assertEqual(self.take(0.85, model="eleven_v4")[0]["text"], "[warmly] [softly] Stay soft. Stay.")   # calm: softer, not slower
        self.assertEqual(self.take(1.0, model="eleven_v4")[0]["text"], "Stay soft. Stay.")   # normal: the words as they are
        self.assertEqual(self.take(None, model="eleven_v4")[0]["text"], "Stay soft. Stay.")

    def test_slow_puts_an_ellipsis_at_phrase_breaks_because_the_tag_alone_does_not_slow_v4(self):   # measured live: 5.76 s with tags, 7.84 s with these ellipses, same words
        t = T.directed("You are allowed to outgrow your old life, and still be grateful for who you were.\n\nYou are allowed to change, even when no one understands why.", 0.75)
        self.assertEqual(t, "[warmly] [softly] [slowly] You are allowed... to outgrow... your old life... and still be grateful... for who you were. [pause] You are allowed... to change... even when no one understands why.")
        self.assertNotIn("......", t); self.assertNotIn("... ...", t)   # a comma and a connector together make one break, not two
        self.assertEqual(T.directed("Stay.", 0.85), "[warmly] [softly] Stay.")   # calm is tone only: no extra breaks

    def test_the_ellipsis_is_phrase_aware_it_does_not_double_a_pause_the_text_already_has(self):
        d = lambda t: T.directed(t, 0.75).replace("[warmly] [softly] [slowly] ", "")
        self.assertEqual(d("Wait! And then go to the sea."), "Wait! And then go... to the sea.")   # none after the sentence end, and the break only where a phrase of two words or more came before
        self.assertEqual(d("Go to the sea."), "Go to the sea.")   # two words before "to" is a phrase: but "Go" alone is not
        self.assertEqual(d("Stay, and go."), "Stay... and go.")   # the comma is the pause: one ellipsis, not two
        self.assertEqual(d("Stay — and go to it."), "Stay — and go... to it.")   # no ellipsis next to the dash (it already pauses); the later phrase break is fine
        self.assertEqual(d("Stay soft [pause] and go."), "Stay soft [pause] and go.")   # nor right after a tag
        self.assertEqual(d("Be calm. To you, for your life."), "Be calm. To you... for your life.")
        self.assertNotIn("... ...", d("Light, and love, and loss, to be, for you.")); self.assertNotIn("......", d("Light, and love, and loss, to be, for you."))

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
