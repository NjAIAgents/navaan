#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: the per-song choices for the lyrics on the Instagram reel: whether to use the reel with lyrics at all, and a nudge in seconds when they are early or late.

  on or off   stored in the song's meta (`reel_lyrics: "off"`), so switching it never makes the reel stale: Instagram simply takes the reel without lyrics.
  offset      stored in reel_lyrics.json ({"offset": seconds}); a positive number shows the lyrics later, a negative one earlier. Changing it makes the reel stale: redo the reel.
"""
import os, json
import navaan_common as C

FILE = "reel_lyrics.json"
MAX_OFFSET = 10.0


def offset(D):
    """Seconds the reel's lyrics are nudged (positive = later). 0 when never set or unreadable."""
    try: return float((C.load_json(os.path.join(D, FILE), default={}) or {}).get("offset") or 0.0)
    except (TypeError, ValueError): return 0.0   # expected: a damaged file means no nudge


def check_offset(seconds):
    """The nudge as a number. ValueError with a sentence when it is not a number or is more than 10 seconds either way."""
    try: v = round(float(seconds), 2)
    except (TypeError, ValueError): raise ValueError("The nudge must be a number of seconds, for example 1.5 or -2.") from None
    if abs(v) > MAX_OFFSET: raise ValueError(f"The nudge can be at most {MAX_OFFSET:.0f} seconds either way. For more, redo the captions.")
    return v


def save_offset(D, seconds):
    """Keep a nudge (0 removes it)."""
    v = check_offset(seconds)
    p = os.path.join(D, FILE)
    if v == 0.0:
        if os.path.exists(p): os.remove(p)
        return 0.0
    with open(p, "w", encoding="utf-8") as f: json.dump({"offset": v}, f); f.write("\n")
    return v


def on(meta):
    """Whether Instagram takes the reel with lyrics (the default) or the plain one."""
    return (meta or {}).get("reel_lyrics") != "off"


def view(D, meta):
    return {"on": on(meta), "offset": offset(D)}
