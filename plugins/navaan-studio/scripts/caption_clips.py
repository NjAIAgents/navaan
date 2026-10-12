#!/usr/bin/env python3
"""caption_clips.py <slug> [16x9|reel]

Burn lyric captions onto the video using MEASURED timing from songs/<slug>/caption_cues.json ([[start, end, text], ...]).
  16x9 reads final_16x9.mp4        and writes final_16x9_cap.mp4
  reel reads final_reel_sync.mp4   and writes final_reel_cap.mp4  (cue times are shifted by reel_start.json start)
Needs Pillow and ffmpeg. Set NAVAAN_FONT if no Devanagari font is found.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import tool, song_dir, duration, run, load_json, font
from PIL import Image, ImageDraw, ImageFilter


def main(slug, mode):
    D = song_dir(slug)
    cues = load_json(f"{D}/caption_cues.json")
    W, H = (1920, 1080) if mode == "16x9" else (1080, 1920)
    base = f"{D}/final_16x9.mp4" if mode == "16x9" else f"{D}/final_reel_sync.mp4"
    if not os.path.exists(base):
        sys.exit(f"navaan: missing {base}. Build it with clipvideo.py first.")
    total = duration(base)
    off = 0.0 if mode == "16x9" else float(load_json(f"{D}/reel_start.json")["start"])
    items = []
    for i, (a, e, text) in enumerate(cues):
        nxt = cues[i + 1][0] if i + 1 < len(cues) else e + 2
        a2 = a - 0.1 - off
        b = min(e + 0.35, nxt - 0.05) - off
        if b <= 0.5 or a2 >= total - 0.5:
            continue
        items.append((max(a2, 0.3), min(b, total - 0.3), text))
    size, y = (54, 900) if mode == "16x9" else (46, 1450)
    fnt = font(size)
    tmp = f"{D}/.cache/cap_{mode}"; os.makedirs(tmp, exist_ok=True)
    inputs, fc, last = ["-i", base], [], "[0:v]"
    for i, (a, b, text) in enumerate(items):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
        x = (W - dr.textlength(text, font=fnt)) / 2
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).text((x, y), text, font=fnt, fill=(0, 0, 0, 235))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
        dr.text((x, y), text, font=fnt, fill=(255, 238, 205, 255))
        p = f"{tmp}/c{i:03d}.png"; im.save(p)
        inputs += ["-loop", "1", "-framerate", "24", "-t", f"{b + 1:.2f}", "-i", p]
        fc.append(f"[{i + 1}:v]format=rgba,fade=t=in:st={a:.2f}:d=0.4:alpha=1,fade=t=out:st={b - 0.4:.2f}:d=0.4:alpha=1[c{i}]")
        fc.append(f"{last}[c{i}]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[m{i}]")
        last = f"[m{i}]"
    out = os.environ.get("NAVAAN_OUT") or f"{D}/final_{mode}_cap.mp4"
    run([tool("ffmpeg"), "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc), "-map", last, "-map", "0:a",
         "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", out])
    print("wrote", out, len(items), "captions", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2 or (len(sys.argv) > 2 and sys.argv[2] not in ("16x9", "reel")):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "16x9")
