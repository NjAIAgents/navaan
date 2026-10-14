#!/usr/bin/env python3
"""short_meta.py <slug>  write youtube_short.json, the title, description and tags of the YouTube Short, from youtube.json and the uploaded full video.

Title: the song title plus #Shorts (100 characters at most). Description: a link to the full song, the first paragraph of the full description, then #Shorts.
Run after the full video is uploaded, before the Short is. Sends nothing."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C


def build(meta, full_url):
    title = (meta.get("title") or "").replace("#Shorts", "").replace("#shorts", "").strip()[:90].rstrip()
    first = (meta.get("description") or "").strip().split("\n\n")[0].strip()[:300]
    desc = (f"Full song: {full_url}\n\n" if full_url else "") + (first + "\n\n" if first else "") + "#Shorts"
    tags = list(dict.fromkeys(list(meta.get("tags") or []) + ["Shorts"]))
    out = {"title": f"{title} #Shorts", "description": desc, "tags": tags}
    if meta.get("language"): out["language"] = meta["language"]
    return out


def main(slug):
    D = C.song_dir(slug)
    meta = C.load_json(os.path.join(D, "youtube.json"))
    if not meta: sys.exit("navaan: youtube.json is missing")
    items = (C.load_json(os.path.join(D, "meta.json"), default={}).get("published", {}) or {}).get("youtube_items", [])
    full = next((i["url"] for i in items if i.get("file") != "final_reel_9x16.mp4" and i.get("url")), "")
    if not full: print("note: the full video is not uploaded yet, the Short description has no link to it")
    out = build(meta, full)
    json.dump(out, open(os.path.join(D, "youtube_short.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"youtube_short.json: {out['title']}")


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1])
