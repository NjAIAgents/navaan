import os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import narration_sync as N
import setup_captions as S


class Venv(unittest.TestCase):
    def test_switches_when_outside_the_venv_even_if_the_python_file_is_the_same(self):
        # The server case: the venv python is a symlink to the system python, so sys.executable resolves to the same file.
        with mock.patch.object(S, "ready", return_value=True), mock.patch.object(N.os, "execv") as ex, mock.patch.object(N.sys, "prefix", "/usr/local"):
            N._again_in_venv(["insp-003"])
        ex.assert_called_once()
        self.assertEqual(ex.call_args[0][0], S.venv_python())

    def test_stays_when_already_in_the_venv(self):
        with mock.patch.object(S, "ready", return_value=True), mock.patch.object(N.os, "execv") as ex, mock.patch.object(N.sys, "prefix", S.VENV):
            N._again_in_venv(["insp-003"])
        ex.assert_not_called()

    def test_does_nothing_when_tools_are_missing(self):
        with mock.patch.object(S, "ready", return_value=False), mock.patch.object(N.os, "execv") as ex:
            N._again_in_venv(["insp-003"])
        ex.assert_not_called()

    def test_the_script_runs_again_in_the_caption_tools_first_even_when_the_system_python_has_numpy(self):
        # insp-005: numpy was there but onnxruntime was not, so the old check (numpy missing?) never switched, Whisper failed quietly and the lines were timed from pauses
        import navaan_common as C
        with mock.patch.object(N, "_again_in_venv", side_effect=SystemExit("switched")) as again, mock.patch.object(C, "song_dir", side_effect=AssertionError("went on in the wrong python")):
            with self.assertRaises(SystemExit) as c: N.main(["insp-003"])
        self.assertEqual(str(c.exception), "switched"); again.assert_called_once_with(["insp-003"])

    def test_a_fallback_to_pauses_says_so_in_the_log(self):
        import io, json, tempfile, navaan_common as C
        d = tempfile.mkdtemp(); json.dump({"lines": ["a b", "c d"], "language": "en"}, open(os.path.join(d, "quote.json"), "w"))
        out = io.StringIO()
        with mock.patch.object(N, "_again_in_venv"), mock.patch.object(C, "song_dir", lambda s: d), mock.patch.object(N, "sync", return_value={"method": "pauses", "cues": 2, "seconds": 9.0, "whisper_lines_failed": "No module named 'onnxruntime'"}), mock.patch("sys.stdout", out):
            self.assertEqual(N.main(["insp-003"]), 0)
        self.assertIn("WARNING: the lines were timed from pauses only", out.getvalue()); self.assertIn("onnxruntime", out.getvalue())
        out = io.StringIO()
        with mock.patch.object(N, "_again_in_venv"), mock.patch.object(C, "song_dir", lambda s: d), mock.patch.object(N, "sync", return_value={"method": "whisper-aligned", "cues": 2, "seconds": 9.0}), mock.patch("sys.stdout", out):
            N.main(["insp-003"])
        self.assertNotIn("WARNING", out.getvalue())   # a normal run says nothing extra


if __name__ == "__main__":
    unittest.main()
