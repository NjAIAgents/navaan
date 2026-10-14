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


if __name__ == "__main__":
    unittest.main()
