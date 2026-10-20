#!/usr/bin/env python3
"""make_cover.py  build the cover files of a song from one piece of art and the song title. Needs Pillow.

  make_cover.py <slug> [--src FILE] [--out DIR] [--title TEXT]

Art, first found: --src, cover_art.png|jpg|jpeg (the cover generated in Flow), refs/cover.png|jpg (made by you), cover_flow.jpg (a frame of clip 1).
Writes cover_1x1.png (embedded in the mp3 and used for Instagram), cover_16x9.png and thumb_16x9.jpg (YouTube thumbnail 1280x720).
The title comes from title.txt: native script, with the Latin spelling in brackets if present, for example "पता ही ना चला (Pata Hi Na Chala)".
Generated art must carry no lettering of its own, the title is drawn here so the native script is always correct.
The look is modern (NAV-135): MODERN_LOOK is the direction for the art, a clean sans for Latin lettering, a light shade, a tracked artist name and a short gold bar above the title.
"""
import os, sys, re, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import song_dir, font, cfg
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ART = ["cover_art.png", "cover_art.jpg", "cover_art.jpeg", "refs/cover.png", "refs/cover.jpg", "cover_flow.jpg"]
# What the art should look like (NAV-135): the same direction for a song's cover (the flow-visuals skill says it in its own words) and an album's (album_pipeline.default_prompt).
MODERN_LOOK = ("Modern contemporary cover art in the style of current streaming-era releases: one strong graphic subject or abstract form, flat or soft-gradient colour fields with fine film grain, "
               "a limited palette of two or three colours, generous negative space, crisp and minimal. Not painterly, not cinematic, no clip-art, no stock-photo look, no heavy vignette.")
# Latin lettering is a clean modern sans: Inter when it is installed, then Noto Sans, Avenir Next, Helvetica Neue, and the old Arial / DejaVu Bold last.
LATIN = [("/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf", 0), ("/usr/share/fonts/opentype/inter/Inter-Bold.otf", 0), ("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", 0),
         ("/System/Library/Fonts/Avenir Next.ttc", 2), ("/System/Library/Fonts/HelveticaNeue.ttc", 1),
         ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0), ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0), ("C:/Windows/Fonts/arialbd.ttf", 0)]
GOLD = (226, 183, 90)


def latin(size):
    for p, i in LATIN:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size, index=i)
            except OSError: continue   # expected: a font collection without that face, so the next font is tried
    return ImageFont.load_default()


def tracked(d, xy, text, font, fill, space=6, anchor="l"):
    """Small capitals with letter-spacing, the modern way to set an artist name. anchor l: xy is the left edge; r: the right edge."""
    text = text.upper(); w = sum(d.textlength(c, font=font) + space for c in text) - space; x = xy[0] - (w if anchor == "r" else 0)
    for c in text:
        d.text((x, xy[1]), c, font=font, fill=fill); x += d.textlength(c, font=font) + space
    return w


def split_title(t):
    m = re.match(r"^(.*?)\s*\((.+)\)\s*$", t.strip())
    native, lat = (m.group(1).strip(), m.group(2).strip()) if m else (t.strip(), "")
    if native and all(ord(c) < 0x250 for c in native): return "", native  # a Latin only title is drawn as the main line
    return native, lat


def fit(draw, text, make_font, size, max_w, min_size=40):
    while size > min_size:
        f = make_font(size)
        if draw.textlength(text, font=f) <= max_w: return f
        size -= 6
    return make_font(min_size)


def cover_scale(img, w, h):
    s = max(w / img.width, h / img.height); im = img.resize((int(img.width * s) + 1, int(img.height * s) + 1), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def shade(im, top_a, bot_a, frac=0.5):
    w, h = im.size; band = int(h * frac); g = Image.new("L", (1, band))
    for y in range(band): g.putpixel((0, y), int(top_a + (bot_a - top_a) * y / max(1, band - 1)))
    im.paste(Image.new("RGB", (w, band), (8, 10, 18)), (0, h - band), g.resize((w, band)))


def title_block(im, native, lat, x, y_bottom, max_w, native_px, latin_px, artist):
    d = ImageDraw.Draw(im)
    fl = fit(d, lat or native, latin, latin_px, max_w) if (lat or not native) else None
    fn = fit(d, native, font, native_px, max_w) if native else None
    y = y_bottom
    if fl and (lat or not native):
        y -= fl.size + 6; d.text((x, y), lat or native, font=fl, fill=(240, 200, 140) if native else (255, 244, 224))
    if fn:
        y -= int(fn.size * 1.45); d.text((x, y), native, font=fn, fill=(255, 244, 224))
    d.rounded_rectangle((x, y - 30, x + 76, y - 22), radius=4, fill=GOLD)   # a short gold bar above the title
    return y


def make(slug, src=None, out=None, title=None):
    D = song_dir(slug); out = out or D
    path = src or next((os.path.join(D, a) for a in ART if os.path.exists(os.path.join(D, a))), None)
    if not path: sys.exit("navaan: no cover art found. Expected cover_art.png from Flow, refs/cover.png, or cover_flow.jpg.")
    art = Image.open(path).convert("RGB")
    tp = os.path.join(D, "title.txt"); title = title or (open(tp, encoding="utf-8").read().strip().splitlines()[0] if os.path.exists(tp) else slug)
    native, lat = split_title(title); artist = cfg("artist.name") or "NAVAAN"
    # 1:1, art full bleed, title low left
    sq = cover_scale(art, 1080, 1080); shade(sq, 0, 150, 0.42); pad = 76   # a lighter shade than before: the art is the cover
    tracked(ImageDraw.Draw(sq), (pad, pad), artist, latin(26), (255, 255, 255), 7)
    title_block(sq, native, lat, pad, 1080 - pad, 1080 - 2 * pad, 150, 104, artist)
    sq.save(os.path.join(out, "cover_1x1.png"))
    # 16:9, blurred extension of the art as background, the sharp square on the right, title on the left
    W, H = 1920, 1080
    bg = cover_scale(art, W, H).filter(ImageFilter.GaussianBlur(40)); bg = Image.blend(bg, Image.new("RGB", (W, H), (8, 10, 18)), 0.45)
    side = 900; bg.paste(art.resize((side, side), Image.LANCZOS) if art.width == art.height else cover_scale(art, side, side), (W - side - 90, (H - side) // 2))
    tracked(ImageDraw.Draw(bg), (90, 90), artist, latin(30), (255, 255, 255), 8)
    title_block(bg, native, lat, 90, H // 2 + 190, W - side - 90 - 90 - 60, 170, 120, artist)
    bg.save(os.path.join(out, "cover_16x9.png")); bg.resize((1280, 720), Image.LANCZOS).save(os.path.join(out, "thumb_16x9.jpg"), quality=90)
    print(f"cover from {os.path.basename(path)}: cover_1x1.png, cover_16x9.png, thumb_16x9.jpg")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("slug"); ap.add_argument("--src"); ap.add_argument("--out"); ap.add_argument("--title")
    a = ap.parse_args(); make(a.slug, a.src, a.out, a.title)
