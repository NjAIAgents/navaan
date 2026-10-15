"""The caption package check starts Python once, not on every dashboard load. Run: python3 -W ignore -m unittest test_have_pkgs_cache"""
import os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import setup_captions as SC


class Cache(unittest.TestCase):
    def setUp(self): SC._PKGS_OK = False

    def test_yes_is_remembered(self):
        with mock.patch.object(SC.os.path, "exists", return_value=True), mock.patch.object(SC.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            self.assertTrue(all(SC.have_pkgs() for _ in range(12)))
            self.assertEqual(run.call_count, 1)

    def test_no_is_rechecked(self):
        with mock.patch.object(SC.os.path, "exists", return_value=True), mock.patch.object(SC.subprocess, "run", return_value=mock.Mock(returncode=1)) as run:
            self.assertFalse(SC.have_pkgs()); self.assertFalse(SC.have_pkgs())
            self.assertEqual(run.call_count, 2)


if __name__ == "__main__": unittest.main()
