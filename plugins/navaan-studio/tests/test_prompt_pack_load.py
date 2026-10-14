"""A song without a prompt pack must still open: load() answers None instead of exiting. Run: python3 -W ignore -m unittest test_prompt_pack_load"""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import prompt_pack as PP
import navaan_common as C


class Load(unittest.TestCase):
    def test_missing_pack_is_none_not_an_exit(self):
        with tempfile.TemporaryDirectory() as d: self.assertIsNone(PP.load(d))

    def test_saved_pack_is_returned(self):
        with tempfile.TemporaryDirectory() as d:
            json.dump({"prompts": ["a"]}, open(os.path.join(d, "prompt_pack.json"), "w"))
            self.assertEqual(PP.load(d), {"prompts": ["a"]})


class LoadJson(unittest.TestCase):
    def test_default_none_means_none(self):
        self.assertIsNone(C.load_json("/nonexistent/x.json", default=None))

    def test_other_defaults_still_returned(self):
        self.assertEqual(C.load_json("/nonexistent/x.json", default={}), {}); self.assertEqual(C.load_json("/nonexistent/x.json", default=[1]), [1])

    def test_no_default_still_exits_with_the_path(self):
        with self.assertRaises(SystemExit) as e: C.load_json("/nonexistent/x.json")
        self.assertIn("/nonexistent/x.json", str(e.exception))


if __name__ == "__main__":
    unittest.main()
