import glob, os, re, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import tts_eleven as T

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
# the only ElevenLabs addresses the app may contain: speech, and the free read-only account check that tests a saved key
ALLOWED = ("https://api.elevenlabs.io/v1/text-to-speech/", "https://api.elevenlabs.io/v1/user")


class Only(unittest.TestCase):
    def test_a_music_or_sound_effect_address_is_refused_before_it_is_sent(self):
        for bad in ("https://api.elevenlabs.io/v1/music", "https://api.elevenlabs.io/v1/music/compose", "https://api.elevenlabs.io/v1/sound-generation", "https://api.elevenlabs.io/v1/text-to-dialogue", "https://example.com/v1/text-to-speech/x"):
            with self.assertRaises(RuntimeError, msg=bad): T.check_url(bad)
        self.assertTrue(T.check_url("https://api.elevenlabs.io/v1/text-to-speech/abc?output_format=mp3_44100_128").startswith(T.ALLOWED_URL))

    def test_no_script_in_the_app_can_call_any_other_elevenlabs_address(self):   # music (about 900 credits a minute) and sound effects are generation: the owner uses a licensed track of their own
        found = []
        for p in sorted(glob.glob(os.path.join(SCRIPTS, "*.py"))):
            for n, line in enumerate(open(p, encoding="utf-8"), 1):
                for u in re.findall(r"https?://[A-Za-z0-9.\-]*elevenlabs\.io[^\s\"'),]*", line):
                    if not u.startswith(ALLOWED): found.append(f"{os.path.basename(p)}:{n}: {u}")
        self.assertEqual(found, [], "an ElevenLabs address that can spend credits on music or sound effects was added")

    def test_the_music_the_pipeline_mixes_comes_from_a_file_of_the_owner_never_from_a_service(self):
        for name in ("bg_music.py", "inspire_prep.py"):
            src = open(os.path.join(SCRIPTS, name), encoding="utf-8").read()
            self.assertNotIn("elevenlabs", src.lower(), name + " must not talk to ElevenLabs")   # music is read from a file and fitted with ffmpeg


class NoDirections(unittest.TestCase):
    def test_the_tags_added_for_pace_ask_for_tone_and_pauses_only_never_for_music_or_sound_effects(self):
        for sp in (0.75, 0.85, 1.0):
            t = T.directed("You are allowed to outgrow your old life, and still be grateful.\n\nYou are allowed to change.", sp)
            for tag in re.findall(r"\[([^\]]+)\]", t): self.assertIn(tag, ("warmly", "softly", "slowly", "pause"), tag)   # a tag like [music] or [applause] would be a sound effect


if __name__ == "__main__":
    unittest.main()
