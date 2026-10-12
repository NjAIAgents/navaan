#!/usr/bin/env python3
"""Animated cover video: Ken Burns scenes cut on the song's quiet moments, mist, dust, petals.
usage: animate.py <slug> [16x9|reel] [captions]
  16x9   -> songs/<slug>/anim_16x9.mp4        (full song, no captions)
  16x9 captions -> anim_16x9_cap.mp4          (adds estimated-timing lyric captions; DRAFT)
  reel   -> anim_reel.mp4                      (9:16, 60 s from the first chorus-like section)
Needs: ffmpeg on PATH, .venv with pillow + numpy.
"""
import subprocess, sys, os, re, random, math, json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS, XF = 25, 1.5
FOCI = [  # cx, cy, cx1, cy1, z0, z1  (fractions of the square cover; z=1 is full width)
    (.50, .50, .50, .50, 1.00, 1.25),  # 0 wide opener
    (.49, .22, .49, .20, 1.40, 1.80),  # 1 moon in window
    (.66, .62, .69, .58, 1.50, 2.00),  # 2 diya
    (.33, .66, .36, .64, 1.40, 1.80),  # 3 lotus
    (.49, .42, .49, .40, 1.70, 1.35),  # 4 river through window
    (.60, .80, .58, .78, 1.60, 1.35),  # 5 coin on table
    (.62, .40, .40, .40, 1.45, 1.45),  # 6 curtain pan
    (.69, .55, .69, .52, 2.00, 1.75),  # 7 flame close
    (.50, .50, .50, .50, 1.80, 1.00),  # 8 final pull back
]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(" ".join(cmd)[:400]); print(r.stderr[-1500:]); sys.exit(1)


def duration(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                capture_output=True, text=True).stdout)


def envelope(f):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(float) / 32768
    n = len(x) // 8000
    r = np.array([np.sqrt((x[i * 8000:(i + 1) * 8000] ** 2).mean()) for i in range(n)])
    return r / r.max()


def dips(r, lo=8, hi_margin=10, gap=12, thr=0.30):
    c = [i for i in range(1, len(r) - 1) if r[i] < thr and r[i] <= r[i - 1] and r[i] <= r[i + 1] and lo < i < len(r) - hi_margin]
    out = []
    for i in c:
        if not out or i - out[-1] >= gap:
            out.append(i)
        elif r[i] < r[out[-1]]:
            out[-1] = i
    return out


def upscale(cover, path):
    im = Image.open(cover).convert("RGB").resize((4096, 4096), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=3, percent=60, threshold=2))
    im.save(path)


def seg_clip(src, idx, dur, W, H, out):
    cx, cy, cx1, cy1, z0, z1 = FOCI[idx]
    n = int(round(dur * FPS))
    z = f"{z0}+({z1}-{z0})*on/{n}"
    zz = f"({z})"
    cxe = f"({cx}+({cx1}-{cx})*on/{n})"
    cye = f"({cy}+({cy1}-{cy})*on/{n})"
    x = f"max(0,min(iw-iw/{zz},{cxe}*iw-iw/{zz}/2))"
    y = f"max(0,min(ih-ih/{zz},{cye}*ih-ih/{zz}/2))"
    S = max(W, H)
    vf = f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={S}x{S}:fps={FPS},crop={W}:{H}:{(S-W)//2}:{(S-H)//2}"
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", vf, "-frames:v", str(n), "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", out])


def make_layers(W, H, d):
    random.seed(7); np.random.seed(7)
    # dust: warm specks, tile height H repeated twice (rises)
    def dots(count, rmin, rmax, color, alpha):
        t = Image.new("RGBA", (W, H * 2), (0, 0, 0, 0))
        for _ in range(count):
            x, y = random.uniform(0, W), random.uniform(0, H)
            r = random.uniform(rmin, rmax)
            for dy in (0, H):
                lay = Image.new("RGBA", t.size, (0, 0, 0, 0))
                ImageDraw.Draw(lay).ellipse([x - r, y + dy - r, x + r, y + dy + r], fill=color + (int(alpha * random.uniform(.5, 1)),))
                t.alpha_composite(lay.filter(ImageFilter.GaussianBlur(r * .6)))
        return t
    dust = dots(120, 1.2, 3.2, (255, 214, 150), 190)
    dust.save(f"{d}/dust.png")
    pet = Image.new("RGBA", (W, H * 2), (0, 0, 0, 0))
    for _ in range(26):
        x, y = random.uniform(0, W), random.uniform(0, H)
        w, h = random.uniform(9, 17), random.uniform(5, 9)
        ang = random.uniform(0, 180)
        p = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        ImageDraw.Draw(p).ellipse([20 - w, 20 - h, 20 + w, 20 + h], fill=(255, 226, 232, 215))
        p = p.rotate(ang, resample=Image.BICUBIC)
        for dy in (0, H):
            pet.alpha_composite(p, (int(x) - 20, int(y + dy) - 20)) if 0 <= x - 20 < W - 40 and 0 <= y + dy - 20 < 2 * H - 40 else None
    pet.save(f"{d}/petals.png")
    # mist: periodic soft noise, tile width W repeated twice
    small = np.random.rand(6, 10)
    wide = np.concatenate([small, small, small], axis=1)   # periodic in x so the scroll loops with no seam
    big3 = Image.fromarray((wide * 255).astype("uint8")).resize((W * 3, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(H // 8))
    big = big3.crop((W, 0, 2 * W, H))
    a = np.asarray(big).astype(float)
    a = (a - a.min()) / (a.max() - a.min())
    alpha = (a ** 1.6 * 55).astype("uint8")
    tile = Image.merge("RGBA", [Image.new("L", (W, H), 205), Image.new("L", (W, H), 215), Image.new("L", (W, H), 240), Image.fromarray(alpha)])
    mist = Image.new("RGBA", (W * 2, H)); mist.paste(tile, (0, 0)); mist.paste(tile, (W, 0))
    mist.save(f"{d}/mist.png")


def build(slug, mode, captions=False):
    D = f"{ROOT}/songs/{slug}"
    mp3 = f"{D}/final.mp3"
    tmp = f"/tmp/anim_{slug}_{mode}"; os.makedirs(tmp, exist_ok=True)
    W, H = (1920, 1080) if mode == "16x9" else (1080, 1920)
    total = duration(mp3)
    env = envelope(mp3)
    dp = dips(env)
    if mode == "reel":
        st = next((t + 1 for t in dp if t >= 40), 30); ln = 60
        bounds = [0.0] + [i * 10.0 for i in range(1, 6)] + [60.0]
        a_start, a_len = st, ln
    else:
        edges = [0.0] + [float(t) for t in dp] + [total]
        bounds = [0.0]
        for a, b in zip(edges, edges[1:]):
            span = b - a
            k = max(1, math.ceil(span / 26))
            bounds += [a + span * j / k for j in range(1, k + 1)]
        bounds = sorted(set(round(x, 2) for x in bounds))
        a_start, a_len = 0.0, total
    durs = [b - a for a, b in zip(bounds, bounds[1:])]
    m = len(durs)
    order = [0] + [1 + (i % 7) for i in range(m - 2)] + [8] if m >= 2 else [0]
    src = f"{tmp}/src.png"
    if not os.path.exists(src):
        upscale(f"{D}/cover_suno.jpeg", src)
    clips = []
    for i, d in enumerate(durs):
        out = f"{tmp}/seg{i:02d}.mp4"
        seg_clip(src, order[i], d + (XF if i < m - 1 else 0), W, H, out)
        clips.append(out)
        print("seg", i, round(d, 1), "s focus", order[i], flush=True)
    make_layers(W, H, tmp)
    # xfade chain
    inputs = []
    for c in clips: inputs += ["-i", c]
    ni = len(clips)
    inputs += ["-loop", "1", "-framerate", str(FPS), "-i", f"{tmp}/dust.png",
               "-loop", "1", "-framerate", str(FPS), "-i", f"{tmp}/petals.png",
               "-loop", "1", "-framerate", str(FPS), "-i", f"{tmp}/mist.png",
               "-ss", str(a_start), "-t", str(a_len), "-i", mp3]
    fc, last, off = [], "[0:v]", 0.0
    for i in range(1, ni):
        off += durs[i - 1]
        fc.append(f"{last}[{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{i}]")
        last = f"[x{i}]"
    if ni == 1: fc.append("[0:v]null[x1]"); last = "[x1]"
    dust_i, pet_i, mist_i, aud_i = ni, ni + 1, ni + 2, ni + 3
    fc += [
        f"{last}eq=brightness='0.012*sin(t*1.1)':saturation=1.06:eval=frame,vignette=PI/4.5,noise=alls=2:allf=t[g]",
        f"[g][{dust_i}:v]overlay=x=0:y='-mod(t*22,{H})':shortest=0[o1]",
        f"[o1][{pet_i}:v]overlay=x='28*sin(t/1.7)':y='-{H}+mod(t*38,{H})':shortest=0[o2]",
        f"[o2][{mist_i}:v]overlay=x='-mod(t*14,{W})':y=0:shortest=0[o3]",
        f"[o3]fade=t=in:st=0:d=2,fade=t=out:st={a_len - 3:.2f}:d=3,format=yuv420p[v]",
        f"[{aud_i}:a]afade=t=out:st={a_len - 3:.2f}:d=3[a]",
    ]
    outname = {"16x9": "anim_16x9.mp4", "reel": "anim_reel.mp4"}[mode]
    out = f"{D}/{outname}"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
         "-t", f"{a_len:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    print("wrote", out, flush=True)
    json.dump({"dips": dp, "total": total}, open(f"{tmp}/timing.json", "w"))
    return out, dp, env, total


def parse_lyrics(path):
    blocks, cur = [], []
    for line in open(path, encoding="utf-8").read().splitlines():
        s = line.strip()
        if not s:
            if cur: blocks.append(cur); cur = []
        elif s.endswith("]") or s.startswith("["):
            continue   # section tags, including malformed ones like "Intro]"
        elif re.match(r"^\[.*\]", s):
            continue
        else:
            cur.append(s)
    if cur: blocks.append(cur)
    return blocks


def caption(slug, base_mp4, dp, env, total):
    D = f"{ROOT}/songs/{slug}"
    lyr = f"{D}/lyrics.txt" if slug != "song-002" else f"{D}/lyrics.txt"
    blocks = parse_lyrics(lyr)
    lines = [(bi, l) for bi, b in enumerate(blocks) for l in b]
    on = next(i for i, v in enumerate(env) if v > 0.42)            # first vocal-ish onset
    off = max(i for i, v in enumerate(env) if v > 0.30 and i < total - 6)
    span = off - on
    n = len(lines)
    # even spread, then pull block starts toward nearby quiet dips
    t = [on + span * i / n for i in range(n)]
    starts = {}
    for i, (bi, _) in enumerate(lines): starts.setdefault(bi, i)
    for bi, i in starts.items():
        near = min(dp, key=lambda d: abs(d - t[i]), default=None)
        if near is not None and abs(near - t[i]) <= 6 and i > 0:
            shift = (near + 1.0) - t[i]
            for j in range(i, n): t[j] += shift * 0.0   # keep spacing, only snap this line
            t[i] = near + 1.0
    for i in range(1, n):
        if t[i] <= t[i - 1] + 1.5: t[i] = t[i - 1] + 1.5
    tmp = f"/tmp/anim_{slug}_cap"; os.makedirs(tmp, exist_ok=True)
    fnt = ImageFont.truetype("/System/Library/Fonts/Kohinoor.ttc", 54, index=2)
    imgs = []
    for i, (bi, text) in enumerate(lines):
        im = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        w = dr.textlength(text, font=fnt, features=["-kern"] if False else None)
        x, y = (1920 - w) / 2, 900
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).text((x, y), text, font=fnt, fill=(0, 0, 0, 230))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
        dr.text((x, y), text, font=fnt, fill=(255, 238, 205, 255))
        p = f"{tmp}/c{i:03d}.png"; im.save(p); imgs.append(p)
    inputs = ["-i", base_mp4]
    for p in imgs: inputs += ["-loop", "1", "-framerate", str(FPS), "-i", p]
    fc, last = [], "[0:v]"
    for i in range(n):
        a = t[i]; b = (t[i + 1] if i + 1 < n else a + 4) - 0.1
        b = min(b, a + 7)
        fc.append(f"[{i + 1}:v]format=rgba,fade=t=in:st={a:.2f}:d=0.4:alpha=1,fade=t=out:st={b - 0.4:.2f}:d=0.4:alpha=1[c{i}]")
        fc.append(f"{last}[c{i}]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})':shortest=0[m{i}]")
        last = f"[m{i}]"
    out = f"{D}/anim_16x9_cap.mp4"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc), "-map", last, "-map", "0:a",
         "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", out])
    json.dump([[round(x, 1), l] for x, (_, l) in zip(t, lines)], open(f"{D}/caption_timing.json", "w"), ensure_ascii=False, indent=1)
    print("wrote", out, flush=True)


if __name__ == "__main__":
    slug = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "16x9"
    caps = len(sys.argv) > 3 and sys.argv[3] == "captions"
    base = f"{ROOT}/songs/{slug}/anim_{mode}.mp4"
    if caps and os.path.exists(base):
        mp3 = f"{ROOT}/songs/{slug}/final.mp3"
        e = envelope(mp3); caption(slug, base, dips(e), e, duration(mp3))
    else:
        out, dp, e, tot = build(slug, mode)
        if caps: caption(slug, out, dp, e, tot)
