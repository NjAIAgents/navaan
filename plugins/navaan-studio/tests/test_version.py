"""One release version everywhere, and a changelog that matches it (deploy/bump-version.py keeps them in step; this fails when someone edits one by hand)."""
import json, os, re, subprocess, sys, tempfile, shutil, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))


def ver(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f: return json.load(f)


class Version(unittest.TestCase):
    def test_every_manifest_carries_the_same_version(self):
        v = ver("plugins", "navaan-studio", ".claude-plugin", "plugin.json")["version"]
        self.assertRegex(v, r"^\d+\.\d+\.\d+$")
        self.assertEqual(ver(".claude-plugin", "marketplace.json")["plugins"][0]["version"], v)
        self.assertEqual(ver("plugins", "navaan-studio", "web", "package.json")["version"], v)
        self.assertEqual(ver("plugins", "navaan-studio", "web", "package-lock.json")["version"], v)

    def test_the_changelog_names_that_version_as_the_latest_release(self):
        v = ver("plugins", "navaan-studio", ".claude-plugin", "plugin.json")["version"]
        with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f: cl = f.read()
        self.assertIn("## [Unreleased]", cl)
        heads = re.findall(r"^## \[(\d+\.\d+\.\d+)\]( - \d{4}-\d\d-\d\d)?", cl, re.M)
        self.assertEqual(heads[0][0], v, "the newest released heading in CHANGELOG.md must be the plugin version")
        for ver_, date in heads[:-1]: self.assertTrue(date, f"release {ver_} needs a date")   # only the oldest (0.1.0) predates the dates
        self.assertEqual([h[0] for h in heads], sorted((h[0] for h in heads), key=lambda s: tuple(map(int, s.split("."))), reverse=True), "releases are newest first")
        for h in heads: self.assertIn(f"[{h[0]}]: https://github.com/NjAIAgents/navaan/", cl)

    def test_the_portal_reports_the_plugin_version(self):
        import navaan_ui as U
        self.assertEqual(U.app_version(), ver("plugins", "navaan-studio", ".claude-plugin", "plugin.json")["version"])


class Bump(unittest.TestCase):
    """The bump script on a scratch copy of the files it edits."""
    FILES = ("CHANGELOG.md", "plugins/navaan-studio/.claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "plugins/navaan-studio/web/package.json",
             "plugins/navaan-studio/web/package-lock.json", "deploy/bump-version.py")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        for f in self.FILES:
            d = os.path.join(self.tmp.name, f); os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy(os.path.join(ROOT, f), d)

    def run_bump(self, *a):
        return subprocess.run([sys.executable, os.path.join(self.tmp.name, "deploy", "bump-version.py"), *a], capture_output=True, text=True)

    def blank_unreleased(self):
        p = os.path.join(self.tmp.name, "CHANGELOG.md"); s = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8").write(re.sub(r"(## \[Unreleased\]\n)(.*?)(?=^## \[)", "\\1\n", s, count=1, flags=re.S | re.M))

    def test_an_empty_unreleased_section_is_refused(self):
        self.blank_unreleased(); r = self.run_bump("9.9.9"); self.assertNotEqual(r.returncode, 0); self.assertIn("empty", r.stdout + r.stderr)

    def test_bump_moves_unreleased_into_the_release_and_updates_every_file(self):
        p = os.path.join(self.tmp.name, "CHANGELOG.md"); s = open(p, encoding="utf-8").read()
        # the real [Unreleased] already has entries in this repo: replace the section body with a known one
        s = re.sub(r"(## \[Unreleased\]\n)(.*?)(?=^## \[)", "\\1\n### Added\n- A thing.\n\n", s, count=1, flags=re.S | re.M)
        open(p, "w", encoding="utf-8").write(s)
        r = self.run_bump("9.9.9", "--date", "2030-01-02"); self.assertEqual(r.returncode, 0, r.stderr)
        cl = open(p, encoding="utf-8").read()
        self.assertRegex(cl, r"## \[Unreleased\]\n\n## \[9\.9\.9\] - 2030-01-02\n\n### Added\n- A thing\.")
        self.assertIn("[9.9.9]: https://github.com/NjAIAgents/navaan/compare/", cl); self.assertIn("compare/v9.9.9...HEAD", cl)
        for f in ("plugins/navaan-studio/.claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
            self.assertIn('"9.9.9"', open(os.path.join(self.tmp.name, f)).read(), f)
        for f in ("package.json", "package-lock.json"): self.assertEqual(json.load(open(os.path.join(self.tmp.name, "plugins/navaan-studio/web", f)))["version"], "9.9.9")
        self.assertIn("git tag -a v9.9.9", r.stdout)

    def test_a_bad_version_is_refused(self):
        self.assertNotEqual(self.run_bump("v1").returncode, 0); self.assertNotEqual(self.run_bump().returncode, 0)


if __name__ == "__main__":
    unittest.main()
