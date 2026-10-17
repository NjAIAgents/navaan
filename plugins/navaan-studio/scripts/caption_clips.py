#!/usr/bin/env python3
"""caption_clips.py <slug> [16x9|reel|own]

Burn lyric captions onto the video using MEASURED timing from songs/<slug>/caption_cues.json ([[start, end, text], ...]).
  16x9 reads final_16x9.mp4        and writes final_16x9_cap.mp4
  reel reads final_reel_sync.mp4   and writes final_reel_cap.mp4  (cue times are shifted by reel_start.json start)
  own  reads final_reel_9x16.mp4   and writes final_reel_9x16_cap.mp4  (the reel cut from your own pictures; cue times are shifted by the start in reel_report.json)
Needs Pillow and ffmpeg. Set NAVAAN_FONT if no Devanagari font is found.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import tool, song_dir, duration, run, load_json, font_for
from PIL import Image, ImageDraw, ImageFilter


def plan(cues, off, total):
    """[(start, end, text)] of the captions that fall inside a clip of length total that begins off seconds into the song."""
    items = []
    for i, (a, e, text) in enumerate(cues):
        nxt = cues[i + 1][0] if i + 1 < len(cues) else e + 2
        a2 = a - 0.1 - off
        b = min(e + 0.35, nxt - 0.05) - off
        if b <= 0.5 or a2 >= total - 0.5:
            continue
        items.append((max(a2, 0.3), min(b, total - 0.3), text))
    return items


def fit_lines(text, size, width, measure, limit=0.88):
    """(lines, size) so that every line fits inside `limit` of the frame width: one line if it fits, else two lines split near the middle, shrinking the type (down to 60%) when a line is still too wide.
    measure(text, size) is the drawn width of a line at a size."""
    if measure(text, size) <= width * limit: return [text], size
    words = text.split(" ")
    lines = [text]
    if len(words) >= 2:
        cut = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
        lines = [" ".join(words[:cut]), " ".join(words[cut:])]
    s = size
    while s > size * 0.6 and max(measure(l, s) for l in lines) > width * limit: s -= 2
    return lines, s


def main(slug, mode):
    D = song_dir(slug)
    cues = load_json(f"{D}/caption_cues.json")
    W, H = (1920, 1080) if mode == "16x9" else (1080, 1920)
    base = {"16x9": f"{D}/final_16x9.mp4", "reel": f"{D}/final_reel_sync.mp4", "own": f"{D}/final_reel_9x16.mp4"}[mode]
    if not os.path.exists(base):
        sys.exit(f"navaan: missing {base}. Build it first.")
    total = duration(base)
    if mode == "16x9": off = 0.0
    elif mode == "own": off = float((load_json(f"{D}/reel_report.json", default={}) or {}).get("start") or 0.0)  # where the reel begins in the song
    else: off = float(load_json(f"{D}/reel_start.json")["start"])
    items = plan(cues, off, total)
    size, y = (54, 900) if mode == "16x9" else (46, 1450)
    tmp = f"{D}/.cache/cap_{mode}"; os.makedirs(tmp, exist_ok=True)
    inputs, fc, last = ["-i", base], [], "[0:v]"
    for i, (a, b, text) in enumerate(items):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
        lines, sz = fit_lines(text, size, W, lambda t, s: dr.textlength(t, font=font_for(t, s)))   # a long line wraps to two and fits the frame; it used to run off both edges
        lh = round(sz * 1.25); y0 = y - (len(lines) - 1) * lh   # two lines grow upward, so the bottom of the block stays where one line sat
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
        for k, ln in enumerate(lines):
            f = font_for(ln, sz); x = (W - dr.textlength(ln, font=f)) / 2   # Hindi lines in a Devanagari font, English lines in one that has the letters
            sd.text((x, y0 + k * lh), ln, font=f, fill=(0, 0, 0, 235))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
        for k, ln in enumerate(lines):
            f = font_for(ln, sz); dr.text(((W - dr.textlength(ln, font=f)) / 2, y0 + k * lh), ln, font=f, fill=(255, 238, 205, 255))
        p = f"{tmp}/c{i:03d}.png"; im.save(p)
        inputs += ["-loop", "1", "-framerate", "24", "-t", f"{b + 1:.2f}", "-i", p]
        fc.append(f"[{i + 1}:v]format=rgba,fade=t=in:st={a:.2f}:d=0.4:alpha=1,fade=t=out:st={b - 0.4:.2f}:d=0.4:alpha=1[c{i}]")
        fc.append(f"{last}[c{i}]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[m{i}]")
        last = f"[m{i}]"
    out = os.environ.get("NAVAAN_OUT") or (f"{D}/final_reel_9x16_cap.mp4" if mode == "own" else f"{D}/final_{mode}_cap.mp4")
    run([tool("ffmpeg"), "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc), "-map", last, "-map", "0:a",
         "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", out])
    print("wrote", out, len(items), "captions", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2 or (len(sys.argv) > 2 and sys.argv[2] not in ("16x9", "reel", "own")):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "16x9")
