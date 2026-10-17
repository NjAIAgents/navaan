#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: background music for an inspiration short: the owner's own track, kept with the item and fitted to the video by inspire_prep.py (ffmpeg trims it, fades it in and out and levels it; the renderer plays it quietly under the voice)

  save(D, name, audio)   keep the track as music_src.<ext> (audio is bytes or base64), checked with ffprobe; the music option becomes auto
  remove(D)              take it away; the music option becomes none
  info(D)                {"file", "name", "added", "seconds"} or None

The track's own name is kept beside it (music_src.json) so the licence of that track can be looked up later. Nothing is downloaded here: tracks come from the owner.
"""
import os, sys, json, glob, base64, subprocess, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C, narration

EXT = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")
MAX_BYTES = 20 * 1024 * 1024
STALE = ("music.mp3", "beats.json", "timing.json")   # made from the old music: the typography step makes them again


def _seconds(path):
    try:
        r = subprocess.run([C.tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=30)
        return round(float(r.stdout.strip()), 1)
    except Exception:   # expected: not an audio file, or no ffprobe: the caller says so
        return 0.0


def _drop_stale(D):
    for n in STALE:
        p = os.path.join(D, n)
        if os.path.exists(p): os.remove(p)


def _clear(D):
    for p in glob.glob(os.path.join(D, "music_src.*")): os.remove(p)


def save(D, name, audio, drop_stale=True):
    ext = os.path.splitext(str(name or ""))[1].lower()
    if ext not in EXT: raise ValueError("the music must be an mp3, wav, m4a, aac, flac or ogg file")
    raw = audio if isinstance(audio, (bytes, bytearray)) else base64.b64decode(str(audio).split(",", 1)[-1])
    if not raw: raise ValueError("the music file is empty")
    if len(raw) > MAX_BYTES: raise ValueError("the music is over 20 MB")
    _clear(D); p = os.path.join(D, "music_src" + ext)
    with open(p, "wb") as f: f.write(bytes(raw))
    secs = _seconds(p)
    if secs <= 0:
        os.remove(p); raise ValueError("that file is not audio that can be played")
    with open(os.path.join(D, "music_src.json"), "w", encoding="utf-8") as f: json.dump({"name": os.path.basename(str(name)), "added": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}, f)
    narration.set_options(D, {"music": "auto"})
    if drop_stale: _drop_stale(D)
    return info(D)


def remove(D, drop_stale=True):
    _clear(D)
    p = os.path.join(D, "music_src.json")
    if os.path.exists(p): os.remove(p)
    narration.set_options(D, {"music": "none"})
    if drop_stale: _drop_stale(D)


def info(D):
    files = [x for x in sorted(glob.glob(os.path.join(D, "music_src.*"))) if not x.endswith(".json")]
    if not files: return None
    f = files[0]
    meta = C.load_json(os.path.join(D, "music_src.json"), default={}) or {}
    return {"file": os.path.basename(f), "name": meta.get("name") or os.path.basename(f), "added": meta.get("added", ""), "seconds": _seconds(f)}
