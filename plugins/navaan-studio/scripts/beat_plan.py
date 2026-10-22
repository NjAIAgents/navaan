#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-21
Last updated: 2026-10-21
Description: the picture plan of an inspiration short made with "a picture per beat" (NAV-145): which lines share a picture, what each picture shows, and the one look of the short.

  beat_plan.py <slug> --check     print what is wrong with picture_plan.json (exit 1), or "ok"

picture_plan.json, written by the inspiration-beats skill (no spend):
  {"look": "one art direction for every picture of this short",
   "beats": [{"lines": [0, 1], "prompt": "the scene of this beat"}, {"lines": [2], "prompt": "..."}, ...]}
`lines` count from 0 in quote.json's "lines". Beats are whole lines, in order, each line in exactly one beat, so a picture changes where a line starts, and a line starts where the
voice does (narration_sync). There are fewer pictures than lines, so a picture carries a thought, not a sentence; the last beat holds its picture to the end card.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C

PLAN = "picture_plan.json"
MIN_BEATS, MAX_BEATS = 2, 6    # a short with one picture is the single-background output; more than six cuts is a slideshow
MIN_WORDS = 5                  # about 2 seconds of speech: a picture is never gone before it was seen
MIN_PROMPT, MAX_PROMPT = 20, 600


def load(D): return C.load_json(os.path.join(D, PLAN), default=None)


def quote_lines(D):
    q = C.load_json(os.path.join(D, "quote.json"), default={}) or {}
    return [str(l).strip() for l in (q.get("lines") or []) if str(l).strip()]


def max_beats(n_lines): return max(MIN_BEATS, min(MAX_BEATS, n_lines - 1))


def problems(plan, lines):
    """Everything that is wrong with the plan against the script's lines, in words the owner can read. An empty list is a plan the pictures step can use."""
    if not isinstance(plan, dict): return ["there is no picture plan"]
    n = len(lines); out = []
    if n < MIN_BEATS: return [f"the script has {n} line{'s' * (n != 1)}: a picture per beat needs at least {MIN_BEATS}"]
    look = " ".join(str(plan.get("look") or "").split())
    if len(look) < 10: out.append("the plan has no look (one art direction for all the pictures, 10 or more characters)")
    beats = plan.get("beats")
    if not isinstance(beats, list) or not beats: return out + ["the plan has no beats"]
    top = max_beats(n)
    if not MIN_BEATS <= len(beats) <= top: out.append(f"a script of {n} lines takes {MIN_BEATS} to {top} pictures, the plan has {len(beats)}")
    expect = 0
    for k, b in enumerate(beats, 1):
        ls = b.get("lines") if isinstance(b, dict) else None
        if not isinstance(ls, list) or not ls or not all(isinstance(i, int) and not isinstance(i, bool) for i in ls): out.append(f"beat {k} has no lines"); continue
        if ls != list(range(expect, expect + len(ls))): out.append(f"beat {k} must hold the next lines in order (starting at line {expect}), it has {ls}")
        expect = ls[-1] + 1
        words = sum(len(lines[i].split()) for i in ls if 0 <= i < n)
        if words < MIN_WORDS: out.append(f"beat {k} has {words} words: a picture needs at least {MIN_WORDS} words of speech, join it to a neighbour")
        p = " ".join(str(b.get("prompt") or "").split())
        if not MIN_PROMPT <= len(p) <= MAX_PROMPT: out.append(f"beat {k}'s prompt is {len(p)} characters, it needs {MIN_PROMPT} to {MAX_PROMPT}")
    if expect != n: out.append(f"the beats cover {expect} of the {n} lines: every line belongs to exactly one beat")
    return out


def check(D): return problems(load(D), quote_lines(D))


def valid(D): return load(D) is not None and not check(D)


def beat_file(D, k): return os.path.join(D, "scenes", "beat_%02d.png" % (k + 1))


def count(D):
    plan = load(D)
    return len(plan["beats"]) if plan and isinstance(plan.get("beats"), list) else 0


def pictures_done(D):
    """The plan is usable and every beat has its picture."""
    return valid(D) and all(os.path.exists(beat_file(D, k)) for k in range(count(D)))


def prompts(D):
    plan = load(D); bad = problems(plan, quote_lines(D))
    if bad: raise ValueError("the picture plan is not usable: " + "; ".join(bad) + ". Plan the pictures again.")
    return [" ".join(b["prompt"].split()) for b in plan["beats"]]


def look(D):
    return " ".join(str(load(D)["look"]).split())[:400]


def segments(D, starts, duration):
    """What the renderer shows when: one picture per beat from where its first line starts (the first from 0) to where the next beat's first line starts (the last to the end).
    `starts` is the start second of every line as the voice timing has it. None when the beats do not fit the lines, and the short keeps its one background."""
    plan = load(D); lines = quote_lines(D)
    if problems(plan, lines) or len(starts) != len(lines): return None
    firsts = [b["lines"][0] for b in plan["beats"]]
    cuts = [0.0] + [round(float(starts[f]), 2) for f in firsts[1:]] + [round(float(duration), 2)]
    if any(b - a < 0.8 for a, b in zip(cuts, cuts[1:])): return None   # a cut that would show a picture for under a second: better one background than a flicker
    return [{"bg": os.path.join("scenes", os.path.basename(beat_file(D, k))), "start": cuts[k], "end": cuts[k + 1]} for k in range(len(firsts))]


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) != 2 or a[1] != "--check": sys.exit(__doc__)
    bad = check(C.song_dir(a[0]))
    print("ok" if not bad else "\n".join("- " + p for p in bad)); sys.exit(1 if bad else 0)
