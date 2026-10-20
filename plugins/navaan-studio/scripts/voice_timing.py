#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: what the narration's own sound says about its captions (NAV-132): when each word starts, and how loud the voice is at every frame.

  analyse(path, fps, lines)    {"amp": [0..1 per video frame], "at": [[start second of each word] per line]}, or None when numpy or the audio is not usable

The speech model (Whisper, via sherpa-onnx) places whole phrases, not words, so word starts come from the voice itself: inside each line the words are first spread by length
(a long word takes longer), then each boundary moves to the quiet dip nearest to it, and the next word starts where the voice picks up again. A boundary with no real dip nearby (words
spoken straight into each other) keeps the length-based time. `amp` is the loudness per frame, 0 at the voice's noise floor and 1 at its loud parts; the renderer lets the glow breathe with it.
"""
import os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
LOG = L.get("voice_timing")
FRAME_S = 0.02   # narration_sync.envelope: one value per 20 ms


def _amp(np, env, floor, peak, fps):
    a = np.clip((env - floor) / (peak - floor), 0.0, 1.0)
    a = np.convolve(a, np.ones(5) / 5, "same")   # a calmer curve than the 20 ms flicker: it moves a glow, it does not strobe it
    n = int(len(env) * FRAME_S * fps) + 1
    return [round(float(a[min(len(a) - 1, int(f / fps / FRAME_S))]), 2) for f in range(n)]


def onsets(np, env, floor, start, end, words):
    """Start second of each word of one line spoken between `start` and `end`."""
    n = len(words)
    if n == 0: return []
    total = sum(len(w) for w in words) or 1; acc = 0; expect = []
    for w in words: expect.append(start + (acc / total) * (end - start) * 0.93); acc += len(w)
    a, b = int(start / FRAME_S), min(len(env) - 1, int(end / FRAME_S))
    if b - a < 6 * n: return expect
    med = float(np.median(env[a:b]))
    out = [expect[0]]; reach = max(1, int(0.35 * (end - start) / n / FRAME_S))
    for k in range(1, n):
        c = int(expect[k] / FRAME_S); lo, hi = max(a, c - reach), min(b, c + reach)
        if hi <= lo: out.append(expect[k]); continue
        m = lo + int(np.argmin(env[lo:hi])); dip = float(env[m])
        if dip >= floor + 0.55 * (med - floor): out.append(expect[k]); continue   # no real dip: the words run together
        j = m
        while j < b and env[j] < dip + 0.5 * (med - dip): j += 1   # the word starts where the voice picks up again
        out.append(max(out[-1] + 0.08, j * FRAME_S))
    return [round(t, 2) for t in out]


def analyse(path, fps, lines):
    try:
        import numpy as np
        import narration_sync as N
    except ImportError as e:
        L.ignored(LOG, "analyse: numpy is optional, the words are timed by length", e); return None
    try:
        env = N.envelope(N.decode(path, C.tool("ffmpeg")))
        if len(env) < 10: return None
        floor, peak = N.levels(env)
        if peak - floor < 1e-4: return None   # silent
        at = [onsets(np, env, floor, float(l["start"]), float(l["end"]), str(l["text"]).split()) for l in lines]
        return {"amp": _amp(np, env, floor, peak, fps), "at": at}
    except (OSError, ValueError, subprocess.CalledProcessError):
        L.soft(LOG, "voice_timing_failed", path=path); return None
