#!/usr/bin/env python3
"""caption_clips.py <slug> [16x9|reel]  burns lyric captions onto final_<mode>.mp4 -> final_<mode>_cap.mp4
Timing is MEASURED: caption_cues.json comes from vocal separation + speech recognition (see scripts/align_notes.md)."""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(__file__))
import animate as A
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = A.ROOT


def timing(slug):
    D = f"{ROOT}/songs/{slug}"
    mp3 = f"{D}/final.mp3"
    env = A.envelope(mp3); dp = A.dips(env); total = A.duration(mp3)
    blocks = A.parse_lyrics(f"{D}/lyrics.txt")
    lines = [(bi, l) for bi, b in enumerate(blocks) for l in b]
    on = next(i for i, v in enumerate(env) if v > 0.42)
    off = max(i for i, v in enumerate(env) if v > 0.30 and i < total - 6)
    n = len(lines); span = off - on
    t = [on + span * i / n for i in range(n)]
    starts = {}
    for i, (bi, _) in enumerate(lines): starts.setdefault(bi, i)
    for bi, i in starts.items():
        near = min(dp, key=lambda d: abs(d - t[i]), default=None)
        if near is not None and abs(near - t[i]) <= 6 and i > 0:
            t[i] = near + 1.0
    for i in range(1, n):
        if t[i] <= t[i - 1] + 1.5: t[i] = t[i - 1] + 1.5
    st = next((x + 1 for x in dp if x >= 40), 30)
    return [(a, l) for a, (_, l) in zip(t, lines)], st


def main(slug, mode):
    D = f"{ROOT}/songs/{slug}"
    # real timing: caption_cues.json = [[start, end, text], ...] measured from the isolated vocal track
    cues3 = json.load(open(f"{D}/caption_cues.json"))
    cues = [(c[0], c[2]) for c in cues3]
    W, H = (1920, 1080) if mode == "16x9" else (1080, 1920)
    base = f"{D}/final_{mode}.mp4" if mode == "16x9" else f"{D}/final_reel_sync.mp4"
    total = A.duration(base)
    off = 0.0 if mode == "16x9" else json.load(open(f"{D}/reel_start.json"))["start"]
    items = []
    for i, (a, e, text) in enumerate(cues3):
        nxt = cues3[i + 1][0] if i + 1 < len(cues3) else e + 2
        a2 = a - 0.1
        b = min(e + 0.35, nxt - 0.05)
        a2 -= off; b -= off
        if b <= 0.5 or a2 >= total - 0.5: continue
        items.append((max(a2, 0.3), min(b, total - 0.3), text))
    size, y = (54, 900) if mode == "16x9" else (46, 1450)
    fnt = ImageFont.truetype("/System/Library/Fonts/Kohinoor.ttc", size, index=2)
    tmp = f"/tmp/cap_{slug}_{mode}"; os.makedirs(tmp, exist_ok=True)
    inputs = ["-i", base]; fc = []; last = "[0:v]"
    for i, (a, b, text) in enumerate(items):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
        w = dr.textlength(text, font=fnt); x = (W - w) / 2
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).text((x, y), text, font=fnt, fill=(0, 0, 0, 235))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
        dr.text((x, y), text, font=fnt, fill=(255, 238, 205, 255))
        p = f"{tmp}/c{i:03d}.png"; im.save(p)
        inputs += ["-loop", "1", "-framerate", "24", "-t", f"{b + 1:.2f}", "-i", p]
        fc.append(f"[{i + 1}:v]format=rgba,fade=t=in:st={a:.2f}:d=0.4:alpha=1,fade=t=out:st={b - 0.4:.2f}:d=0.4:alpha=1[c{i}]")
        fc.append(f"{last}[c{i}]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[m{i}]")
        last = f"[m{i}]"
    out = f"{D}/final_{mode}_cap.mp4"
    subprocess.run(["/opt/homebrew/bin/ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc),
                    "-map", last, "-map", "0:a", "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out], check=True)
    print("wrote", out, len(items), "captions", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "16x9")
