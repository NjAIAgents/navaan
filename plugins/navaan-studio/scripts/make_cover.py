#!/usr/bin/env python3
"""make_cover.py  build the cover files of a song from one piece of art and the song title. Needs Pillow.

  make_cover.py <slug> [--src FILE] [--out DIR] [--title TEXT]

Art, first found: --src, cover_art.png|jpg|jpeg (the cover generated in Flow), refs/cover.png|jpg (made by you), cover_flow.jpg (a frame of clip 1).
Writes cover_1x1.png (embedded in the mp3 and used for Instagram), cover_16x9.png and thumb_16x9.jpg (YouTube thumbnail 1280x720).
The title comes from title.txt: native script, with the Latin spelling in brackets if present, for example "पता ही ना चला (Pata Hi Na Chala)".
Generated art must carry no lettering of its own, the title is drawn here so the native script is always correct.
"""
import os, sys, re, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import song_dir, font, cfg
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ART = ["cover_art.png", "cover_art.jpg", "cover_art.jpeg", "refs/cover.png", "refs/cover.jpg", "cover_flow.jpg"]
LATIN = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]


def latin(size):
    for p in LATIN:
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()


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
    return y


def make(slug, src=None, out=None, title=None):
    D = song_dir(slug); out = out or D
    path = src or next((os.path.join(D, a) for a in ART if os.path.exists(os.path.join(D, a))), None)
    if not path: sys.exit("navaan: no cover art found. Expected cover_art.png from Flow, refs/cover.png, or cover_flow.jpg.")
    art = Image.open(path).convert("RGB")
    tp = os.path.join(D, "title.txt"); title = title or (open(tp, encoding="utf-8").read().strip().splitlines()[0] if os.path.exists(tp) else slug)
    native, lat = split_title(title); artist = cfg("artist.name") or "NAVAAN"
    # 1:1, art full bleed, title low left
    sq = cover_scale(art, 1080, 1080); shade(sq, 0, 200, 0.5); pad = 70
    ImageDraw.Draw(sq).text((1080 - pad, pad), artist, font=latin(34), fill=(255, 255, 255), anchor="ra")
    title_block(sq, native, lat, pad, 1080 - pad, 1080 - 2 * pad, 170, 62, artist)
    sq.save(os.path.join(out, "cover_1x1.png"))
    # 16:9, blurred extension of the art as background, the sharp square on the right, title on the left
    W, H = 1920, 1080
    bg = cover_scale(art, W, H).filter(ImageFilter.GaussianBlur(40)); bg = Image.blend(bg, Image.new("RGB", (W, H), (8, 10, 18)), 0.45)
    side = 900; bg.paste(art.resize((side, side), Image.LANCZOS) if art.width == art.height else cover_scale(art, side, side), (W - side - 90, (H - side) // 2))
    ImageDraw.Draw(bg).text((90, 90), artist, font=latin(40), fill=(255, 255, 255))
    title_block(bg, native, lat, 90, H // 2 + 190, W - side - 90 - 90 - 60, 190, 76, artist)
    bg.save(os.path.join(out, "cover_16x9.png")); bg.resize((1280, 720), Image.LANCZOS).save(os.path.join(out, "thumb_16x9.jpg"), quality=90)
    print(f"cover from {os.path.basename(path)}: cover_1x1.png, cover_16x9.png, thumb_16x9.jpg")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("slug"); ap.add_argument("--src"); ap.add_argument("--out"); ap.add_argument("--title")
    a = ap.parse_args(); make(a.slug, a.src, a.out, a.title)
