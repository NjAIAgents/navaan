"""NAV-13: sending an item back with a note (FR-023) -- no approval is kept, the note stays in the history, and an empty note or unknown gate is refused."""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401


class RequestChanges(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = self.tmp.name
        import navaan as N, navaan_common as C
        self.N = N; self.D = os.path.join(C.songs_root(), "s1"); os.makedirs(self.D)
        json.dump({"slug": "s1", "type": "music", "state": "drafted", "approvals": {"lyrics": {"at": "t", "via": "ui:owner"}}}, open(os.path.join(self.D, "meta.json"), "w"))

    def tearDown(self):
        os.environ.pop("NAVAAN_ROOT", None); self.tmp.cleanup()

    def test_the_approval_is_dropped_and_the_note_is_kept(self):
        self.N.request_changes("s1", "lyrics", "  the second   verse is too long ", "ui:owner")
        m = self.N.meta("s1")
        self.assertNotIn("lyrics", m["approvals"])
        self.assertTrue(m["history"][-1].endswith("changes requested at lyrics via ui:owner: the second verse is too long"))

    def test_a_note_and_a_known_gate_are_required(self):
        with self.assertRaises(SystemExit): self.N.request_changes("s1", "lyrics", "  ", "ui:owner")
        with self.assertRaises(SystemExit): self.N.request_changes("s1", "nope", "x", "ui:owner")
        self.assertIn("lyrics", self.N.meta("s1")["approvals"])   # a refusal changes nothing


    def test_revoking_an_approval_records_who_and_reopens_the_gate(self):
        self.N.set_gate("s1", "lyrics", True, "ui:owner"); self.assertIn("lyrics", self.N.meta("s1")["approvals"])
        self.N.set_gate("s1", "lyrics", False, "ui:owner")
        m = self.N.meta("s1"); self.assertNotIn("lyrics", m["approvals"]); self.assertTrue(m["history"][-1].endswith("gate lyrics revoked via ui:owner"))


if __name__ == "__main__":
    unittest.main()
