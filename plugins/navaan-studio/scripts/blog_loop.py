#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: the blog's claim checks (NAV-72) and the bounded fact-check loop back to the writer (NAV-73).

  blog_loop.py factcheck <slug>

Reads factcheck.json (written by the blog-factcheck skill for the current drafts). A pass ends the loop. A fail writes fix_notes.md with the failing
claims, which makes the writer step due again (its drafts are older than the notes), and counts the round in factcheck_rounds.json.
After MAX_ROUNDS rewrites that still fail, it stops: needs_you.txt names the claims and the run waits for the owner (exit 5), so no third rewrite runs.
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C

MAX_ROUNDS = 2   # rewrites the fact check may ask for before a person decides (owner, 2026-10-19)
DRAFTS = ("devto.md", "linkedin_article.md")
MARK = "draft.json"   # written by the writer when it finishes; the editor and humanizer change the drafts but not this, so their edits do not restart the fact check


def _p(D, n): return os.path.join(D, n)
def _mt(D, n): return os.path.getmtime(_p(D, n)) if os.path.exists(_p(D, n)) else 0.0


def claims_errors(data):
    """What is wrong with a claims.json document, or []: {"claims": [{"id", "text", "source_url", "evidence", "primary": bool}]}, at least one claim, unique ids, http(s) sources."""
    cl = (data or {}).get("claims") if isinstance(data, dict) else None
    if not isinstance(cl, list) or not cl: return ["claims.json needs a non-empty \"claims\" list"]
    errs, seen = [], set()
    for i, c in enumerate(cl):
        if not isinstance(c, dict): errs.append(f"claim {i + 1} is not an object"); continue
        cid = str(c.get("id") or "").strip()
        if not cid or cid in seen: errs.append(f"claim {i + 1}: missing or repeated id")
        seen.add(cid)
        if not str(c.get("text") or "").strip(): errs.append(f"claim {cid or i + 1}: no text")
        if not str(c.get("source_url") or "").startswith(("https://", "http://")): errs.append(f"claim {cid or i + 1}: source_url must be a web address")
        if not isinstance(c.get("primary"), bool): errs.append(f"claim {cid or i + 1}: primary must be true or false")
    return errs


def claims_ok(D): return not claims_errors(C.load_json(_p(D, "claims.json"), default=None))


def checked(D):
    """factcheck.json is about the writer's latest drafts."""
    return all(os.path.exists(_p(D, n)) for n in (*DRAFTS, MARK)) and _mt(D, "factcheck.json") >= _mt(D, MARK)


def passed(D):
    return checked(D) and (C.load_json(_p(D, "factcheck.json"), default={}) or {}).get("verdict") == "pass"


def fix_pending(D):
    """Fix notes newer than the drafts: the writer has to run again."""
    return os.path.exists(_p(D, "fix_notes.md")) and _mt(D, "fix_notes.md") > _mt(D, MARK)


def rounds(D):
    """Rewrites asked for since the outline was last written (a new outline starts the count again)."""
    r = C.load_json(_p(D, "factcheck_rounds.json"), default={}) or {}
    return int(r.get("rounds", 0)) if _mt(D, "factcheck_rounds.json") >= _mt(D, "outline.md") else 0


def failing(D):
    return [c for c in (C.load_json(_p(D, "factcheck.json"), default={}) or {}).get("claims") or [] if c.get("status") != "verified"]


def factcheck(slug):
    D = C.song_dir(slug)
    if not checked(D): print("navaan: there is no fact check for the current drafts yet"); return 2
    if passed(D):
        ny = _p(D, "needs_you.txt")
        if os.path.exists(ny) and open(ny, encoding="utf-8").read().startswith("The fact check"): os.remove(ny)   # the owner's fix worked: no longer waiting
        print("fact check passed"); return 0
    bad = failing(D); n = rounds(D)
    lines = [f"- {c.get('id', '?')}: {c.get('text', '')} ({c.get('status', 'unverified')}: {c.get('note', '')})" for c in bad] or ["- the fact check failed without naming a claim; read factcheck.json"]
    if n >= MAX_ROUNDS:
        msg = f"The fact check still fails after {MAX_ROUNDS} rewrites. Fix these claims in the drafts (or drop them), then press Run again:\n" + "\n".join(lines)
        with open(_p(D, "needs_you.txt"), "w", encoding="utf-8") as f: f.write(msg + "\n")
        print(msg); return 5
    with open(_p(D, "fix_notes.md"), "w", encoding="utf-8") as f:
        f.write(f"# Fact check, round {n + 1} of {MAX_ROUNDS}\n\nThese claims could not be verified. Correct each against its source, or remove it:\n\n" + "\n".join(lines) + "\n")
    with open(_p(D, "factcheck_rounds.json"), "w", encoding="utf-8") as f: json.dump({"rounds": n + 1, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f)
    print(f"fact check failed: {len(bad)} claim(s); the writer runs again (round {n + 1} of {MAX_ROUNDS})"); return 0


def main(a):
    if len(a) != 2 or a[0] != "factcheck": sys.exit(__doc__)
    sys.exit(factcheck(a[1]))


if __name__ == "__main__":
    main(sys.argv[1:])
