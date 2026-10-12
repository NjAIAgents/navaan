#!/usr/bin/env python3
"""tag_mp3.py <slug>  ->  songs/<slug>/final_tagged.mp3 with ID3v2.3 tags from tags.json and cover_1x1.png embedded.
tags.json keys used: title artist album album_artist track genre year composer copyright comment language."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import tool, song_dir, run, load_json, cfg

MAP = {"title": "title", "artist": "artist", "album": "album", "album_artist": "album_artist", "track": "track",
       "genre": "genre", "year": "date", "composer": "composer", "copyright": "copyright", "comment": "comment",
       "language": "language"}

def main(slug):
    D = song_dir(slug); t = load_json(f"{D}/tags.json")
    for need in ("final.mp3", "cover_1x1.png"):
        if not os.path.exists(f"{D}/{need}"):
            sys.exit(f"navaan: missing {D}/{need}")
    fb = {"artist": cfg("artist.name"), "album_artist": cfg("artist.album_artist"), "copyright": cfg("artist.copyright_owner"),
          "comment": cfg("publish.credit_text")}
    md = []
    for k, v in MAP.items():
        val = t.get(k) or fb.get(k)
        if val:
            md += ["-metadata", f"{v}={val}"]
    run([tool("ffmpeg"), "-y", "-loglevel", "error", "-i", f"{D}/final.mp3", "-i", f"{D}/cover_1x1.png",
         "-map", "0:a", "-map", "1:v", "-c", "copy", "-id3v2_version", "3",
         "-metadata:s:v", "title=Cover", "-metadata:s:v", "comment=Cover (front)", *md, f"{D}/final_tagged.mp3"])
    print("wrote", f"{D}/final_tagged.mp3")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
