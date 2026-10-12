#!/usr/bin/env python3
"""new_song.py <slug>  creates songs/<slug>/ from songs/_template if present, else from the plugin's templates/song."""
import os, sys, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import find_root, cfg, songs_root

def main(slug):
    sr = songs_root(); dst = f"{sr}/{slug}"
    if os.path.exists(dst):
        sys.exit(f"navaan: exists: {dst}")
    os.makedirs(sr, exist_ok=True)
    tpl = f"{sr}/_template"
    if not os.path.isdir(tpl):
        tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "song")
    shutil.copytree(tpl, dst)
    mp = f"{dst}/meta.json"
    m = json.load(open(mp)); m["slug"] = slug
    json.dump(m, open(mp, "w"), indent=2, ensure_ascii=False); open(mp, "a").write("\n")
    tp = f"{dst}/tags.json"
    if os.path.exists(tp) and cfg("artist.name"):
        t = json.load(open(tp, encoding="utf-8"))
        t.update({"artist": cfg("artist.name"), "album_artist": cfg("artist.album_artist") or cfg("artist.name"),
                  "copyright": cfg("artist.copyright_owner", ""), "comment": cfg("publish.credit_text", ""),
                  "year": str(__import__("datetime").date.today().year), "language": cfg("music.default_language", "")})
        json.dump(t, open(tp, "w", encoding="utf-8"), indent=2, ensure_ascii=False); open(tp, "a").write("\n")
    if not cfg("artist.name"):
        print("note: no artist profile yet. Run scripts/setup_profile.py to create navaan.config.json.")
    print("created", dst)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
