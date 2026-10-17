import os, sys, json, shutil, subprocess, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import bg_music as B, narration, inspire_prep as IP

HAVE = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def tone(seconds=5):
    p = os.path.join(tempfile.mkdtemp(), "a.mp3")
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=330:duration=%d" % seconds, "-c:a", "libmp3lame", p], check=True)
    return open(p, "rb").read()


class Base(unittest.TestCase):
    def setUp(self):
        self.D = tempfile.mkdtemp()
        open(os.path.join(self.D, "brief.md"), "w").write("# Inspiration short\n\n## Idea\n\nx\n\n## Options\n\n- music: none\n")


@unittest.skipUnless(HAVE, "ffmpeg is needed")
class Music(Base):
    def test_a_track_is_kept_checked_named_and_turns_the_music_on_and_drops_what_was_made_from_the_old_music(self):
        for n in ("music.mp3", "beats.json", "timing.json"): open(os.path.join(self.D, n), "w").write("old")
        r = B.save(self.D, "Calm Piano by Someone.mp3", tone(5))
        self.assertEqual((r["file"], r["name"]), ("music_src.mp3", "Calm Piano by Someone.mp3")); self.assertGreaterEqual(r["seconds"], 4.5)   # the track's own name is kept for its licence
        self.assertEqual(narration.get_option(self.D, "music"), "auto")
        self.assertEqual([os.path.exists(os.path.join(self.D, n)) for n in ("music.mp3", "beats.json", "timing.json")], [False] * 3)
        self.assertEqual(B.info(self.D)["name"], "Calm Piano by Someone.mp3")

    def test_remove_takes_it_away_and_turns_the_music_off(self):
        B.save(self.D, "a.mp3", tone(3)); B.remove(self.D)
        self.assertIsNone(B.info(self.D)); self.assertEqual(narration.get_option(self.D, "music"), "none")
        self.assertEqual([f for f in os.listdir(self.D) if f.startswith("music_src")], [])

    def test_a_new_track_replaces_the_old_one(self):
        B.save(self.D, "a.mp3", tone(3)); B.save(self.D, "b.mp3", tone(4))
        self.assertEqual(sorted(f for f in os.listdir(self.D) if f.startswith("music_src")), ["music_src.json", "music_src.mp3"]); self.assertEqual(B.info(self.D)["name"], "b.mp3")

    def test_an_approved_video_keeps_its_old_sound_so_nothing_is_dropped(self):
        open(os.path.join(self.D, "timing.json"), "w").write("old"); B.save(self.D, "a.mp3", tone(3), drop_stale=False)
        self.assertTrue(os.path.exists(os.path.join(self.D, "timing.json")))


class Refusals(Base):
    def test_only_audio_of_a_sensible_size_is_kept(self):
        with self.assertRaises(ValueError): B.save(self.D, "a.exe", b"x")
        with self.assertRaises(ValueError): B.save(self.D, "a.mp3", b"")
        with self.assertRaises(ValueError): B.save(self.D, "a.mp3", b"x" * (B.MAX_BYTES + 1))
        if HAVE:
            with self.assertRaises(ValueError): B.save(self.D, "a.mp3", b"this is not audio")   # named mp3, but ffprobe finds no audio
            self.assertEqual([f for f in os.listdir(self.D) if f.startswith("music_src")], [])


class UnderAVoice(unittest.TestCase):
    def test_auto_under_a_voice_means_only_the_owners_track_never_a_library_pick_or_the_pad(self):
        self.assertEqual(IP.narrated_music(True, "auto", "/lib/x.mp3", "library"), (None, "none"))
        self.assertEqual(IP.narrated_music(True, "auto", None, "pad"), (None, "none"))
        self.assertEqual(IP.narrated_music(True, "auto", "/d/music_src.mp3", "file in folder"), ("/d/music_src.mp3", "file in folder"))
        self.assertEqual(IP.narrated_music(False, "auto", None, "pad"), (None, "pad"))   # no voice: as before
        self.assertEqual(IP.narrated_music(True, "/some/path.mp3", "/some/path.mp3", "brief"), ("/some/path.mp3", "brief"))   # a path in the brief was asked for by name


if __name__ == "__main__":
    unittest.main()
