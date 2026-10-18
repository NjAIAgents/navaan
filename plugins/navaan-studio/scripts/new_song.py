#!/usr/bin/env python3
"""new_song.py [slug] [--type music|inspiration] [--idea TEXT]  create an item folder under <local_dir>/songs.

Without a slug the next free one for the type is used (song-005, insp-001). Every item has a content type in meta.json
(`type`), which picks its pipeline. The folder comes from songs/_template (music only) or the plugin's templates/<type>."""
import os, sys, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import find_root, cfg, songs_root, CONTENT_TYPES, next_slug, item_save

BUILT = ("music", "inspiration", "aha")


def create(slug=None, ctype="music", idea=""):
    if ctype not in CONTENT_TYPES: sys.exit(f"navaan: unknown type {ctype}. Types: {', '.join(CONTENT_TYPES)}")
    if ctype not in BUILT: sys.exit(f"navaan: the {ctype} pipeline is planned, not built yet.")
    sr = songs_root(); slug = slug or next_slug(ctype); dst = f"{sr}/{slug}"
    if os.path.exists(dst): sys.exit(f"navaan: exists: {dst}")
    os.makedirs(sr, exist_ok=True)
    here = os.path.dirname(os.path.abspath(__file__))
    tpl = f"{sr}/_template" if ctype == "music" and os.path.isdir(f"{sr}/_template") else None
    if not tpl:
        tpl = os.path.join(here, "..", "templates", ctype if os.path.isdir(os.path.join(here, "..", "templates", ctype)) else "song")
    shutil.copytree(tpl, dst)
    mp = f"{dst}/meta.json"
    m = json.load(open(mp)); m["slug"] = slug; m["type"] = ctype
    item_save(slug, m)   # into Postgres; the store writes meta.json back into the folder
    if idea.strip():
        bp = f"{dst}/brief.md"; old = open(bp, encoding="utf-8").read() if os.path.exists(bp) else ""
        ph = "(write the quote or the idea here)"
        open(bp, "w", encoding="utf-8").write(old.replace(ph, idea.strip()) if ph in old else old.rstrip() + f"\n\n## Idea\n\n{idea.strip()}\n")
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
    return slug


def main(a):
    def opt(n, d=""): return a[a.index(n) + 1] if n in a and a.index(n) + 1 < len(a) else d
    skip = {i for n in ("--type", "--idea") if n in a for i in (a.index(n), a.index(n) + 1)}
    pos = [x for i, x in enumerate(a) if i not in skip]
    create(pos[0] if pos else None, opt("--type", "music"), opt("--idea"))


if __name__ == "__main__":
    if len(sys.argv) < 2 and False: sys.exit(__doc__)
    if any(x in ("-h", "--help") for x in sys.argv[1:]): sys.exit(__doc__)
    main(sys.argv[1:])
