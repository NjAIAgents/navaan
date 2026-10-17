import os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import navaan as N


class GateWait(unittest.TestCase):
    def open(self, approvals, nxt, g="visuals_mode"):
        with mock.patch.object(N, "meta", lambda s: {"approvals": approvals}), mock.patch.object(N, "plan", lambda s: ([], nxt)):
            return N._gate_open("s", g)

    def test_it_waits_while_the_gate_is_the_next_thing_and_unapproved(self):
        self.assertTrue(self.open({}, {"type": "gate", "gate": "visuals_mode", "step": "pictures"}))

    def test_an_approval_ends_the_wait(self):
        self.assertFalse(self.open({"visuals_mode": {"at": "x"}}, {"type": "gate", "gate": "visuals_mode"}))

    def test_a_gate_settled_without_an_approval_ends_the_wait(self):   # song-007: visuals chosen, the run kept waiting for an approval that never comes
        self.assertFalse(self.open({}, {"type": "run", "step": "pictures"}))
        self.assertFalse(self.open({}, {"type": "gate", "gate": "credits", "step": "pictures"}))
        self.assertFalse(self.open({}, {"type": "done"}))


if __name__ == "__main__":
    unittest.main()
