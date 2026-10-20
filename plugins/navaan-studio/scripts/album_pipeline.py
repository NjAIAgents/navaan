#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: the album pipeline: name suggestions from the chosen songs, and a square cover made from a prompt you can read and change.

  suggest_names(slugs)            five album names with a line on why, from the songs' titles, moods and first lines (an OpenAI chat call, a few cents)
  cover_state(album_slug)         the prompt, the cost and whether a cover exists (no spend)
  generate_cover(album_slug, prompt, style)   the art from OpenAI images (square), the NAVAAN mark, the title and the artist drawn by us

  publish(album_slug)             put the cover in the bucket and register it in the catalog, so the album shows it (made covers are published as they are made)

The cover is kept in <project>/albums/<slug>/cover_1x1.png and copied to <artist>/albums/<slug>/cover_1x1.png in the bucket.
"""
import os, sys, json, re, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
LOG = L.get("album_pipeline")
import media_cfg, image_openai as IO, prompt_pack, poster as P, catalog_store as K
from PIL import Image, ImageDraw
from make_cover import cover_scale, shade, latin

SIZE = "1024x1024"
W = 1080
FINISH = " Square album cover composition with a calm open area in the lower third. No text, no letters, no logos, no watermarks."
SUGGEST = ("You are naming a record. NAVAAN, an independent artist, is releasing an album and needs its title: the kind an artist chooses for a new release, not the name of a playlist. "
           "Songs on this album (title; mood; language; first lines):\n{songs}\n\n"
           "Suggest {n} album titles. A real album title has a point of view: it comes from an image, a line, a place, a feeling or one idea that runs through all the songs, and it reads like something a listener would remember a record by "
           "(think 'Rumours', 'Blue', 'Kind of Blue', 'Lemonade', 'Unplugged in the rain', 'Dil Ki Baat'; never 'Chill Vibes', 'Late Night Mix' or 'Best of 2026'). "
           "One to five words, a title, not a description. Do NOT use playlist words: mix, vibes, hits, best of, collection, playlist, essentials, songs, tracks, volume, vol, chill, lofi, mood, years or 'Top N'. "
           "Do not name the genre or the mood outright; hint at it. Do not reuse a song title. Write it in the language of the songs (Hindi in Devanagari with its Roman spelling in brackets when the songs are Hindi). "
           "In `why`, one short sentence on the idea that ties the songs together. Reply as JSON only: {{\"names\": [{{\"name\": \"...\", \"why\": \"one short sentence\"}}]}}")
PLAYLIST_WORDS = ("mix", "vibes", "vibe", "hits", "best of", "collection", "playlist", "essentials", "songs", "tracks", "volume", "vol.", "lofi", "lo-fi", "chill", "mood")


def playlist_like(name):
    """True for a name that reads like a playlist, not a record: it carries one of the playlist words or a year or 'Top N'."""
    t = " " + re.sub(r"[^\w\s.\-]", " ", str(name or "").lower()) + " "
    return any((" " + w + " ") in t or t.rstrip().endswith(" " + w) for w in PLAYLIST_WORDS) or bool(re.search(r"(?<!\w)(19|20)\d\d(?!\w)|(?<!\w)top\s*\d+(?!\w)", t))


def _read(D, name):
    p = os.path.join(D, name)
    if not os.path.isfile(p): return ""
    with open(p, encoding="utf-8") as f: return f.read().strip()


def song_facts(slug):
    D = C.song_dir(slug); m = C.item_load(slug, None) or {}
    lines = [l.strip() for l in _read(D, "lyrics.txt").splitlines() if l.strip() and not l.strip().startswith("[")][:2]
    info = {}
    try: info = json.loads(_read(D, "tags.json") or "{}")
    except ValueError: info = {}   # expected: tags.json can be a list
    return {"slug": slug, "title": (_read(D, "title.txt").splitlines() or [slug])[0], "mood": m.get("mood") or "", "language": (info.get("language") if isinstance(info, dict) else "") or "", "lines": lines}


def suggest_names(slugs, n=5, runner=None):
    slugs = [s for s in dict.fromkeys(slugs) if s]
    if len(slugs) < 2: raise ValueError("pick at least two songs")
    facts = [song_facts(s) for s in slugs]
    songs = "\n".join("- %s; %s; %s; %s" % (f["title"], f["mood"] or "no mood", f["language"] or "language not given", " / ".join(f["lines"]) or "no lyrics") for f in facts)
    text = (runner or prompt_pack.openai_runner)(SUGGEST.format(songs=songs, n=n))
    m = re.search(r"\{.*\}", text, re.S)
    if not m: raise RuntimeError("the name helper did not answer in the expected form")
    out = []
    for x in (json.loads(m.group(0)).get("names") or []):
        name = " ".join(str((x.get("name") if isinstance(x, dict) else x) or "").split())[:80]
        if name and name not in [o["name"] for o in out]: out.append({"name": name, "why": " ".join(str(x.get("why") or "").split())[:160] if isinstance(x, dict) else ""})
    if not out: raise RuntimeError("no names came back, try again")
    real = [o for o in out if not playlist_like(o["name"])]   # a playlist-style name that slipped through is dropped, unless nothing else is left
    return (real or out)[:n]


def album_dir(slug):
    if not re.match(r"^[A-Za-z0-9_-]{1,80}$", slug or ""): raise ValueError("bad album name")
    d = os.path.join(os.path.dirname(C.songs_root()), "albums", slug); os.makedirs(d, exist_ok=True); return d


def _album(slug):
    a = next((x for x in K.albums() if x["slug"] == slug), None)
    if not a: raise LookupError("no such album")
    return a


def default_prompt(album):
    facts = [song_facts(t["slug"]) for t in album["tracks"]]
    moods = sorted({f["mood"] for f in facts if f["mood"]})
    lines = [l for f in facts for l in f["lines"]][:3]
    return ("Professional square album cover artwork for an album called \"%s\" with songs: %s. " % (album["title"], ", ".join(f["title"] for f in facts))
            + ("Mood: %s. " % ", ".join(moods) if moods else "") + ("Feeling of these lines: \"%s\". " % " / ".join(lines) if lines else "")
            + "Cinematic, painterly, refined colour, timeless." + FINISH)


def cover_state(slug):
    a = _album(slug); d = album_dir(slug); cfg = media_cfg.load(); q = cfg["image_quality"]
    pf = os.path.join(d, "cover_prompt.txt"); cv = os.path.join(d, "cover_1x1.png")
    return {"prompt": _read(d, "cover_prompt.txt") or default_prompt(a), "has": os.path.isfile(cv), "v": int(os.path.getmtime(cv)) if os.path.isfile(cv) else 0,
            "published": os.path.isfile(cv) and bool(a.get("art")) and a["art"]["v"] == os.path.getsize(cv),
            "style": _read(d, "cover_style.txt") if _read(d, "cover_style.txt") in P.STYLES else "bold", "styles": list(P.STYLES),
            "usd": IO.estimate(q, SIZE, IO.model_name(cfg)), "key": bool(media_cfg.get_key("openai"))}


def typeset(slug, art_path=None, style=None):
    a = _album(slug); d = album_dir(slug); art = Image.open(art_path or os.path.join(d, "cover_art.png")).convert("RGB")
    style = style if style in P.STYLES else (_read(d, "cover_style.txt") if _read(d, "cover_style.txt") in P.STYLES else "bold")
    file, px, _align = P.STYLES[style]; path = os.path.join(P.FONTS, file); pad = 70
    im = cover_scale(art, W, W); shade(im, 0, 225, 0.5); dr = ImageDraw.Draw(im)
    P._mark(im, W // 2, pad - 24, 110)
    title = a["title"]; f = P._fit(dr, title, path, int(px * 0.85), W - 2 * pad, 56)
    P._text(im, (W // 2, W - pad - 52), title, f, (255, 246, 228), "ms")
    dr.text((W // 2, W - pad - 8), (C.cfg("artist.name") or "NAVAAN").upper(), font=latin(30), fill=P.GOLD, anchor="ms")
    im.save(os.path.join(d, "cover_1x1.png"), optimize=True)
    try: publish(slug)
    except Exception: L.soft(LOG, "album_cover_publish")   # the cover is made and kept; "Save for the site" tries again


def publish(slug):
    """Put the made cover in the bucket and register it as the album's cover. Raises ValueError with a sentence when it cannot."""
    _album(slug); src = os.path.join(album_dir(slug), "cover_1x1.png")
    if not os.path.isfile(src): raise ValueError("Make the cover first.")
    import objstore
    with open(src, "rb") as f: data = f.read()
    key = f"{K.ARTIST}/albums/{slug}/cover_1x1.png"
    objstore.put(key, data, "image/png")
    if not K.set_album_cover(slug, key, len(data)): raise ValueError("This album is not in the catalog.")


def generate_cover(slug, prompt, style=None):
    prompt = (prompt or "").strip()
    if len(prompt) < 20: raise ValueError("Write a prompt of at least a sentence.")
    cfg = media_cfg.load(); q = cfg["image_quality"]; cost = IO.check_cap(q, cfg, SIZE)
    key = media_cfg.get_key("openai")
    if not key: raise ValueError("No OpenAI key. Paste it in Settings.")
    d = album_dir(slug); _album(slug)
    raw = IO.request_image(prompt[:3500], q, key, SIZE, IO.model_name(cfg))
    media_cfg.add_usage(openai_usd=cost)   # spent now, whatever happens to the file
    Image.open(io.BytesIO(raw)).convert("RGB").save(os.path.join(d, "cover_art.png"), optimize=True)
    for name, val in (("cover_prompt.txt", prompt), ("cover_style.txt", style if style in P.STYLES else "bold")):
        with open(os.path.join(d, name), "w", encoding="utf-8") as f: f.write(val + "\n")
    typeset(slug, style=style)
    return cost


def use_picture(slug, data):
    d = album_dir(slug); _album(slug)
    try: Image.open(io.BytesIO(data)).convert("RGB").save(os.path.join(d, "cover_art.png"), optimize=True)
    except Exception as e: raise ValueError("That is not a picture I can read.") from e
    typeset(slug)
