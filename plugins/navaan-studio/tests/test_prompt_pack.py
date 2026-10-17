import os, sys, json, unittest, unittest.mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import prompt_pack as P


class Singer(unittest.TestCase):
    def test_the_singer_is_read_from_the_style_and_a_note_tells_the_directors(self):
        for style, want in (("male vocals, soft hindi pop", "male"), ("Female vocalist, indie", "female"), ("baritone, slow ballad", "male"), ("soprano choir", "female"), ("duet, male and female vocals", ""), ("soft piano pop", ""), ("", ""), (None, "")):
            self.assertEqual(P.singer(style), want, style)
        self.assertIn("The main person in the film is a man; never make the main person a woman", P.voice_note("male vocals"))
        self.assertIn("never make the main person a man", P.voice_note({"style": "female vocals"}))
        self.assertIn("do not assume it", P.voice_note("soft piano"))

    def test_the_artists_own_voice_from_the_profile_is_the_fallback_when_the_style_does_not_say(self):
        with unittest.mock.patch.object(P.C, "cfg", lambda k, d=None: "male" if k == "music.voice" else d):
            self.assertEqual(P.who_sings("soft pop, cinematic"), "male"); self.assertIn("the singer is a man", P.voice_note("soft pop"))   # NAVAAN sings: no need to say it in every style
            self.assertEqual(P.who_sings("female vocals, indie"), "female")   # a song that says otherwise wins
        for v in ("duet", "mixed", "", None):
            with unittest.mock.patch.object(P.C, "cfg", lambda k, d=None, v=v: v if k == "music.voice" else d): self.assertEqual(P.who_sings("soft pop"), "", v)   # not one singer: nothing assumed

    def test_the_story_directors_brief_carries_the_voice_note_and_no_longer_asks_for_a_beloved_in_every_love_song(self):
        ctx = {"title": "T", "style": "male vocals, ballad", "sections": [{"label": "Verse", "lines": ["a"], "start": 0, "end": 10}]}
        text = P.build_prompt(ctx, [{"section": "Verse", "part": 1, "of": 1, "lines": ["a"]}])
        self.assertIn("the singer is a man", text); self.assertNotIn("<<voice_note>>", text)
        self.assertIn("Do not invent a romantic partner for a song that is not about one", text); self.assertNotIn("For a love or longing song write the main person first", text)


class T(unittest.TestCase):
    def test_count(self):
        self.assertEqual(P.default_count(60), 6)
        self.assertEqual(P.default_count(200), 20)
        self.assertEqual(P.default_count(900), 24)

    def test_allocate(self):
        secs = [{"label": "A", "lines": ["x"], "start": 0, "end": 30}, {"label": "B", "lines": ["y"], "start": 30, "end": 150}, {"label": "C", "lines": ["z"], "start": 150, "end": 160}]
        sl = P.allocate(secs, 12)
        self.assertEqual(len(sl), 12)
        self.assertEqual({s["section"] for s in sl}, {"A", "B", "C"})

    def test_parse(self):
        st, ps = P.parse('text {"style_line": "warm", "prompts": ["a", "b"]} more', 2)
        self.assertEqual((st, ps), ("warm", ["a", "b"]))
        with self.assertRaises(ValueError): P.parse('{"style_line": "w", "prompts": ["a"]}', 2)
        with self.assertRaises(ValueError): P.parse("no json", 1)

    def test_parse_full_takes_scene_objects_and_motion(self):
        r = P.parse_full('{"concept": "c", "character": "a woman in a mustard shawl", "style_line": "warm", "prompts": [{"scene": "a chai stall", "motion": "steam from the glass"}, {"scene": "a bus stop", "motion": "none"}]}', 2)
        self.assertEqual(r["concept"], "c"); self.assertEqual(r["character"], "a woman in a mustard shawl")
        self.assertEqual([i["prompt"] for i in r["items"]], ["a chai stall", "a bus stop"])
        self.assertEqual([i["motion"] for i in r["items"]], ["steam from the glass", ""])
        with self.assertRaises(ValueError): P.parse_full('{"style_line": "w", "prompts": [{"scene": "a", "motion": ""}]}', 2)

    def test_director_prompt_is_emotion_first_with_full_lyrics(self):
        ctx = {"title": "T", "style": "romantic ghazal", "scene_override": "",
               "sections": [{"label": "Verse 1", "lines": ["tum samne thin", "main chup raha"]}, {"label": "Chorus", "lines": ["khat jo kabhi likha nahi"]}]}
        sl = [{"section": "Verse 1", "part": 1, "of": 1, "lines": ["tum samne thin"]}]
        p = P.build_prompt(ctx, sl)
        for w in ("emotion", "character", "motion", "FULL LYRICS", "[Chorus]", "khat jo kabhi likha nahi", "romantic ghazal", "At most 3 of the 1 frames", "No markets", "exactly 1 prompts"):
            self.assertIn(w, p)

    def test_parse_reads_emotion_as_concept(self):
        r = P.parse_full('{"emotion": "longing", "character": "c", "style_line": "s", "prompts": [{"scene": "a", "motion": "none"}]}', 1)
        self.assertEqual(r["concept"], "longing")


class Roles(unittest.TestCase):
    CTX = {"title": "T", "style": "romantic ghazal", "scene_override": "monsoon", "camera_override": "very slow",
           "sections": [{"label": "Verse 1", "lines": ["a", "b"], "start": 0, "end": 40}]}
    SL = [{"section": "Verse 1", "part": 1, "of": 2, "lines": ["a"]}, {"section": "Verse 1", "part": 2, "of": 2, "lines": ["b"]}]

    def test_look_prompt_has_lyrics_and_notes(self):
        p = P.build_look_prompt(self.CTX)
        for w in ("style_line", "camera_style", "romantic ghazal", "monsoon", "very slow", "[Verse 1]"): self.assertIn(w, p)
        self.assertNotIn("<<", p)

    def test_story_prompt_has_no_camera_or_look_job(self):
        p = P.build_prompt(self.CTX, self.SL, look={"style_line": "warm dusk film look"})
        self.assertIn("warm dusk film look", p); self.assertIn("exactly 2 prompts", p); self.assertNotIn("<<", p)
        self.assertNotIn("push_in", p)

    def test_camera_prompt_lists_scenes_and_moves(self):
        p = P.build_camera_prompt(self.CTX, self.SL, [{"prompt": "scene one"}, {"prompt": "scene two"}], {"camera_style": "slow"})
        for w in ("scene one", "scene two", "push_in", "exactly 2 moves", "about 20.0 s"): self.assertIn(w, p)
        self.assertNotIn("<<", p)

    def test_parse_camera(self):
        r = P.parse_camera('{"moves": [{"camera": "Push In", "focus": [0.3, 1.4]}, {"camera": "zoom"}]}', 2)
        self.assertEqual(r[0], {"camera": "push_in", "focus": [0.3, 1.0]}); self.assertEqual(r[1], {"camera": "", "focus": None})
        with self.assertRaises(ValueError): P.parse_camera('{"moves": []}', 2)

    def test_make_runs_three_roles_in_order(self):
        import tempfile, shutil
        calls = []
        def fake(prompt):
            if "ART DIRECTOR" in prompt: calls.append("look"); return '{"style_line": "warm", "palette": "p", "camera_style": "slow"}'
            if "STORY DIRECTOR" in prompt: calls.append("story"); return '{"emotion": "e", "character": "c", "prompts": [{"scene": "s1", "motion": "rain"}, {"scene": "s2"}]}'
            calls.append("camera"); return '{"moves": [{"camera": "push_in", "focus": [0.5, 0.5]}, {"camera": "pull_out"}]}'
        orig = (P.shots_prep.build_context, P.allocate, P.C.song_dir)
        d = tempfile.mkdtemp()
        try:
            P.shots_prep.build_context = lambda D: dict(self.CTX, duration=40, sections=self.CTX["sections"])
            P.allocate = lambda secs, n: self.SL
            P.C.song_dir = lambda slug: d
            pk = P.make("x", 6, runner=fake)
        finally:
            P.shots_prep.build_context, P.allocate, P.C.song_dir = orig; shutil.rmtree(d, ignore_errors=True)
        self.assertEqual(calls, ["look", "story", "camera"])
        self.assertEqual(pk["style_line"], "warm"); self.assertEqual(pk["prompts"][0]["camera"], "push_in"); self.assertEqual(pk["prompts"][1]["camera"], "pull_out")


if __name__ == "__main__":
    unittest.main()
