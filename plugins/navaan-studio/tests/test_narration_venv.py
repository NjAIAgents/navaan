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


if __name__ == "__main__":
    unittest.main()
