#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-20
Last updated: 2026-10-20
Description: change an Aha-lorithm script at its approval (NAV-133): edit the words of its beats, or replace the script with the owner's own words.

  edit(D, lines, captions)    rewrite the spoken line and the caption of each beat in quote.json; the beats, pictures and visual plan stay as they are
  replace(D, text)            write quote_feedback.txt so the script step runs again with the owner's words kept exactly (the aha-script skill reads it, then deletes it)
  feedback(D, note)           the same file for a plain "change this" note

Both raise ValueError with a sentence the owner can read. Neither runs anything: the caller redoes the script step.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C

MAX_LINE, MAX_CAPTION, MAX_OWN = 200, 80, 2500
FEEDBACK = "quote_feedback.txt"


def _clean(s): return " ".join(str(s).split())


def edit(D, lines, captions):
    path = os.path.join(D, "quote.json"); q = C.load_json(path, default={}) or {}
    old = [l for l in (q.get("lines") or []) if str(l).strip()]
    if not old: raise ValueError("There is no script yet. Run the script step first.")
    if not isinstance(lines, list) or not isinstance(captions, list) or len(lines) != len(old) or len(captions) != len(old):
        raise ValueError(f"The script has {len(old)} beats: keep one spoken line and one caption for each. To change the number of beats, use your own words instead.")
    lines = [_clean(l).replace("*", "") for l in lines]; captions = [_clean(c) for c in captions]   # the spoken lines carry no marks; a caption keeps its *marks*
    for i, (l, c) in enumerate(zip(lines, captions), 1):
        if not l: raise ValueError(f"Beat {i} has no spoken line.")
        if not c: raise ValueError(f"Beat {i} has no caption.")
        if len(l) > MAX_LINE: raise ValueError(f"Beat {i}: a spoken line can have {MAX_LINE} characters; this one has {len(l)}.")
        if len(c) > MAX_CAPTION: raise ValueError(f"Beat {i}: a caption can have {MAX_CAPTION} characters; this one has {len(c)}.")
    q.update({"lines": lines, "captions": captions, "text": " ".join(lines)})
    with open(path, "w", encoding="utf-8") as f: json.dump(q, f, ensure_ascii=False, indent=2)
    return q


def replace(D, text):
    t = "\n".join(l.strip() for l in str(text or "").strip().splitlines() if l.strip())
    if len(t) < 20: raise ValueError("Paste the words you want spoken.")
    if len(t) > MAX_OWN: raise ValueError(f"That is {len(t):,} characters; a short can use about {MAX_OWN:,}.")
    _write(D, "REPLACE: the owner wrote this script. Keep every word exactly as written (fix nothing but typos), split it into beats at sentence ends, and write the captions, "
              "the picture prompts and the visual plan for it. The words:\n" + t)


def feedback(D, note):
    n = _clean(note)
    if not n: raise ValueError("Say what should change.")
    _write(D, n[:1000])


def _write(D, text):
    with open(os.path.join(D, FEEDBACK), "w", encoding="utf-8") as f: f.write(text + "\n")
