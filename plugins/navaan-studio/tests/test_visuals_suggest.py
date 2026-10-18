import os, sys, json, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import visuals_cfg as V


class Suggest(unittest.TestCase):
    def test_before_the_plan_exists_the_suggestion_is_a_starting_point_written_from_the_song(self):
        D = tempfile.mkdtemp(); open(os.path.join(D, "style.txt"), "w").write("country folk,\n melancholic male vocal")
        s = V.suggest(D)
        self.assertIn("slow pull out", s["camera"]); self.assertIn("country folk, melancholic male vocal", s["scene"])
        self.assertTrue(0 < len(s["camera"]) <= V.NOTE_MAX and 0 < len(s["scene"]) <= V.NOTE_MAX)

    def test_without_a_style_file_it_still_gives_a_usable_look(self):
        s = V.suggest(tempfile.mkdtemp()); self.assertTrue(s["scene"].startswith("Photorealistic cinematic stills that fit the song.")); self.assertNotIn("()", s["scene"])

    def test_once_the_plan_is_written_the_art_directors_own_look_and_camera_are_the_suggestion(self):
        D = tempfile.mkdtemp(); json.dump({"style_line": "Dusk, tungsten lamps, 35mm.", "look": {"style_line": "x", "camera_style": "Barely moving, ends on a pull out."}, "prompts": []}, open(os.path.join(D, "prompt_pack.json"), "w"))
        self.assertEqual(V.suggest(D), {"camera": "Barely moving, ends on a pull out.", "scene": "Dusk, tungsten lamps, 35mm."})

    def test_a_long_look_is_cut_to_what_a_note_may_hold_and_can_be_saved_back(self):
        D = tempfile.mkdtemp(); json.dump({"style_line": "w " * 900, "prompts": []}, open(os.path.join(D, "prompt_pack.json"), "w"))
        s = V.suggest(D); self.assertLessEqual(len(s["scene"]), V.NOTE_MAX)
        self.assertEqual(V.save(D, "own", "video", s["camera"], s["scene"], pictures_later=True)["scene"], s["scene"].strip())


if __name__ == "__main__":
    unittest.main()
