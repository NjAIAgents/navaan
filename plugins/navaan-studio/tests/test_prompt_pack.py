import os, sys, json, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import prompt_pack as P


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

    def test_director_prompt_asks_for_people_places_and_bans_cliches(self):
        ctx = {"title": "T", "style": "lo-fi", "scene_override": ""}
        sl = [{"section": "Verse 1", "part": 1, "of": 1, "lines": ["line one"]}]
        p = P.build_prompt(ctx, sl)
        for w in ("concept", "character", "motion", "street", "market", "lone bench by a river", "Never a close up of a face", "exactly 1 prompts"):
            self.assertIn(w, p)


if __name__ == "__main__":
    unittest.main()
