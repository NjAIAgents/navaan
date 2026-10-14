import os, sys, json, shutil, tempfile, unittest, wave
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
try:
    import numpy as np
except ImportError:
    np = None
import narration as N
if np is not None:
    import narration_sync as S

BRIEF = "# Inspiration short\n\n## Idea\n\nx\n\n## Options\n\n- music: auto\n- voiceover: none\n"
SR = 16000


def voice(parts):
    """parts: [(seconds, loud)] made into mono audio. Loud parts are noise with a speech like wobble, quiet parts are near silence."""
    rng = np.random.default_rng(3); out = []
    for sec, loud in parts:
        n = int(sec * SR); t = np.arange(n) / SR
        out.append((0.3 * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t)) * rng.standard_normal(n) if loud else 0.0005 * rng.standard_normal(n)).astype(np.float32))
    return np.concatenate(out)


# three lines: 2.0 s, 3.5 s, 5.0 s of voice with a small breath inside the last one, 1.2 s gaps between lines
X = voice([(0.3, 0), (2.0, 1), (1.2, 0), (3.5, 1), (1.2, 0), (2.4, 1), (0.3, 0), (2.4, 1), (0.4, 0)])
L3 = ["a" * 20, "b" * 35, "c" * 50]


def wav(path, x):
    with wave.open(path, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR); f.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


@unittest.skipIf(np is None, "numpy missing")
class Pauses(unittest.TestCase):
    def test_lines_are_matched_to_the_gaps(self):
        cues, info = S.by_pauses(X, L3)
        self.assertEqual(info["method"], "pauses"); self.assertEqual(len(cues), 3)
        self.assertAlmostEqual(cues[0][0], 0.3, delta=0.15)
        self.assertAlmostEqual(cues[1][0], 3.42, delta=0.2)   # the second line starts where its voice starts
        self.assertAlmostEqual(cues[2][0], 8.02, delta=0.2)
        self.assertEqual(cues[0][1], cues[1][0]); self.assertEqual(cues[1][1], cues[2][0])

    def test_wrong_number_of_lines_is_not_accepted(self):
        cues, why = S.by_pauses(X, L3 + ["d" * 30])
        self.assertIsNone(cues); self.assertIn("real pauses", why)

    def test_a_single_line_needs_no_pause(self):
        cues, _ = S.by_pauses(X, ["only"]); self.assertEqual(len(cues), 1)

    def test_silence_is_reported(self):
        cues, why = S.by_pauses(np.zeros(SR * 3, np.float32), L3); self.assertIsNone(cues); self.assertIn("no voice", why)

    def test_srt_text(self):
        t = S.to_srt([[0.3, 3.4, "one"], [3.4, 7.0, "two"]])
        self.assertIn("00:00:00,300 --> 00:00:03,400\none", t); self.assertIn("2\n00:00:03,400 --> 00:00:07,000\ntwo", t)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg missing")
    def test_sync_writes_the_srt_beside_the_audio(self):
        D = tempfile.mkdtemp(); wav(os.path.join(D, "voiceover.wav"), X)
        info = S.sync(D, L3, allow_whisper=False)
        self.assertEqual((info["method"], info["cues"]), ("pauses", 3))
        import inspire_prep
        cues = inspire_prep.parse_srt(os.path.join(D, "voiceover.srt"))
        self.assertEqual([c["text"] for c in cues], L3)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg missing")
    def test_no_fit_and_no_whisper_returns_none(self):
        D = tempfile.mkdtemp(); wav(os.path.join(D, "voiceover.wav"), X)
        self.assertIsNone(S.sync(D, L3 + ["d" * 30], allow_whisper=False)); self.assertFalse(os.path.exists(os.path.join(D, "voiceover.srt")))


class Upload(unittest.TestCase):
    def folder(self):
        D = tempfile.mkdtemp(); open(os.path.join(D, "brief.md"), "w").write(BRIEF); return D

    def test_audio_with_text_and_no_srt(self):
        D = self.folder()
        r = N.save(D, "v.m4a", b"M4A", "", "Some people leave.\n\n  but the life   you imagined stays.\n")
        self.assertEqual((r["audio"], r["cues"], r["seconds"], r["timing"]), ("voiceover.m4a", 2, None, "pending"))
        self.assertFalse(os.path.exists(os.path.join(D, "voiceover.srt")))
        q = json.load(open(os.path.join(D, "quote.json")))
        self.assertEqual(q["lines"], ["Some people leave.", "but the life you imagined stays."])
        b = open(os.path.join(D, "brief.md")).read()
        self.assertIn("- voiceover: file", b); self.assertIn("- music: none", b)

    def test_audio_without_srt_or_text_is_rejected(self):
        with self.assertRaises(ValueError): N.save(self.folder(), "v.m4a", b"M4A", "", "  \n")

    def test_new_audio_clears_the_old_timing(self):
        D = self.folder(); open(os.path.join(D, "narration_sync.json"), "w").write("{}")
        N.save(D, "a.mp3", b"1", "1\n00:00:01,000 --> 00:00:03,000\nhello there\n")
        self.assertTrue(os.path.exists(os.path.join(D, "voiceover.srt")))
        N.save(D, "b.mp3", b"2", "", "new words")
        self.assertFalse(os.path.exists(os.path.join(D, "voiceover.srt"))); self.assertFalse(os.path.exists(os.path.join(D, "narration_sync.json")))


class Step(unittest.TestCase):
    def test_pipeline_has_the_narration_step_only_with_audio(self):
        import navaan
        D = tempfile.mkdtemp(); open(os.path.join(D, "brief.md"), "w").write(BRIEF)
        ids = lambda: [s["id"] for s in navaan.inspiration_steps("insp-x", D)]
        self.assertNotIn("narration", ids())
        open(os.path.join(D, "voiceover.m4a"), "wb").write(b"x")
        i = ids(); self.assertIn("narration", i); self.assertLess(i.index("narration"), i.index("typeset"))
        st = [s for s in navaan.inspiration_steps("insp-x", D) if s["id"] == "narration"][0]
        self.assertFalse(st["done"]({})); open(os.path.join(D, "voiceover.srt"), "w").write("x")
        self.assertTrue(st["done"]({}))


if __name__ == "__main__":
    unittest.main()
