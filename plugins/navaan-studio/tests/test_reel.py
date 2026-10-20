"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: the reel pipeline: the edit plan check, the shrink-on-arrival step, the music library rule (own published songs only) and the render, on synthetic footage.
"""
import json, os, re, shutil, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import _pgenv  # noqa: F401  (a throwaway database schema per path, for the pipeline walk-through)
HAVE_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def ff(*a):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *a], check=True)


def probe(path):
    j = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:format=duration", "-of", "json", path]))
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    return v["width"], v["height"], v["codec_name"], float(j["format"]["duration"]), any(s["codec_type"] == "audio" for s in j["streams"])


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        os.environ["NAVAAN_ROOT"] = self.tmp.name
        self.songs = os.path.join(self.tmp.name, "songs"); self.D = os.path.join(self.songs, "reel-001")
        os.makedirs(os.path.join(self.D, ".cache"))

    def raw(self, secs=12, size="1920x1080", name="raw.mp4", noise=True):
        p = os.path.join(self.D, ".cache", name)
        a = ["-f", "lavfi", "-i", f"anoisesrc=d={secs}:c=pink:a=0.05"] if noise else []
        ff("-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration={secs}", *a, "-c:v", "libx264", "-pix_fmt", "yuv420p", *(["-c:a", "aac"] if noise else []), "-shortest", p)
        return p

    def song(self, slug, state="published", typ="music"):
        d = os.path.join(self.songs, slug); os.makedirs(d)
        json.dump({"slug": slug, "type": typ, "state": state}, open(os.path.join(d, "meta.json"), "w"))
        open(os.path.join(d, "title.txt"), "w").write("Tera Naam\n")
        ff("-f", "lavfi", "-i", "sine=frequency=330:duration=30", os.path.join(d, "final.mp3"))
        return d


class Skills(unittest.TestCase):
    def test_the_directors_example_plan_is_a_valid_plan(self):
        """The example in the skill is what Claude copies from, so it must pass the same check the render uses."""
        import re, reel_edl as E
        txt = open(os.path.join(HERE, "..", "skills", "reel-director", "SKILL.md"), encoding="utf-8").read()
        block = re.search(r"## 3\. edl\.json.*?```\n(.*?)```", txt, re.S).group(1)
        edl = E.validate(json.loads(block), 30.0)
        self.assertEqual(edl["audio"]["music"]["file"], "final.mp3"); self.assertEqual(edl["grade"]["look"], "warm"); self.assertEqual(edl["seconds"], 17.0); self.assertEqual((edl["intro"]["seconds"], edl["outro"]["seconds"], edl["audio"]["vo_start"]), (1.5, 3.0, 1.9))   # 12.5 s of footage + intro + end card

    def test_both_skills_exist_with_names_matching_the_steps(self):
        import navaan
        steps = {s["id"]: s for s in navaan.reel_steps("reel-001", tempfile.mkdtemp())}
        for sid in ("direct", "critique"):
            d = os.path.join(HERE, "..", "skills", steps[sid]["skill"]); self.assertTrue(os.path.isfile(os.path.join(d, "SKILL.md")), steps[sid]["skill"])
            self.assertIn("name: " + steps[sid]["skill"], open(os.path.join(d, "SKILL.md"), encoding="utf-8").read())


class Registry(Env):
    def test_reel_is_a_built_type_with_its_own_gates_and_steps(self):
        import navaan, navaan_common as C, new_song
        self.assertIn("reel", C.CONTENT_TYPES); self.assertIn("reel", new_song.BUILT); self.assertEqual(C.TYPE_PREFIX["reel"], "reel"); self.assertTrue(C.is_short("reel"))
        g = C.type_gates("reel")
        self.assertIn("edit_plan", g); self.assertIn("edit_plan", C.GATES); self.assertNotIn("publish_youtube", g); self.assertNotIn("go_public", g)
        self.assertEqual(navaan.SHA_FILES["edit_plan"], "edl.json", "an edit after approval needs a new approval")
        ids = [s["id"] for s in navaan.steps("reel-001", self.D) if False] or [s["id"] for s in navaan.reel_steps("reel-001", self.D)]
        self.assertEqual(ids[:4], ["ingest", "direct", "originality", "edit_check"])
        self.assertLess(ids.index("render"), ids.index("critique")); self.assertLess(ids.index("critique"), ids.index("instagram_caption"))
        self.assertNotIn("publish_youtube", ids)
        gates = [s.get("after") or s.get("before") for s in navaan.reel_steps("reel-001", self.D)]
        for need in ("quote", "originality", "edit_plan", "media", "instagram_caption", "publish_instagram"): self.assertIn(need, gates)
        for gate in gates:
            if gate: self.assertIn(gate, g, gate + " must be a gate of the reel type")

    def test_instagram_only_account_needs_just_its_instagram_login(self):
        import navaan_common as C
        env = os.path.join(self.tmp.name, "ig.env"); open(env, "w").write("X=1\n")
        json.dump({"accounts": {"reel": {"instagram_handle": "navaan_reels", "instagram_env": env}}}, open(os.path.join(self.tmp.name, "navaan.config.json"), "w"))
        a = C.account("reel"); self.assertTrue(a["configured"]); self.assertTrue(a["ig_ready"])

    def test_template_makes_a_reel_item(self):
        t = os.path.join(HERE, "..", "templates", "reel")
        self.assertEqual(json.load(open(os.path.join(t, "meta.json")))["type"], "reel")
        self.assertIn("- narrate: eleven", open(os.path.join(t, "brief.md")).read())


class Upload(Env):
    def test_streams_to_disk_and_keeps_the_extension(self):
        import io, reel_upload as U
        data = os.urandom(3 * 1024 * 1024 + 17)
        self.assertEqual(U.save(io.BytesIO(data), len(data), self.D, "Holiday.MOV"), len(data))
        p = os.path.join(self.D, ".cache", "raw.mov"); self.assertEqual(open(p, "rb").read(), data); self.assertFalse(os.path.exists(os.path.join(self.D, ".cache", "raw.part")))

    def test_refusals_leave_nothing_behind(self):
        import io, reel_upload as U
        def code(f, n, name="a.mp4"):
            with self.assertRaises(U.Refused) as cm: U.save(f, n, self.D, name)
            return cm.exception.code
        self.assertEqual(code(io.BytesIO(b"x"), 1, "a.exe"), 400)
        self.assertEqual(code(io.BytesIO(b""), 0), 400)
        self.assertEqual(code(io.BytesIO(b"abc"), 10), 400, "the connection ended early")
        self.assertEqual(os.listdir(os.path.join(self.D, ".cache")), [], "no half-written file is left")
        json.dump({"reel": {"max_upload_mb": 1}}, open(os.path.join(self.tmp.name, "navaan.config.json"), "w"))
        self.assertEqual(code(io.BytesIO(b"x"), 2 * 1024 * 1024), 413)
        open(os.path.join(self.D, "source.mp4"), "wb").write(b"x"); json.dump({}, open(os.path.join(self.tmp.name, "navaan.config.json"), "w"))
        self.assertEqual(code(io.BytesIO(b"x"), 1), 409, "footage is not silently replaced")

    def test_a_new_complete_upload_replaces_an_unshrunk_one(self):
        import io, reel_upload as U
        U.save(io.BytesIO(b"first"), 5, self.D, "a.mp4"); U.save(io.BytesIO(b"second!"), 7, self.D, "b.mov")
        self.assertEqual(sorted(os.listdir(os.path.join(self.D, ".cache"))), ["raw.mov"])


class Edl(unittest.TestCase):
    def good(self):
        return {"segments": [{"start": 1, "end": 5}, {"start": 6, "end": 9, "crop_x": 0.3, "zoom": 1.0, "zoom_to": 1.15}], "grade": {"look": "warm"}, "audio": {"policy": "ambient_low"},
                "text": [{"text": "Stay", "start": 0.3, "end": 2.0}]}

    def test_good_plan_is_cleaned_and_filled(self):
        import reel_edl as E
        e = E.validate(self.good(), 12.0)
        self.assertEqual(e["seconds"], 7.0); self.assertEqual(e["segments"][0]["crop_x"], 0.5); self.assertEqual(e["audio"]["vo_start"], 0.4); self.assertEqual(e["quote"]["pos"], "mid")

    def test_every_problem_is_listed(self):
        import reel_edl as E
        bad = {"segments": [{"start": 1, "end": 6}, {"start": 5, "end": 9}], "grade": {"look": "neon", "contrast": 9}, "audio": {"policy": "shout", "music": {"file": "../x.mp3"}}, "text": [{"text": "late", "start": 1, "end": 40}]}
        with self.assertRaises(ValueError) as cm: E.validate(bad, 12.0)
        m = str(cm.exception)
        for part in ("overlap", "neon", "contrast", "shout", "not a path", "after the reel"):
            self.assertIn(part, m.replace("must be a file name, not a path", "not a path"))

    def test_intro_and_end_card_count_toward_the_length_and_move_the_voice(self):
        import reel_edl as E
        e = E.validate({"segments": [{"start": 0, "end": 10}], "intro": {"seconds": 1.5}, "outro": {"seconds": 3}}, 10.0)
        self.assertEqual((e["seconds"], e["content_seconds"]), (14.5, 10.0))
        self.assertEqual(e["audio"]["vo_start"], 1.9, "the voice starts after the intro unless the plan says otherwise")
        self.assertEqual(e["quote"]["start"], 2.5); self.assertTrue(e["quote"]["show"]); self.assertTrue(e["outro"]["handle"] and e["outro"]["credit"])
        self.assertEqual(E.validate({"segments": [{"start": 0, "end": 10}], "audio": {"vo_start": 0.2}, "quote": {"show": False}}, 10.0)["audio"]["vo_start"], 0.2)
        self.assertFalse(E.validate({"segments": [{"start": 0, "end": 10}], "quote": {"show": False}}, 10.0)["quote"]["show"])
        with self.assertRaises(ValueError) as cm: E.validate({"segments": [{"start": 0, "end": 10}], "intro": {"seconds": 5}, "outro": {"seconds": 9}}, 10.0)
        self.assertIn("intro.seconds", str(cm.exception)); self.assertIn("outro.seconds", str(cm.exception))
        with self.assertRaises(ValueError): E.validate({"segments": [{"start": 0, "end": 2}], "intro": {"seconds": 0.5}}, 10.0)   # 2.5 s in all: under the minimum
        self.assertIn("End card", E.summary(e)); self.assertIn("Intro", E.summary(e))

    def test_length_limits_and_range(self):
        import reel_edl as E
        with self.assertRaises(ValueError): E.validate({"segments": [{"start": 0, "end": 2}]}, 12.0)   # under 3 s
        with self.assertRaises(ValueError): E.validate({"segments": [{"start": 0, "end": 200}]}, 100.0)   # past the footage
        with self.assertRaises(ValueError): E.validate({"segments": []}, 12.0)
        with self.assertRaises(ValueError): E.validate("nope", 12.0)


@unittest.skipUnless(HAVE_FF, "ffmpeg not installed")
class Ingest(Env):
    def test_shrinks_checks_and_deletes_the_original(self):
        import reel_ingest as I
        raw = self.raw(); big = os.path.getsize(raw)
        I.main("reel-001")
        self.assertFalse(os.path.exists(raw), "the big original is removed once the copy is checked")
        w, h, codec, dur, has_a = probe(os.path.join(self.D, "source.mp4"))
        self.assertEqual((codec, has_a), ("h264", True)); self.assertAlmostEqual(dur, 12.0, delta=0.6)
        pr = json.load(open(os.path.join(self.D, "probe.json")))
        self.assertTrue(pr["raw_deleted"]); self.assertEqual(pr["source_bytes"], big); self.assertEqual(pr["source_width"], 1920)
        fr = json.load(open(os.path.join(self.D, "frames.json"))); self.assertGreaterEqual(len(fr), 8)
        self.assertTrue(all(os.path.exists(os.path.join(self.D, f["file"])) for f in fr))
        au = json.load(open(os.path.join(self.D, "audio.json")))
        self.assertTrue(au["has_audio"]); self.assertFalse(au["has_speech"], "steady noise is not speech")

    def test_long_side_is_capped_and_original_can_be_kept(self):
        import reel_ingest as I
        json.dump({"reel": {"proxy": {"max_long_side": 640}, "keep_original": True}}, open(os.path.join(self.tmp.name, "navaan.config.json"), "w"))
        raw = self.raw(secs=6, size="1280x720"); I.main("reel-001")
        self.assertTrue(os.path.exists(raw), "reel.keep_original keeps it")
        w, h, *_ = probe(os.path.join(self.D, "source.mp4")); self.assertEqual((w, h), (640, 360))

    def test_footage_without_sound(self):
        import reel_ingest as I
        self.raw(secs=5, noise=False); I.main("reel-001")
        au = json.load(open(os.path.join(self.D, "audio.json"))); self.assertFalse(au["has_audio"]); self.assertFalse(au["has_speech"])

    def test_an_interrupted_upload_is_not_used(self):
        import reel_ingest as I
        open(os.path.join(self.D, ".cache", "raw.part"), "wb").write(b"half"); self.assertIsNone(I.find_raw(self.D))
        with self.assertRaises(SystemExit): I.main("reel-001")

    def test_speech_is_bursty_noise_is_not(self):
        import reel_ingest as I, random
        random.seed(1)
        steady = [40 + random.random() * 3 for _ in range(1500)]
        talk = [(62 if (i // 12) % 2 == 0 else 38) + random.random() * 4 for i in range(1500)]   # a loud and a quiet frame run, about 4 bursts a second
        self.assertFalse(I.speech_guess(steady)["speech"]); self.assertTrue(I.speech_guess(talk)["speech"])


class Music(Env):
    @unittest.skipUnless(HAVE_FF, "ffmpeg not installed")
    def test_only_our_published_songs_are_offered(self):
        import reel_music as M
        self.song("song-001"); self.song("song-002", state="draft"); self.song("insp-001", typ="inspiration")
        lib = M.library()
        self.assertEqual([(t["slug"], t["file"]) for t in lib], [("song-001", "final.mp3")]); self.assertEqual(lib[0]["title"], "Tera Naam")
        self.assertTrue(M.resolve("song-001", "final.mp3"))
        for slug, name in (("song-002", "final.mp3"), ("insp-001", "final.mp3"), ("../x", "final.mp3"), ("song-001", "../final.mp3"), ("song-001", "secret.txt")):
            self.assertIsNone(M.resolve(slug, name), (slug, name))


@unittest.skipUnless(HAVE_FF, "ffmpeg not installed")
class Render(Env):
    def prep(self, voice=False, plan=None):
        import reel_ingest as I
        self.raw(secs=14); I.main("reel-001")
        self.song("song-001")
        plan = plan or {"segments": [{"start": 1, "end": 5, "zoom": 1.0, "zoom_to": 1.2}, {"start": 7, "end": 11, "crop_x": 0.2}], "grade": {"look": "cinematic", "vignette": True}, "stabilize": True,
                        "audio": {"policy": "ambient_low", "music": {"slug": "song-001", "file": "final.mp3", "start": 3, "level": 0.4}},
                        "text": [{"text": "Some places feel like a pause", "start": 0.3, "end": 2.5, "pos": "top"}], "quote": {"start": 3.0, "pos": "low"}}
        json.dump(plan, open(os.path.join(self.D, "edl.json"), "w"))
        json.dump({"lines": ["Slow down.", "The day is still yours."], "author": ""}, open(os.path.join(self.D, "quote.json"), "w"))
        if voice:
            ff("-f", "lavfi", "-i", "sine=frequency=200:duration=5", os.path.join(self.D, "voiceover.mp3"))
            open(os.path.join(self.D, "voiceover.srt"), "w").write("1\n00:00:00,000 --> 00:00:02,000\nSlow down.\n\n2\n00:00:02,200 --> 00:00:05,000\nThe day is still yours.\n")

    def check(self, secs, audio=True):
        import reel_render as R
        R.main("reel-001")
        w, h, codec, dur, has_a = probe(os.path.join(self.D, "final_reel_9x16.mp4"))
        self.assertEqual((w, h, codec), (1080, 1920, "h264")); self.assertAlmostEqual(dur, secs, delta=0.3); self.assertEqual(has_a, audio)
        if audio:   # the sound lasts as long as the picture: ducking under a short voice used to cut the background off when the voice stopped
            asec = float(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration", "-of", "csv=p=0", os.path.join(self.D, "final_reel_9x16.mp4")]).strip())
            self.assertAlmostEqual(asec, dur, delta=0.15)
        self.assertTrue(os.path.exists(os.path.join(self.D, "thumb_9x16.jpg")))
        return json.load(open(os.path.join(self.D, "render_report.json")))

    def test_render_with_music_text_and_zoom(self):
        self.prep(); rep = self.check(8.0)
        self.assertEqual(rep["music"], "song-001/final.mp3"); self.assertFalse(rep["voice"]); self.assertEqual(rep["quote_lines"], 2)

    def test_render_with_a_narration_ducks_the_music_and_times_the_quote(self):
        self.prep(voice=True); rep = self.check(8.0)
        self.assertTrue(rep["voice"])
        import reel_render as R, reel_edl as E
        edl = E.validate(json.load(open(os.path.join(self.D, "edl.json"))), 14.0)
        cues, _ = R.quote_cues(self.D, edl)
        self.assertEqual(cues[0][1], 0.4, "the first line appears where the voice starts (0.4 s in)")

    def frame_brightness(self, t):
        from PIL import Image, ImageStat
        p = os.path.join(self.D, f"b{t}.jpg"); ff("-ss", str(t), "-i", os.path.join(self.D, "final_reel_9x16.mp4"), "-frames:v", "1", "-vf", "scale=108:-2", p)
        return ImageStat.Stat(Image.open(p).convert("L")).mean[0]

    def test_intro_and_end_card_hold_the_first_and_last_frame(self):
        json.dump({"accounts": {"reel": {"instagram_handle": "@navaan_reels"}}}, open(os.path.join(self.tmp.name, "navaan.config.json"), "w"))
        self.prep(plan={"segments": [{"start": 0, "end": 6}], "intro": {"seconds": 1.0}, "outro": {"seconds": 2.0}, "audio": {"policy": "mute"}, "quote": {"show": False}})
        rep = self.check(9.0, audio=False)
        self.assertEqual((rep["intro_s"], rep["outro_s"]), (1.0, 2.0)); self.assertTrue(rep["end_card"], "the handle is drawn on the end card")
        self.assertLess(self.frame_brightness(8.5), 0.8 * self.frame_brightness(5.5), "the end card dims the held last frame")
        a, b = self.frame_brightness(0.5), self.frame_brightness(0.9)   # after the 0.3 s fade in
        self.assertAlmostEqual(a, b, delta=3.0, msg="the intro holds one frame")

    def test_end_card_without_handle_or_credit_is_just_the_held_frame(self):
        self.prep(plan={"segments": [{"start": 0, "end": 6}], "outro": {"seconds": 2.0}, "audio": {"policy": "mute"}})
        rep = self.check(8.0, audio=False); self.assertFalse(rep["end_card"], "no handle and no library track: nothing to write on it")

    def tail_volume(self, ss):
        r = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(ss), "-i", os.path.join(self.D, "final_reel_9x16.mp4"), "-vn", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
        m = re.search(r"mean_volume:\s*(-?[0-9.]+) dB", r.stderr); return float(m.group(1)) if m else -91.0

    def test_the_footage_sound_stays_and_steps_back_under_a_voiceover(self):
        """Even when the footage is rated speech-like (music can fool that guess), its sound is kept: the owner supplies footage with background music and no narration."""
        self.prep(voice=True, plan={"segments": [{"start": 1, "end": 9}], "audio": {"policy": "keep"}, "quote": {"show": False}})
        json.dump({"has_audio": True, "has_speech": True}, open(os.path.join(self.D, "audio.json"), "w"))
        rep = self.check(8.0); self.assertEqual((rep["footage_sound"], rep["ducked"]), ("keep", True))
        kept = self.tail_volume(6.5)   # the voice (5 s from 0.4) is over: only the footage sound is left
        json.dump({"segments": [{"start": 1, "end": 9}], "audio": {"policy": "mute"}, "quote": {"show": False}}, open(os.path.join(self.D, "edl.json"), "w"))
        self.check(8.0); self.assertGreater(kept, self.tail_volume(6.5) + 10, "kept footage sound is audible after the voice; muted is silence")

    def test_footage_sound_follows_the_plan_under_a_voiceover(self):
        self.prep(voice=True); rep = self.check(8.0); self.assertEqual((rep["footage_sound"], rep["ducked"]), ("ambient_low", True))

    def test_a_quote_the_footage_already_shows_is_not_drawn_again(self):
        self.prep(plan={"segments": [{"start": 0, "end": 6}], "audio": {"policy": "mute"}, "quote": {"show": False}})
        rep = self.check(6.0, audio=False); self.assertEqual((rep["quote_lines"], rep["layers"]), (0, 0), "no scrim either: nothing is drawn")

    def test_a_voice_longer_than_the_reel_stretches_the_end_card(self):
        self.prep(plan={"segments": [{"start": 0, "end": 4}], "audio": {"policy": "mute"}})
        ff("-f", "lavfi", "-i", "sine=frequency=200:duration=8", os.path.join(self.D, "voiceover.mp3"))
        rep = self.check(9.0)   # 0.4 s before the voice + 8 s of voice + 0.6 s after
        self.assertAlmostEqual(rep["outro_s"], 5.0, delta=0.05)

    def test_the_end_card_comes_after_a_long_voice_and_the_quote_never_overlaps_it(self):
        import reel_render as R, reel_edl as E
        self.prep(plan={"segments": [{"start": 0, "end": 4}], "outro": {"seconds": 2.0}, "audio": {"policy": "mute"}, "quote": {"start": 0.5}})
        ff("-f", "lavfi", "-i", "sine=frequency=200:duration=8", os.path.join(self.D, "voiceover.mp3"))
        edl = E.validate(json.load(open(os.path.join(self.D, "edl.json"))), 14.0); self.assertTrue(R.fit_voice(self.D, edl))
        self.assertEqual((edl["outro"]["extra"], edl["outro"]["seconds"]), (5.0, 7.0)); self.assertEqual(edl["seconds"], 11.0)   # 4 s of footage, held 5 s for the voice, then a 2 s card
        cues, _ = R.quote_cues(self.D, edl, 11.0 - 2.0)
        self.assertTrue(all(b <= 9.0 + 1e-6 for _, _, b in cues), "no quote line runs into the end card")
        rep = self.check(11.0, audio=True); self.assertEqual(rep["outro_s"], 7.0)

    def test_no_voice_no_music_still_renders(self):
        self.prep(plan={"segments": [{"start": 0, "end": 6}], "audio": {"policy": "mute"}})
        os.remove(os.path.join(self.D, "quote.json")); json.dump({"lines": []}, open(os.path.join(self.D, "quote.json"), "w"))
        import reel_render as R
        R.main("reel-001")
        w, h, codec, dur, has_a = probe(os.path.join(self.D, "final_reel_9x16.mp4"))
        self.assertEqual((w, h), (1080, 1920)); self.assertFalse(has_a)

    def test_music_outside_the_library_is_refused(self):
        self.prep(plan={"segments": [{"start": 0, "end": 6}], "audio": {"music": {"slug": "song-009", "file": "final.mp3"}}})
        import reel_render as R
        with self.assertRaises(SystemExit) as cm: R.main("reel-001")
        self.assertIn("not in the NAVAAN library", str(cm.exception))

    def test_owner_upload_wins_over_the_library(self):
        self.prep(); ff("-f", "lavfi", "-i", "sine=frequency=500:duration=20", os.path.join(self.D, "music_src.mp3"))
        rep = self.check(8.0); self.assertEqual(rep["music"], "owner upload")


class Handle(Env):
    def cfgfile(self, d):
        json.dump(d, open(os.path.join(self.tmp.name, "navaan.config.json"), "w"))

    def test_no_reel_account_never_shows_the_music_handle(self):
        self.cfgfile({"publish": {"instagram_handle": "@navaan_p5l"}, "accounts": {"inspiration": {"instagram_handle": "x"}}})
        import reel_render as R
        self.assertEqual(R.account_handle(), "")

    def test_reel_account_handle_is_used(self):
        self.cfgfile({"publish": {"instagram_handle": "@navaan_p5l"}, "accounts": {"reel": {"instagram_handle": "my.reels"}}})
        import reel_render as R
        self.assertEqual(R.account_handle(), "@my.reels")


@unittest.skipUnless(HAVE_FF, "ffmpeg not installed")
class Pipeline(unittest.TestCase):
    """The real orchestrator walks a reel from the upload to the final-cut approval: script steps run as subprocesses, Claude steps are stood in for by writing their files."""
    def test_a_reel_walks_through_its_gates_in_order(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); os.environ["NAVAAN_ROOT"] = tmp.name
        import navaan, new_song, reel_upload, io
        slug = new_song.create(None, "reel", "a quiet walk"); self.assertEqual(slug, "reel-001")
        D = os.path.join(tmp.name, "songs", slug)
        self.assertEqual(navaan.plan(slug)[1], {"type": "run", "step": "ingest"})
        # the upload route's job, then the ingest step through the orchestrator
        raw = os.path.join(tmp.name, "clip.mp4")
        ff("-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=10", "-f", "lavfi", "-i", "anoisesrc=d=10:c=pink:a=0.05", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", raw)
        data = open(raw, "rb").read(); reel_upload.save(io.BytesIO(data), len(data), D, "clip.mp4")
        self.assertEqual(navaan.run(slug, retries=0), 0); self.assertFalse(os.path.exists(os.path.join(D, ".cache", "raw.mp4")), "the original is gone")
        self.assertEqual(navaan.plan(slug)[1], {"type": "run", "step": "direct"})
        # Claude's step: its files appear; the quote is approved before anything else moves
        for n, v in (("scenes.json", {"summary": "x", "segments": []}), ("copy_options.json", {"quotes": []}),
                     ("quote.json", {"text": "Slow down.", "lines": ["Slow down."], "author": "", "kind": "original"}),
                     ("edl.json", {"segments": [{"start": 0, "end": 6}], "audio": {"policy": "ambient_low"}, "quote": {"start": 1.5}})):
            json.dump(v, open(os.path.join(D, n), "w"))
        open(os.path.join(D, "title.txt"), "w").write("A quiet walk\n")
        self.assertEqual(navaan.plan(slug)[1], {"type": "gate", "step": "direct", "gate": "quote"})
        navaan.set_gate(slug, "quote", True, "test")
        json.dump({"verdict": "clear", "safe_to_publish": True}, open(os.path.join(D, "originality.json"), "w"))
        self.assertEqual(navaan.plan(slug)[1], {"type": "gate", "step": "originality", "gate": "originality"}); navaan.set_gate(slug, "originality", True, "test")
        self.assertEqual(navaan.plan(slug)[1], {"type": "run", "step": "edit_check"}); self.assertEqual(navaan.run(slug, retries=0), 0)
        self.assertEqual(navaan.plan(slug)[1], {"type": "gate", "step": "edit_check", "gate": "edit_plan"}); navaan.set_gate(slug, "edit_plan", True, "test")
        self.assertEqual(navaan.plan(slug)[1], {"type": "run", "step": "render"}, "no ElevenLabs key here, so no narration step"); self.assertEqual(navaan.run(slug, retries=0), 0)
        self.assertEqual(probe(os.path.join(D, "final_reel_9x16.mp4"))[:3], (1080, 1920, "h264"))
        self.assertEqual(navaan.plan(slug)[1], {"type": "run", "step": "critique"})
        json.dump({"verdict": "pass", "summary": "ok", "fixes": []}, open(os.path.join(D, "critique.json"), "w"))
        self.assertEqual(navaan.plan(slug)[1], {"type": "gate", "step": "critique", "gate": "media"})
        # an edit to the approved plan asks for a new approval, and the plan is checked again
        e = json.load(open(os.path.join(D, "edl.json"))); e["segments"][0]["end"] = 5; json.dump(e, open(os.path.join(D, "edl.json"), "w"))
        rows = {r["id"]: r for r in navaan.plan(slug)[0]}
        self.assertFalse(rows["edit_check"]["done"], "the checked plan is stale once edl.json changes")


if __name__ == "__main__":
    unittest.main()
