#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-22
Last updated: 2026-10-22
Description: when each word of a narration is really spoken (NAV-146): a small offline recogniser (Vosk) listens, and what it heard is matched to your script by text.

  align(x, lines, model_dir)   {"lines": [{"at": [start second of each word], "start": s, "end": e}], "matched": n, "words": m} or None
  match(lines, heard)          the same from what a recogniser heard: [{"word", "start", "end"}], no audio and no model needed (what the tests use)

Why: Whisper small gives whole phrases and narration_sync cut those by character count, and voice_timing spread each line's words over its whole slot. For a slow reader with pauses and
a hum between lines both were seconds off (insp-008 and insp-009). Vosk reports every word it hears with its own start and end, and it ignores a hum. It mishears some words, so only
the words it got right are anchors; a misheard word takes its neighbours' time (one heard word for one script word in the same gap) or is spread between the anchors by length.
Too few anchors (under half the words) and align returns None: the caller keeps the Whisper and pause methods. English only: Vosk's small Hindi model is not installed (not tested).
"""
import os, re, sys, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MIN_MATCHED = 0.5   # share of the script's words the recogniser must have got right, else the times are not trusted
MIN_GAP = 0.04      # two words never start closer than this
CHUNK = 8000        # bytes (4000 samples, 0.25 s) fed to the recogniser at a time


def _norm(w): return re.sub(r"[^a-z0-9ऀ-ॿ]", "", w.lower())


def tokens(lines):
    """[(line index, word)] for every word of the script, in order. Words are split on whitespace, as the renderer splits them."""
    return [(i, w) for i, l in enumerate(lines) for w in str(l).split()]


def _spread(words, a, b):
    """Times for `words` placed between a and b in proportion to their length (a word of ten letters takes longer than one of two)."""
    tot = sum(max(1, len(_norm(w))) for w in words) or 1; out = []; acc = 0.0
    for w in words:
        out.append(a + (b - a) * acc / tot); acc += max(1, len(_norm(w)))
    return out


def match(lines, heard):
    """Time each script word from what was heard. heard is [{"word", "start", "end"}] in order. Returns None when fewer than MIN_MATCHED of the words were heard right."""
    toks = tokens(lines)
    if not toks or not heard: return None
    S = [_norm(w) for _, w in toks]; H = [_norm(h["word"]) for h in heard]
    n = len(S); start = [None] * n; end = [None] * n; matched = 0
    blocks = [m for m in difflib.SequenceMatcher(None, S, H, autojunk=False).get_matching_blocks() if m.size]
    anchors = []   # (script index, heard index) of words that were heard right
    for m in blocks:
        for k in range(m.size):
            if S[m.a + k]: anchors.append((m.a + k, m.b + k))
    for si, hi in anchors: start[si], end[si] = float(heard[hi]["start"]), float(heard[hi]["end"]); matched += 1
    if matched < MIN_MATCHED * n: return None
    # words between two anchors: one misheard word for one script word is taken as that word (a substitution); otherwise spread in the gap
    bounds = [(-1, -1)] + anchors + [(n, len(heard))]
    for (s0, h0), (s1, h1) in zip(bounds, bounds[1:]):
        miss = list(range(s0 + 1, s1)); hs = list(range(h0 + 1, h1))
        if not miss: continue
        if len(miss) == len(hs):
            for si, hi in zip(miss, hs): start[si], end[si] = float(heard[hi]["start"]), float(heard[hi]["end"])
            continue
        prev_end = float(heard[h0]["end"]) if h0 >= 0 else None; next_start = float(heard[h1]["start"]) if h1 < len(heard) else None
        if hs: a, b = float(heard[hs[0]]["start"]), float(heard[hs[-1]]["end"])       # words were heard here, just not these: they sit where the voice is
        elif prev_end is None and next_start is None: a, b = 0.0, 0.4 * len(miss)
        elif prev_end is None: b = next_start; a = max(0.0, b - 0.4 * len(miss))     # words before the first anchor: counted back from it
        elif next_start is None: a = prev_end; b = a + 0.4 * len(miss)              # words after the last anchor: counted on from it
        else: a, b = prev_end, next_start
        if b <= a: b = a + 0.12 * len(miss)
        for si, t in zip(miss, _spread([toks[i][1] for i in miss], a, b)): start[si] = t; end[si] = t + min(0.4, (b - a) / len(miss))
    for i in range(n):   # never backwards, never on top of each other
        if i and start[i] < start[i - 1] + MIN_GAP: start[i] = start[i - 1] + MIN_GAP
        if end[i] < start[i]: end[i] = start[i] + 0.1
    out = [{"at": [], "start": None, "end": None} for _ in lines]
    for (li, _), s, e in zip(toks, start, end):
        out[li]["at"].append(round(max(0.0, s), 2)); out[li]["end"] = round(e, 2)
    for o in out:
        if o["at"]: o["start"] = o["at"][0]
    if any(not o["at"] for o in out): return None   # a line with no words at all (a blank line) is not something to time
    return {"lines": out, "matched": matched, "words": n}


WORDS = "voiceover.words.json"   # written by narration_sync when the words were timed by a recogniser: {"method": "vosk", "lines": [{"at": [...]}]}


def load(D, texts):
    """The recognised word times of a narration for these on-screen lines (their text split on whitespace), or None when there are none, they are of another take, or a line's words
    do not match the lines (an edited script): then the caller times the words another way."""
    import json
    try: d = json.load(open(os.path.join(D, WORDS), encoding="utf-8"))
    except (OSError, ValueError): return None   # expected: no recognised times for this narration
    ats = [l.get("at") for l in d.get("lines") or []]
    if len(ats) != len(texts) or any(not isinstance(a, list) or len(a) != len(str(t).split()) for a, t in zip(ats, texts)): return None
    return ats


def recognise(x, model_dir):
    """What Vosk hears in x (float32 mono 16 kHz): [{"word", "start", "end"}]. ImportError when the vosk package is not installed, OSError when the model is missing."""
    import json
    import numpy as np
    from vosk import Model, KaldiRecognizer, SetLogLevel
    if not os.path.isdir(model_dir): raise OSError("the Vosk model is not installed: " + model_dir)
    SetLogLevel(-1)
    pcm = (np.clip(x, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    r = KaldiRecognizer(Model(model_dir), 16000); r.SetWords(True); words = []
    for i in range(0, len(pcm), CHUNK):
        if r.AcceptWaveform(pcm[i:i + CHUNK]): words += json.loads(r.Result()).get("result", [])
    words += json.loads(r.FinalResult()).get("result", [])
    return [{"word": w["word"], "start": w["start"], "end": w["end"]} for w in words]


def align(x, lines, model_dir):
    """Time the script's words from the audio. None when too little was heard right (the caller keeps its other methods)."""
    return match(lines, recognise(x, model_dir))
