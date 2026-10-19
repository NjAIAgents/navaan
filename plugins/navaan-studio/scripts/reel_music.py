#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: the music a reel may use: only audio NAVAAN owns, the published songs on this server. Nothing is downloaded and nothing third party is ever listed.

  reel_music.py <slug>     write music_library.json into the reel's folder: one entry per usable track

A track is listed when the item is a `music` item that is published (meta state "published", or a YouTube upload recorded) and has final_tagged.mp3 or final.mp3,
plus its reel_audio.mp3 clip when there is one. Each entry carries what the director needs to match mood: title, style, the first lyric lines, length.
Not listed on purpose: an inspiration's music.mp3 and assets/music (their licence is not confirmed). A reel can still use the owner's own track uploaded on its Music card (music_src.*).
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
LOG = L.get("reel_music")

CANDIDATES = ("final_tagged.mp3", "final.mp3", "reel_audio.mp3")


def _read(path, limit=400):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f: return f.read(limit).strip()
    except OSError:
        return ""   # expected: the song has no such file


def _seconds(path):
    try:
        return round(float(subprocess.check_output([C.tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], timeout=30).strip()), 1)
    except (subprocess.SubprocessError, ValueError, OSError):
        L.soft(LOG, "music_probe_failed"); return 0.0


def is_published(m):
    p = (m or {}).get("published") or {}
    return (m or {}).get("state") == "published" or bool(p.get("youtube_items")) or bool(p.get("youtube")) or bool(p.get("instagram"))


def library(root=None):
    root = root or C.songs_root(); out = []
    for slug in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        d = os.path.join(root, slug); mp = os.path.join(d, "meta.json")
        if not os.path.isfile(mp): continue
        try: m = json.load(open(mp, encoding="utf-8"))
        except ValueError: L.soft(LOG, "music_meta_unreadable"); continue
        if C.item_type(m) != "music" or not is_published(m): continue
        lines = C.lyric_lines(d)[:6]
        for name in CANDIDATES:
            p = os.path.join(d, name)
            if not os.path.isfile(p): continue
            out.append({"slug": slug, "file": name, "title": _read(os.path.join(d, "title.txt"), 120) or slug, "style": _read(os.path.join(d, "style.txt"), 300),
                        "lyric_lines": lines, "seconds": _seconds(p), "clip": name == "reel_audio.mp3"})
            if name != "reel_audio.mp3": break   # the full song once (tagged first); its reel clip is its own entry
        rp = os.path.join(d, "reel_audio.mp3")
        if os.path.isfile(rp) and not any(e["slug"] == slug and e["clip"] for e in out):
            out.append({"slug": slug, "file": "reel_audio.mp3", "title": (_read(os.path.join(d, "title.txt"), 120) or slug) + " (reel clip)", "style": _read(os.path.join(d, "style.txt"), 300),
                        "lyric_lines": lines, "seconds": _seconds(rp), "clip": True})
    return out


def resolve(slug, name, root=None):
    """The real path of a library track, or None. The slug and file must name a listed track: no paths, nothing outside the songs folder."""
    if not slug or os.path.basename(slug) != slug or os.path.basename(name) != name or name not in CANDIDATES: return None
    p = os.path.join(root or C.songs_root(), slug, name)
    return p if os.path.isfile(p) and any(e["slug"] == slug and e["file"] == name for e in library(root)) else None


def main(slug):
    D = C.song_dir(slug); lib = library()
    own = [os.path.basename(p) for p in sorted(os.listdir(D)) if p.startswith("music_src.")] if os.path.isdir(D) else []
    json.dump({"tracks": lib, "own_upload": own[0] if own else None,
               "note": "only audio NAVAAN owns; an empty list means no published songs on this machine: the reel then has no music unless the owner uploads a track on the Music card"},
              open(os.path.join(D, "music_library.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"music library: {len(lib)} track(s)" + (f", plus the owner's own upload {own[0]}" if own else ""))


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1])
