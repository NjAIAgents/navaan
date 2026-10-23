#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-20
Last updated: 2026-10-20
Description: a square cover for a song in the modern look (NAV-135): art from the OpenAI image API (the prompt is shown and editable), title and artist drawn by make_cover.

  song_cover.py <slug> [--prompt TEXT] [--estimate]

With no --prompt and art already there (cover_art.*, refs/cover.*), only the lettering is redone: free. With --prompt, or no art yet, the art is made: it spends on the OpenAI
images API and the run cap in Settings applies. Writes cover_art.png (the raw art, no lettering), cover_prompt.txt, then cover_1x1.png, cover_16x9.png and thumb_16x9.jpg through
make_cover. When the song is already in the bucket the new cover replaces the one there, so the site shows it.
"""
import os, sys, json, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
LOG = L.get("song_cover")
import media_cfg, image_openai as IO, make_cover as MC
from PIL import Image

SIZE = "1024x1024"
FINISH = " Square cover composition with a calm open area in the lower third. No text, no letters, no logos, no watermarks."


def _read(D, name):
    p = os.path.join(D, name)
    if not os.path.isfile(p): return ""
    with open(p, encoding="utf-8") as f: return f.read().strip()


def default_prompt(slug):
    """Built from the song's own files, no model call, no spend. The owner edits it before anything is generated."""
    D = C.song_dir(slug); title = (_read(D, "title.txt").splitlines() or [slug])[0]
    style = " ".join(_read(D, "style.txt").split())[:300]
    lines = [l.strip() for l in _read(D, "lyrics.txt").splitlines() if l.strip() and not l.strip().startswith("[")][:4]
    import prompt_pack as PP
    g = PP.who_sings(_read(D, "style.txt"))
    who = ("A lone figure of a man seen from behind or in silhouette, because the song is sung by a man: do not show a woman. " if g == "male"
           else "A lone figure of a woman seen from behind or in silhouette, because the song is sung by a woman: do not show a man. " if g == "female"
           else "No people in the frame: an abstract form or an atmospheric place only, because who sings is not stated. ")
    return ("Cover art for the song \"%s\". " % title + who + ("Sound and mood: %s. " % style if style else "")
            + ("Feeling of these lines: \"%s\". " % " / ".join(lines) if lines else "") + MC.MODERN_LOOK + FINISH)


def has_art(D):
    return any(os.path.exists(os.path.join(D, a)) for a in MC.ART)


def _cloud(slug):
    cloud = (C.item_load(slug, None) or {}).get("cloud") or {}
    return cloud if (cloud.get("verified") and cloud.get("prefix") is not None) else None


def published(slug):
    """True when the bucket holds the cover the studio has now (False when the song is not in the bucket, or the cover changed since)."""
    D = C.song_dir(slug); f = os.path.join(D, "cover_1x1.png"); c = _cloud(slug)
    return bool(c and os.path.isfile(f) and ((c.get("objects") or {}).get("cover_1x1.png") or {}).get("size") == os.path.getsize(f))


def state(slug):
    D = C.song_dir(slug); cfg = media_cfg.load(); q = cfg["image_quality"]; f = os.path.join(D, "cover_1x1.png")
    return {"prompt": _read(D, "cover_prompt.txt") or default_prompt(slug), "default": default_prompt(slug), "has": os.path.isfile(f), "v": int(os.path.getmtime(f)) if os.path.isfile(f) else 0,
            "art": has_art(D), "in_bucket": bool(_cloud(slug)), "published": published(slug), "usd": IO.estimate(q, SIZE, IO.model_name(cfg)), "quality": q, "key": bool(IO.key_for(cfg))}


def publish(slug):
    """Put the cover in the song's bucket folder in place of the earlier one and record its size, so the catalog and the sizes cut for the site follow it. ValueError with a sentence when it cannot."""
    D = C.song_dir(slug); src = os.path.join(D, "cover_1x1.png")
    if not os.path.isfile(src): raise ValueError("Make the cover first.")
    cloud = _cloud(slug)
    if not cloud: raise ValueError("This song is not in the bucket yet.")
    import objstore, catalog_store as K
    with open(src, "rb") as f: data = f.read()
    key = (cloud.get("prefix") or "") + "cover_1x1.png"
    objstore.put(key, data, "image/png")
    m = C.item_load(slug, None) or {}; objs = m.setdefault("cloud", {}).setdefault("objects", {}); objs.setdefault("cover_1x1.png", {})["size"] = len(data)
    C.item_save(slug, m)   # the catalog sync reads the size from here: a stale one would bring the old picture back
    if not K.set_picture(slug, "cover", key, "image/png", len(data)): raise ValueError("This song is not in the catalog yet.")
    return {"key": key, "bytes": len(data)}


def typeset(slug):
    MC.make(slug)
    if _cloud(slug):   # a song not in the bucket yet has nothing to replace
        try: publish(slug)
        except Exception: L.soft(LOG, "song_cover_publish")   # the cover is made and kept; "Save for the site" tries again


def generate(slug, prompt):
    prompt = (prompt or "").strip()
    if len(prompt) < 20: raise ValueError("Write a prompt of at least a sentence.")
    cfg = media_cfg.load(); q = cfg["image_quality"]; cost = IO.check_cap(q, cfg, SIZE)   # ValueError when over the run cap
    key, who = IO.key_for(cfg), IO.NAME[IO.engine(cfg)]   # the key of the picture maker chosen in Settings, not always OpenAI's
    if not key: raise ValueError("No %s key. Paste it in Settings, Pictures and voice." % who)
    D = C.song_dir(slug)
    raw = IO.request_image(prompt[:3500], q, key, SIZE, IO.model_name(cfg))
    media_cfg.add_usage(openai_usd=cost)   # spent now, whatever happens to the file
    for a in MC.ART[:3]:   # older art made by Flow would be found first; the new one replaces it
        if os.path.exists(os.path.join(D, a)): os.remove(os.path.join(D, a))
    Image.open(io.BytesIO(raw)).convert("RGB").save(os.path.join(D, "cover_art.png"), optimize=True)
    with open(os.path.join(D, "cover_prompt.txt"), "w", encoding="utf-8") as f: f.write(prompt + "\n")
    typeset(slug)
    return cost


def use_picture(slug, data):
    D = C.song_dir(slug)
    try: im = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e: raise ValueError("That is not a picture I can read.") from e
    for a in MC.ART[:3]:
        if os.path.exists(os.path.join(D, a)): os.remove(os.path.join(D, a))
    im.save(os.path.join(D, "cover_art.png"), optimize=True)
    typeset(slug)


def main(a):
    if not a: sys.exit("usage: song_cover.py <slug> [--prompt TEXT] [--estimate]")
    if "--estimate" in a: print(json.dumps(state(a[0]))); return 0
    try:
        if "--prompt" not in a and has_art(C.song_dir(a[0])): typeset(a[0]); print("cover lettered again from the art that is there"); return 0
        p = a[a.index("--prompt") + 1] if "--prompt" in a else state(a[0])["prompt"]   # the prompt saved on the Cover card when there is one, else the one made from the song
        print("cover_1x1.png, about $%.3f" % generate(a[0], p))
    except (ValueError, RuntimeError) as e: sys.exit("navaan: " + str(e))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
