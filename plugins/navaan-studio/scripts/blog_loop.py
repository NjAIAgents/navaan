#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: the blog's claim checks (NAV-72) and the bounded fact-check loop back to the writer (NAV-73).

  blog_loop.py factcheck <slug>
  blog_loop.py humanize-prep <slug>    keep the edited drafts in humanize_before/ before the humanizer rewrites them (NAV-74)
  blog_loop.py humanize-check <slug>   the humanizer may change how the drafts sound, not what they say (NAV-89): markers, numbers, links, code and front matter must be unchanged

Reads factcheck.json (written by the blog-factcheck skill for the current drafts). A pass ends the loop. A fail writes fix_notes.md with the failing
claims, which makes the writer step due again (its drafts are older than the notes), and counts the round in factcheck_rounds.json.
After MAX_ROUNDS rewrites that still fail, it stops: needs_you.txt names the claims and the run waits for the owner (exit 5), so no third rewrite runs.
"""
import os, sys, json, time, re, shutil
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


BEFORE = "humanize_before"


def humanized_ok(D):
    """humanize_check.json is about the humanizer's latest rewrite and found nothing wrong."""
    c = C.load_json(_p(D, "humanize_check.json"), default=None)
    return isinstance(c, dict) and c.get("ok") is True and _mt(D, "humanize_check.json") >= _mt(D, "humanize.json") >= _mt(D, BEFORE + "/" + DRAFTS[0])


def humanize_prep(slug):
    D = C.song_dir(slug); os.makedirs(_p(D, BEFORE), exist_ok=True)
    for n in DRAFTS:
        if not os.path.exists(_p(D, n)): print(f"navaan: {n} is missing; write and edit the drafts first"); return 2
        shutil.copyfile(_p(D, n), os.path.join(_p(D, BEFORE), n))
    print(f"kept the edited drafts in {BEFORE}/"); return 0


MARKER = re.compile(r"\[c\d+\]")
NUMBER = re.compile(r"\d[\d.,]*%?")
LINK = re.compile(r"https?://[^\s)>\]\"']+")
CODE = re.compile(r"```.*?```", re.S)
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
FRONT = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)


def _facts(text):
    """What a rewrite must not change: the claim markers, the numbers, the links, the code, the images (as multisets, so a number cannot move or double)."""
    body = FRONT.sub("", text, count=1); code = CODE.findall(body); prose = CODE.sub(" ", body)
    prose = IMAGE.sub(" ", prose)   # an image's address has digits of its own: it is compared as an image below
    return {"markers": sorted(MARKER.findall(body)), "numbers": sorted(n.rstrip(".,") for n in NUMBER.findall(MARKER.sub(" ", LINK.sub(" ", prose)))),
            "links": sorted(LINK.findall(body)), "code": code, "images": sorted(IMAGE.findall(body))}


def _front(text):
    m = FRONT.match(text)
    if not m: return None
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line: k, v = line.split(":", 1); out[k.strip()] = v.strip().strip("\"'")
    return out


def humanize_problems(before, after, devto=False):
    """What the rewrite changed that it may not, as sentences for the owner (empty when it only changed the sound)."""
    a, b = _facts(before), _facts(after); out = []
    for k, label in (("markers", "claim markers"), ("numbers", "numbers"), ("links", "links"), ("code", "code blocks"), ("images", "images")):
        if a[k] != b[k]:
            gone = [x for x in a[k] if x not in b[k]] if k != "code" else [x[:40] for x in a[k] if x not in b[k]]
            new = [x for x in b[k] if x not in a[k]] if k != "code" else [x[:40] for x in b[k] if x not in a[k]]
            out.append(f"the {label} changed" + (f"; missing: {', '.join(map(str, gone[:5]))}" if gone else "") + (f"; new: {', '.join(map(str, new[:5]))}" if new else ""))
    if devto:
        fa, fb = _front(before) or {}, _front(after)
        if fb is None: out.append("the dev.to front matter is gone")
        else:
            if fb.get("published", "").lower() != "false": out.append("front matter: published must stay false")
            tags = [t.strip() for t in fb.get("tags", "").split(",") if t.strip()]
            if len(tags) > 4 or any(not re.fullmatch(r"[a-z0-9]+", t) for t in tags): out.append("front matter: at most 4 tags, lowercase letters and digits only")
            if len(fb.get("description", "")) >= 160: out.append("front matter: the description must stay under 160 characters")
    wa, wb = len(before.split()), len(after.split())
    if wa and abs(wb - wa) > 0.25 * wa: out.append(f"the length changed from {wa} to {wb} words (more than 25%)")
    return out


def humanize_check(slug):
    D = C.song_dir(slug); problems = []
    for n in DRAFTS:
        if not os.path.exists(os.path.join(_p(D, BEFORE), n)) or not os.path.exists(_p(D, n)): print(f"navaan: {n} or its copy in {BEFORE}/ is missing"); return 2
        before = open(os.path.join(_p(D, BEFORE), n), encoding="utf-8").read(); after = open(_p(D, n), encoding="utf-8").read()
        problems += [f"{n}: {x}" for x in humanize_problems(before, after, devto=(n == "devto.md"))]
    with open(_p(D, "humanize_check.json"), "w", encoding="utf-8") as f: json.dump({"ok": not problems, "problems": problems, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f, indent=1)
    if problems:
        msg = "The humanizer changed what the posts say, not just how they sound. The text it started from is in humanize_before/; fix the drafts, or press Redo on the humanizer:\n" + "\n".join("- " + x for x in problems)
        with open(_p(D, "needs_you.txt"), "w", encoding="utf-8") as f: f.write(msg + "\n")
        print(msg); return 5
    ny = _p(D, "needs_you.txt")
    if os.path.exists(ny) and open(ny, encoding="utf-8").read().startswith("The humanizer"): os.remove(ny)
    print("the humanizer kept every fact, number, link, code block and marker"); return 0


def main(a):
    cmds = {"factcheck": factcheck, "humanize-prep": humanize_prep, "humanize-check": humanize_check}
    if len(a) != 2 or a[0] not in cmds: sys.exit(__doc__)
    sys.exit(cmds[a[0]](a[1]))


if __name__ == "__main__":
    main(sys.argv[1:])
