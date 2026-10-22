"""Author: Navjyot Nishant
Created: 2026-10-22
Last updated: 2026-10-22
Description: words timed by what a recogniser hears (NAV-146), tested on the two real narrations that drifted (insp-008 and insp-009), not on synthetic tones.

The reference times are in fixtures/narration/truth.json (two independent recognisers and the loudness agree on them). The recogniser's raw output on the two clips is recorded in
fixtures/narration/vosk_heard.json, so the matching logic is tested everywhere; one more test runs the real recogniser when vosk and its model are installed.
"""
import json, os, shutil, sys, tempfile, unittest
from unittest import mock
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import word_align as W

FIX = os.path.join(HERE, "fixtures", "narration")
TRUTH = json.load(open(os.path.join(FIX, "truth.json"), encoding="utf-8"))
HEARD = json.load(open(os.path.join(FIX, "vosk_heard.json"), encoding="utf-8"))
CLIPS = {"insp-008": "008", "insp-009": "009"}


def check(case, name, res):
    t = TRUTH[name]; tol_on, tol_end = TRUTH["onset_tolerance"], TRUTH["end_tolerance"]
    case.assertIsNotNone(res, name)
    for i, (l, on, end) in enumerate(zip(res["lines"], t["onset"], t["end"])):
        case.assertAlmostEqual(l["start"], on, delta=tol_on, msg=f"{name} line {i + 1} starts at {l['start']}, spoken at {on}")
        case.assertAlmostEqual(l["end"], end, delta=tol_end, msg=f"{name} line {i + 1} ends at {l['end']}, spoken until {end}")
        case.assertEqual(len(l["at"]), len(t["lines"][i].split()), "one time per word")
        case.assertEqual(l["at"], sorted(l["at"]), "words in order")
        case.assertTrue(l["at"][0] >= on - tol_on and l["at"][-1] <= end + tol_end, f"{name} line {i + 1} words stay inside where the line is spoken")


class Real(unittest.TestCase):
    def test_each_line_starts_and_ends_where_it_is_spoken_on_both_real_narrations(self):
        for name, key in CLIPS.items(): check(self, name, W.match(TRUTH[name]["lines"], HEARD[key]))

    def test_the_times_the_published_videos_used_were_far_off_and_these_are_not(self):
        for name, key in CLIPS.items():
            res = W.match(TRUTH[name]["lines"], HEARD[key]); used = TRUTH[name]["used_by_the_video_at"]
            old = [abs(u - o) for u, o in zip(used, TRUTH[name]["onset"])]; new = [abs(l["start"] - o) for l, o in zip(res["lines"], TRUTH[name]["onset"])]
            self.assertGreater(max(old), 1.5, "the bug: some line lit more than 1.5 s from where it is spoken")
            self.assertLess(max(new), TRUTH["onset_tolerance"])

    def test_a_misheard_word_takes_the_place_of_the_word_that_was_said_not_a_guess_across_the_gap(self):
        res = W.match(TRUTH["insp-008"]["lines"], HEARD["008"])   # "Not their guilt." was heard as "other killed": two heard words, three script words
        at = res["lines"][2]["at"]
        self.assertEqual(len(at), 3); self.assertTrue(all(10.3 <= t <= 11.2 for t in at), at)

    def test_a_last_word_the_recogniser_missed_is_placed_after_the_one_before_it(self):
        res = W.match(TRUTH["insp-009"]["lines"], HEARD["009"])   # "found you": it heard "found" and not "you"
        at = res["lines"][5]["at"]; self.assertGreater(at[-1], at[-2]); self.assertLess(at[-1], 35.0)


class Refusals(unittest.TestCase):
    L = ["You were never meant to carry everything.", "Not their expectations."]

    def test_too_few_words_heard_right_is_not_trusted(self):
        other = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.3} for i, w in enumerate("completely different words that match nothing here at all".split())]
        self.assertIsNone(W.match(self.L, other)); self.assertIsNone(W.match(self.L, [])); self.assertIsNone(W.match([], other))

    def test_a_blank_line_cannot_be_timed(self):
        h = [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate("you were never meant to carry everything".split())]
        self.assertIsNone(W.match([self.L[0], "   "], h))

    def test_punctuation_and_case_do_not_matter_and_times_never_run_backwards(self):
        h = [{"word": w, "start": 1.0, "end": 1.0} for w in "YOU were, never meant TO carry everything".split()]   # a recogniser that gave every word the same instant
        at = W.match([self.L[0]], h)["lines"][0]["at"]
        self.assertEqual(at, sorted(at)); self.assertTrue(all(b - a >= 0.03 for a, b in zip(at, at[1:])), at)


class Load(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.d, True)
    def write(self, lines): json.dump({"method": "vosk", "lines": [{"at": a} for a in lines]}, open(os.path.join(self.d, W.WORDS), "w"))

    def test_times_are_used_only_when_they_fit_the_lines_on_screen(self):
        self.assertIsNone(W.load(self.d, ["a b"]), "no file")
        self.write([[1.0, 1.5], [3.0]]); self.assertEqual(W.load(self.d, ["a b", "c"]), [[1.0, 1.5], [3.0]])
        self.assertIsNone(W.load(self.d, ["a b", "c d"]), "a line with another number of words: the script was edited")
        self.assertIsNone(W.load(self.d, ["a b"]), "another number of lines")
        open(os.path.join(self.d, W.WORDS), "w").write("{nope"); self.assertIsNone(W.load(self.d, ["a b", "c"]))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class Sync(unittest.TestCase):
    """narration_sync tries the word times first and falls back, with a reason, when they cannot be used."""
    def setUp(self):
        try: import numpy  # noqa: F401
        except ImportError: self.skipTest("numpy not installed")
        self.d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.d, True)
        shutil.copy(os.path.join(FIX, "insp-008.mp3"), os.path.join(self.d, "voiceover.mp3"))
        self.lines = TRUTH["insp-008"]["lines"]

    def run_sync(self, vosk_ready=True, aligned=True):
        import narration_sync as N, setup_captions as S
        res = W.match(self.lines, HEARD["008"]) if aligned else None
        with mock.patch.object(S, "vosk_ready", return_value=vosk_ready), mock.patch.object(W, "align", return_value=res), \
             mock.patch.object(N, "by_whisper_lines", side_effect=RuntimeError("the caption tools are not installed")), mock.patch.object(N, "by_pauses", return_value=([[0.0, 5.0, "x"]], {"method": "pauses"})):
            return N.sync(self.d, self.lines, ffmpeg="ffmpeg")

    def test_the_word_times_set_the_line_starts_and_are_kept_for_the_captions(self):
        info = self.run_sync()
        self.assertEqual(info["method"], "word-aligned"); self.assertEqual(info["heard_right"], "13 of 20")
        srt = open(os.path.join(self.d, "voiceover.srt"), encoding="utf-8").read()
        self.assertIn("00:00:02,190 --> 00:00:07,350", srt); self.assertIn("00:00:10,470 --> 00:00:16,140", srt)   # line 1 starts where it is spoken, and runs to where line 2 is
        words = json.load(open(os.path.join(self.d, W.WORDS))); self.assertEqual(len(words["lines"]), 5); self.assertEqual(len(words["lines"][2]["at"]), 3)
        self.assertEqual(W.load(self.d, self.lines), [l["at"] for l in words["lines"]])

    def test_without_the_tools_or_enough_words_it_falls_back_and_says_why_and_forgets_old_times(self):
        json.dump({"method": "vosk", "lines": []}, open(os.path.join(self.d, W.WORDS), "w"))   # the times of an older take
        info = self.run_sync(vosk_ready=False)
        self.assertEqual(info["method"], "pauses"); self.assertIn("not installed", info["words_unavailable"]); self.assertFalse(os.path.exists(os.path.join(self.d, W.WORDS)))
        info = self.run_sync(aligned=False); self.assertIn("too few of your words", info["words_unavailable"]); self.assertFalse(os.path.exists(os.path.join(self.d, W.WORDS)))


def _model():
    p = os.environ.get("NAVAAN_VOSK_MODEL")
    if not p:
        try: import setup_captions as S; p = S.VOSK
        except ImportError: return None   # expected: no caption tools module on this path
    return p if os.path.isfile(os.path.join(p, "am", "final.mdl")) else None


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class Recogniser(unittest.TestCase):
    """The real recogniser on the real clips, when vosk and its model are installed (setup_captions.py --vosk --yes, or NAVAAN_VOSK_MODEL)."""
    def test_listening_to_the_audio_gives_the_same_answer_within_the_tolerances(self):
        try: import numpy, vosk  # noqa: F401
        except ImportError: self.skipTest("numpy or vosk not installed")
        model = _model()
        if not model: self.skipTest("the Vosk model is not installed")
        import narration_sync as N
        for name in CLIPS:
            x = N.decode(os.path.join(FIX, name + ".mp3"), "ffmpeg"); check(self, name, W.align(x, TRUTH[name]["lines"], model))


class Setup(unittest.TestCase):
    """The word timing tools are optional: they never make the caption tools look not ready, and a bad download installs nothing."""
    def test_the_caption_tools_are_ready_without_them_and_the_status_says_so(self):
        import setup_captions as S
        with mock.patch.object(S, "have_pkgs", return_value=True), mock.patch.object(S, "have_models", return_value=True), mock.patch.object(S, "vosk_ready", return_value=False):
            self.assertTrue(S.ready()); self.assertFalse(S.status()["word_timing"])

    def test_they_need_both_the_package_and_the_model(self):
        import setup_captions as S
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d, True); os.makedirs(os.path.join(d, "am")); open(os.path.join(d, "am", "final.mdl"), "w").write("x")
        with mock.patch.object(S, "VOSK", d):
            with mock.patch.object(S, "have_vosk_pkg", return_value=False): self.assertFalse(S.vosk_ready())
            with mock.patch.object(S, "have_vosk_pkg", return_value=True): self.assertTrue(S.vosk_ready())
        with mock.patch.object(S, "VOSK", os.path.join(d, "none")), mock.patch.object(S, "have_vosk_pkg", return_value=True): self.assertFalse(S.vosk_ready())

    def test_without_the_caption_tools_python_it_stops_and_says_what_to_run_first(self):
        import setup_captions as S
        with mock.patch.object(S, "venv_python", return_value="/nonexistent/python"): self.assertIn("setup_captions.py --yes", str(self.exit(S.install_vosk)))

    def test_an_archive_that_escapes_the_folder_installs_nothing(self):
        import setup_captions as S, zipfile
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d, True); z = os.path.join(d, "m.zip")
        with zipfile.ZipFile(z, "w") as f: f.writestr("../evil.txt", "x")
        def fake_download(url, dest): shutil.copy(z, dest)
        with mock.patch.object(S, "MODELS", d), mock.patch.object(S, "VOSK", os.path.join(d, "model")), mock.patch.object(S, "venv_python", return_value=sys.executable), \
             mock.patch.object(S, "have_vosk_pkg", return_value=True), mock.patch.object(S, "download", side_effect=fake_download):
            self.assertIn("unsafe path", str(self.exit(S.install_vosk)))
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(d), "evil.txt")))

    def test_a_failed_word_timing_install_does_not_fail_the_caption_tools_install(self):
        import setup_captions as S
        with mock.patch.object(S, "have_pkgs", return_value=True), mock.patch.object(S, "have_models", return_value=True), mock.patch.object(S, "VOC", __file__), \
             mock.patch.object(S, "MODELS", tempfile.mkdtemp()), mock.patch.object(S, "install_vosk", side_effect=SystemExit("no network")), mock.patch("builtins.print") as said:
            S.install()
        self.assertTrue(any("were not installed" in " ".join(map(str, c[0])) for c in said.call_args_list))

    @staticmethod
    def exit(fn):
        try: fn()
        except SystemExit as e: return e
        return None


class Prep(unittest.TestCase):
    """inspire_prep puts the recognised word times into the plan the renderer gets, and keeps the glow from the sound."""
    SRT = "1\n00:00:02,090 --> 00:00:07,250\nYou were never meant to carry everything.\n\n2\n00:00:07,250 --> 00:00:10,370\nNot their expectations.\n\n3\n00:00:10,370 --> 00:00:16,040\nNot their guilt.\n\n4\n00:00:16,040 --> 00:00:22,550\nLet it go.\n\n5\n00:00:22,550 --> 00:00:30,000\nYour peace matters too.\n"

    def setUp(self):
        if not shutil.which("ffmpeg"): self.skipTest("ffmpeg not installed")
        import _pgenv  # noqa: F401  (a throwaway database schema per path, for the item made below)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name
        import new_song, narration, navaan_common as C
        self.slug = new_song.create(None, "inspiration", ""); self.D = C.song_dir(self.slug); L = TRUTH["insp-008"]["lines"]
        json.dump({"text": " ".join(L), "lines": L, "author": "", "kind": "original", "language": "en"}, open(os.path.join(self.D, "quote.json"), "w"))
        narration.set_options(self.D, {"music": "none", "narrate": "none"})
        from PIL import Image
        Image.new("RGB", (8, 8)).save(os.path.join(self.D, "background.png"))
        shutil.copy(os.path.join(FIX, "insp-008.mp3"), os.path.join(self.D, "voiceover.mp3"))
        open(os.path.join(self.D, "voiceover.srt"), "w").write(self.SRT)

    def timing(self):
        import inspire_prep
        with mock.patch("builtins.print"): inspire_prep.main(self.slug)
        return json.load(open(os.path.join(self.D, "timing.json")))

    def test_the_captions_get_the_recognised_times_not_a_guess_across_the_slot(self):
        res = W.match(TRUTH["insp-008"]["lines"], HEARD["008"])
        json.dump({"method": "vosk", "lines": [{"at": l["at"]} for l in res["lines"]]}, open(os.path.join(self.D, W.WORDS), "w"))
        T = self.timing()
        self.assertEqual([l["at"] for l in T["lines"]], [l["at"] for l in res["lines"]])

    def test_without_recognised_times_the_old_guess_is_kept_and_an_edited_script_ignores_old_ones(self):
        res = W.match(TRUTH["insp-008"]["lines"], HEARD["008"]); real = [l["at"] for l in res["lines"]]
        T = self.timing(); self.assertNotEqual([l.get("at") for l in T["lines"]], real)   # no recognised times: whatever the sound says, not the real ones
        json.dump({"method": "vosk", "lines": [{"at": l["at"][:-1]} for l in res["lines"]]}, open(os.path.join(self.D, W.WORDS), "w"))   # one word fewer per line: another script
        T = self.timing(); self.assertNotEqual([l.get("at") for l in T["lines"]], [l["at"][:-1] for l in res["lines"]])

if __name__ == "__main__":
    unittest.main()
