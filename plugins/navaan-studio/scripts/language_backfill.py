#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-18
Last updated: 2026-10-18
Description: find the songs that have no language (so an English song is missing under English on the site) and fill in the ones that can be told from the lyrics.

  language_backfill.py            list them and what would be set; changes nothing
  language_backfill.py --apply    set them

The lyrics decide only what they can: Latin letters mean English. Lyrics in Devanagari could be Hindi, Maithili or another language, so those are listed as "needs you" and left alone, as are songs with no lyrics.
The language goes into the song's tags.json (where the catalog reads it) and the catalog row is synced; a song whose folder is gone gets the language written to its catalog row directly.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import catalog_store as K


def guess(lyrics):
    """"English" when the lyrics are in Latin letters, else "" (Devanagari or no words: it takes the owner to say which language)."""
    t = [l for l in (lyrics or "").splitlines() if l.strip() and not l.strip().startswith("[")]
    text = " ".join(t); dev = sum(1 for c in text if "ऀ" <= c <= "ॿ"); lat = sum(1 for c in text if c.isascii() and c.isalpha())
    return "English" if lat and lat > dev else ""


def plan():
    """[{slug, title, language, action}] for every track with no language: action is "set" (with the language to set) or "needs you" (the lyrics do not say)."""
    out = []
    for t in K.tracks_without_language():
        g = guess(t["lyrics"]); out.append({"slug": t["slug"], "studio_slug": t["studio_slug"], "title": t["title"], "language": g, "action": "set" if g else "needs you"})
    return out


def apply_one(item):
    """Write one language: into tags.json when the song's folder is there (then sync the catalog), else straight into the catalog row."""
    try: D = C.song_dir(item["studio_slug"])
    except SystemExit: D = None   # expected: the folder is gone (archived and cleaned up)
    if D and os.path.isdir(D):
        tp = os.path.join(D, "tags.json"); t = C.load_json(tp, default={}) if os.path.exists(tp) else {}
        if isinstance(t, dict) and not str(t.get("language") or "").strip():
            t["language"] = item["language"]; json.dump(t, open(tp, "w", encoding="utf-8"), ensure_ascii=False, indent=2); K.sync_item(item["studio_slug"]); return "tags.json"
    return "catalog" if K.set_language(item["slug"], item["language"]) else "missing"


def main(a):
    items = plan()
    if not items: print("every track has a language"); return 0
    for it in items: print(f"{it['slug']:12} {it['title'][:40]:40} -> {it['language'] or '(needs you: say Hindi, Maithili or other)'}")
    if "--apply" not in a: print("\nNothing changed. Run with --apply to set the ones that say English."); return 0
    done = [apply_one(it) for it in items if it["action"] == "set"]
    print(f"\nset {len(done)} ({', '.join(sorted(set(done))) or 'none'}); {sum(1 for it in items if it['action'] != 'set')} left for you"); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
