#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: a portrait poster for a song: art from the OpenAI image API (the prompt is shown and editable), title and artist typeset here.

  poster.py <slug> [--prompt TEXT] [--estimate]

Writes songs/<slug>/poster_art.png (raw art, no lettering), poster_2x3.png (1080x1620 with the title drawn by us so the native script is always right)
and poster_prompt.txt (the prompt used, so the next run starts from it). Spends on the OpenAI images API: the run cap in Settings applies.
"""
import os, sys, json, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import media_cfg, image_openai as IO
from make_cover import split_title, shade, cover_scale, latin
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SIZE = "1024x1536"   # 2:3, the smaller OpenAI portrait size
W, H = 1080, 1620
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
# style -> (font file, title size, align). One font covers Devanagari and Latin, so the native title and its Latin spelling match.
STYLES = {"bold": ("RozhaOne-Regular.ttf", 190, "center"), "brush": ("YatraOne-Regular.ttf", 200, "center"), "hand": ("Kalam-Bold.ttf", 180, "left")}
GOLD, EMBER = (240, 200, 140), (214, 120, 90)
FINISH = " Portrait 2:3 poster composition with a calm open area in the lower third. No text, no letters, no logos, no watermarks."


def _read(D, name):
    p = os.path.join(D, name)
    if not os.path.isfile(p): return ""
    with open(p, encoding="utf-8") as f: return f.read().strip()


def default_prompt(slug):
    """Built from the song's own files, no model call, no spend. The owner edits it before anything is generated."""
    D = C.song_dir(slug); title = (_read(D, "title.txt").splitlines() or [slug])[0]
    style = " ".join(_read(D, "style.txt").split())[:300]
    lines = [l.strip() for l in _read(D, "lyrics.txt").splitlines() if l.strip() and not l.strip().startswith("[")][:4]
    pk = C.load_json(os.path.join(D, "prompt_pack.json"), default=None) or {}
    look = (pk.get("style_line") or "").strip()
    return ("Professional portrait music poster artwork for the song \"%s\". " % title
            + ("Sound and mood: %s. " % style if style else "")
            + ("Feeling of these lines: \"%s\". " % " / ".join(lines) if lines else "")
            + ("Look: %s. " % look if look else "Cinematic, painterly, refined colour, timeless. ")
            + FINISH.strip())


def state(slug):
    D = C.song_dir(slug); cfg = media_cfg.load(); q = cfg["image_quality"]
    return {"prompt": _read(D, "poster_prompt.txt") or default_prompt(slug), "has": os.path.isfile(os.path.join(D, "poster_2x3.png")),
            "v": int(os.path.getmtime(os.path.join(D, "poster_2x3.png"))) if os.path.isfile(os.path.join(D, "poster_2x3.png")) else 0,
            "style": current_style(D), "styles": list(STYLES), "usd": IO.estimate(q, SIZE, IO.model_name(cfg)), "quality": q, "key": bool(media_cfg.get_key("openai"))}


def _fit(d, text, path, size, max_w, min_size=48):
    while size > min_size:
        f = ImageFont.truetype(path, size)
        if d.textlength(text, font=f) <= max_w: return f
        size -= 8
    return ImageFont.truetype(path, min_size)


def _mark(im, cx, y, h=84):
    """The NAVAAN logo mark (scripts/brand/mark.png, gold with its own transparency), centred on cx."""
    m = Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "brand", "mark.png")).convert("RGBA")
    m = m.resize((round(m.width * h / m.height), h), Image.LANCZOS); im.paste(m, (cx - m.width // 2, y), m)


def _text(im, xy, text, font, fill, anchor):
    """Text with a soft dark shadow, so it reads on any art."""
    sh = Image.new("L", im.size, 0); ImageDraw.Draw(sh).text((xy[0] + 3, xy[1] + 4), text, font=font, fill=170, anchor=anchor)
    im.paste(Image.new("RGB", im.size, (6, 8, 16)), (0, 0), sh.filter(ImageFilter.GaussianBlur(7)))
    ImageDraw.Draw(im).text(xy, text, font=font, fill=fill, anchor=anchor)


def current_style(D):
    s = _read(D, "poster_style.txt"); return s if s in STYLES else "bold"


def typeset(slug, art_path=None, style=None):
    """The logo mark and NAVAAN across the top, the title in a display font over a shaded lower third, a gold rule, the site at the foot. Free, no model call."""
    D = C.song_dir(slug); art = Image.open(art_path or os.path.join(D, "poster_art.png")).convert("RGB")
    style = style if style in STYLES else current_style(D); file, px, align = STYLES[style]; path = os.path.join(FONTS, file)
    title = (_read(D, "title.txt").splitlines() or [slug])[0]; native, lat = split_title(title)
    im = cover_scale(art, W, H); shade(im, 0, 225, 0.5); pad = 84; cx = W // 2 if align == "center" else pad; anchor = "ms" if align == "center" else "ls"
    d = ImageDraw.Draw(im); f = latin(34)
    _mark(im, W // 2, pad - 30, 140); d.text((W // 2, pad + 150), "N A V A A N", font=f, fill=(240, 200, 140), anchor="mm")
    y = H - 150; d.text((W // 2, H - 64), "navaan.online", font=latin(28), fill=(235, 225, 205), anchor="mm")
    d.line((pad if align == "left" else W // 2 - 60, y, (pad + 120) if align == "left" else W // 2 + 60, y), fill=GOLD, width=4); y -= 34
    if lat:
        fl = _fit(d, lat, path, int(px * 0.4), W - 2 * pad); _text(im, (cx, y), lat, fl, GOLD, anchor); y -= int(fl.size * 1.35)
    if native:
        fn = _fit(d, native, path, px, W - 2 * pad); _text(im, (cx, y), native, fn, (255, 246, 228), anchor)
    im.save(os.path.join(D, "poster_2x3.png"), optimize=True)


def use_picture(slug, data):
    """Your own picture as the poster art (free): saved as the art, then typeset."""
    D = C.song_dir(slug)
    try: Image.open(io.BytesIO(data)).convert("RGB").save(os.path.join(D, "poster_art.png"), optimize=True)
    except Exception as e: raise ValueError("That is not a picture I can read.") from e
    typeset(slug)


def generate(slug, prompt, style=None):
    prompt = (prompt or "").strip()
    if len(prompt) < 20: raise ValueError("Write a prompt of at least a sentence.")
    cfg = media_cfg.load(); q = cfg["image_quality"]; cost = IO.check_cap(q, cfg, SIZE)   # ValueError when over the run cap
    key = media_cfg.get_key("openai")
    if not key: raise ValueError("No OpenAI key. Paste it in Settings, Pictures and voice.")
    D = C.song_dir(slug)
    raw = IO.request_image(prompt[:3500], q, key, SIZE, IO.model_name(cfg))
    media_cfg.add_usage(openai_usd=cost)   # spent now, whatever happens to the file
    Image.open(io.BytesIO(raw)).convert("RGB").save(os.path.join(D, "poster_art.png"), optimize=True)
    with open(os.path.join(D, "poster_prompt.txt"), "w", encoding="utf-8") as f: f.write(prompt + "\n")
    if style in STYLES:
        with open(os.path.join(D, "poster_style.txt"), "w") as f: f.write(style)
    typeset(slug)
    return cost


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit("usage: poster.py <slug> [--prompt TEXT] [--estimate]")
    if "--estimate" in a: print(json.dumps(state(a[0]))); sys.exit(0)
    p = a[a.index("--prompt") + 1] if "--prompt" in a else default_prompt(a[0])
    try: print("poster_2x3.png, about $%.3f" % generate(a[0], p))
    except (ValueError, RuntimeError) as e: sys.exit("navaan: " + str(e))
