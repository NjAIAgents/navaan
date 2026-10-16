#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: set the release version everywhere it lives, and turn the changelog's [Unreleased] section into the release.

  python3 deploy/bump-version.py 0.6.0 [--date 2026-10-20]

Edits plugins/navaan-studio/.claude-plugin/plugin.json, .claude-plugin/marketplace.json, plugins/navaan-studio/web/package.json (and its lock file) and CHANGELOG.md.
Prints the git commands to review, commit and tag. It never runs git: the human decides what is committed and tagged.
"""
import datetime, json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def edit(path, fn):
    p = os.path.join(ROOT, path)
    with open(p, encoding="utf-8") as f: s = f.read()
    out = fn(s)
    if out == s: sys.exit(f"bump-version: nothing changed in {path}")
    with open(p, "w", encoding="utf-8") as f: f.write(out)
    print("updated", path)


def main(argv):
    if not argv or not re.fullmatch(r"\d+\.\d+\.\d+", argv[0]): sys.exit("usage: bump-version.py X.Y.Z [--date YYYY-MM-DD]")
    v = argv[0]; date = argv[argv.index("--date") + 1] if "--date" in argv else datetime.date.today().isoformat()
    cl = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
    old = re.search(r"^## \[(\d+\.\d+\.\d+)\]", cl, re.M).group(1)
    if v == old: sys.exit(f"bump-version: already at {v}")
    body = re.search(r"## \[Unreleased\]\n(.*?)(?=^## \[)", cl, re.S | re.M).group(1).strip()
    if not body: sys.exit("bump-version: [Unreleased] in CHANGELOG.md is empty, so there is nothing to release (use /changelog or write the entries first)")
    for path in ("plugins/navaan-studio/.claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
        edit(path, lambda s: re.sub(r'("version":\s*")[^"]+(")', rf"\g<1>{v}\g<2>", s, count=1))
    for path in ("plugins/navaan-studio/web/package.json", "plugins/navaan-studio/web/package-lock.json"):
        def bump(s, path=path):
            d = json.loads(s); d["version"] = v
            if "packages" in d and "" in d["packages"]: d["packages"][""]["version"] = v
            return json.dumps(d, indent=2) + "\n"
        edit(path, bump)
    def log(s):
        s = s.replace("## [Unreleased]\n", f"## [Unreleased]\n\n## [{v}] - {date}\n", 1)
        s = s.replace(f"[Unreleased]: https://github.com/NjAIAgents/navaan/compare/v{old}...HEAD", f"[Unreleased]: https://github.com/NjAIAgents/navaan/compare/v{v}...HEAD\n[{v}]: https://github.com/NjAIAgents/navaan/compare/v{old}...v{v}")
        return s
    edit("CHANGELOG.md", log)
    print(f"\nReview with: git diff\nThen, when you are happy:\n  git add -A && git commit -m \"Release {v}\"\n  git tag -a v{v} -m \"NAVAAN Studio {v}\"      # after the release merges to main, on the merge commit\n  git push origin v{v}")


if __name__ == "__main__":
    main(sys.argv[1:])
