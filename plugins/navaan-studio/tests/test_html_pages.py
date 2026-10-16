"""Guards for the two HTML pages: balanced CSS braces (an unbalanced one silently swallows later rules) and parseable scripts.
Run: python3 -W ignore -m unittest test_html_pages"""
import os, re, subprocess, unittest

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")


class Pages(unittest.TestCase):
    def read(self, name): return open(os.path.join(HERE, name), encoding="utf-8").read()

    def test_css_braces_balance(self):
        for n in ("auth.html", "ui.html"):
            css = re.search(r"<style>(.*?)</style>", self.read(n), re.S).group(1)
            self.assertEqual(css.count("{"), css.count("}"), n)

    def test_media_blocks_are_closed_where_they_start(self):
        """Every @media line must end its block on the same line or be followed by rules that close it: a stray opener shows up as a net depth above 0 at the end of a rule line."""
        css = re.search(r"<style>(.*?)</style>", self.read("auth.html"), re.S).group(1)
        depth = 0
        for line in css.splitlines():
            depth += line.count("{") - line.count("}")
            self.assertGreaterEqual(depth, 0)
            self.assertLessEqual(depth, 0, "a block is still open at the end of: " + line[:80])

    def test_scripts_parse(self):
        node = subprocess.run(["which", "node"], capture_output=True, text=True).stdout.strip()
        if not node: self.skipTest("node is not installed")
        for n in ("auth.html", "ui.html"):
            for i, m in enumerate(re.finditer(r"<script>(.*?)</script>", self.read(n), re.S)):
                r = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0,'utf8'))"], input=m.group(1), capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f"{n} script {i}: {r.stderr[:200]}")

    def test_public_legal_pages_exist_and_say_what_google_checks(self):
        pv, tm = self.read("privacy.html"), self.read("terms.html")
        for needle in ("Google API Services User Data Policy", "Limited Use", "YouTube", "revoke"): self.assertIn(needle, pv)
        self.assertIn("/privacy", tm); self.assertNotIn("@gmail.com", pv + tm)  # no personal email on a public page

    def test_the_credit_is_navaan_studio_not_njlabs(self):
        for n in ("auth.html", "ui.html", "privacy.html", "terms.html"):
            page = self.read(n); self.assertNotRegex(page.upper(), "NJ ?LABS", n)
        for n in ("auth.html", "ui.html"): self.assertIn("&copy; <span id=\"cry\"></span> NAVAAN Studio. All rights reserved.", self.read(n))
        for n in ("privacy.html", "terms.html"): self.assertIn("NAVAAN Studio. All rights reserved.", self.read(n))


if __name__ == "__main__":
    unittest.main()
