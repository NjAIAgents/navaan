#!/usr/bin/env python3
"""clipvideo.py <slug> [16x9|reel]

Build a video only from the song's Flow clips (songs/<slug>/clips/*.mp4), boomerang looped and cross faded.
Audio comes from songs/<slug>/final.mp3.
  16x9 -> songs/<slug>/final_16x9.mp4   (whole song)
  reel -> songs/<slug>/final_reel_sync.mp4   (9:16, audio window from reel_start.json {"start": s, "dur": d}, default 30 and 60)

Optional songs/<slug>/story.json: {"scenes": [{"clip": "c1_diya.mp4", "at": 0.0, "pan": [0.3, 0.5]}, ...]}
  at = fraction of the song where the scene starts (full video only), pan = horizontal crop sweep for the reel.
Without it, clips are used in name order, evenly spaced.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import tool, song_dir, duration, run, load_json

XF, FPS = 1.5, 24


def boom(D, mode, f, pan, cache):
    W, H = (1920, 1080) if mode == "16x9" else (1080, 1920)
    out = f"{cache}/boom_{mode}_{f}"
    if os.path.exists(out):
        return out
    pre = "split[f][r];[r]reverse[rv];[f][rv]concat=n=2:v=1,setpts=PTS*1.25"
    if mode == "16x9":
        fc = f"[0:v]fps={FPS},{pre},scale={W}:{H}:flags=lanczos,unsharp=5:5:0.6,setsar=1[o]"
    else:
        a, b = pan
        fc = (f"[0:v]fps={FPS},{pre},split[x][y];"
              f"[x]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:6,eq=brightness=-0.08[bg];"
              f"[y]crop=trunc(ih*8/9/2)*2:ih:'(iw-ow)*({a}+({b}-{a})*t/20)':0,scale={W}:-2:flags=lanczos,unsharp=5:5:0.6[fg];"
              f"[bg][fg]overlay=0:(H-h)/2,setsar=1[o]")
    run([tool("ffmpeg"), "-y", "-v", "error", "-i", f"{D}/clips/{f}", "-filter_complex", fc, "-map", "[o]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", out])
    return out


def scenes(D):
    story = load_json(f"{D}/story.json", default={}).get("scenes")
    if story:
        return [(s["clip"], float(s.get("at", i / len(story))), tuple(s.get("pan", (0.3, 0.5)))) for i, s in enumerate(story)]
    clips = sorted(f for f in os.listdir(f"{D}/clips") if f.lower().endswith(".mp4"))
    if not clips:
        sys.exit(f"navaan: no clips in {D}/clips")
    return [(c, i / len(clips), (0.3, 0.5)) for i, c in enumerate(clips)]


def main(slug, mode):
    D = song_dir(slug)
    mp3 = f"{D}/final.mp3"
    song = duration(mp3)
    if mode == "reel":
        rs = load_json(f"{D}/reel_start.json", default={"start": 30.0, "dur": 60.0})
        a0, total = float(rs["start"]), min(float(rs["dur"]), song - float(rs["start"]))
    else:
        a0, total = 0.0, song
    sc = scenes(D)
    if mode == "reel":
        spans = [(f, k * total / len(sc), (k + 1) * total / len(sc), p) for k, (f, _, p) in enumerate(sc)]
    else:
        spans = [(f, fr * total, (sc[i + 1][1] if i + 1 < len(sc) else 1.0) * total, p) for i, (f, fr, p) in enumerate(sc)]
    cache = f"{D}/.cache"; os.makedirs(cache, exist_ok=True)
    inputs, fc, last = [], [], None
    for i, (f, a, b, p) in enumerate(spans):
        L = (b - a) + (XF if i + 1 < len(spans) else 0)
        inputs += ["-stream_loop", "-1", "-t", f"{L:.2f}", "-i", boom(D, mode, f, p, cache)]
        if i == 0:
            last = "[0:v]"
        else:
            fc.append(f"{last}[{i}:v]xfade=transition=fade:duration={XF}:offset={round(a, 2)}[x{i}]")
            last = f"[x{i}]"
    n = len(spans)
    inputs += ["-ss", f"{a0:.2f}", "-t", f"{total:.2f}", "-i", mp3]
    fc.append(f"{last}vignette=PI/5,eq=saturation=1.05,noise=alls=2:allf=t,fade=t=in:st=0:d=2,fade=t=out:st={total-3:.2f}:d=3[v]")
    fc.append(f"[{n}:a]afade=t=in:st=0:d=0.4,afade=t=out:st={max(total-2.5,0):.2f}:d=2.5[a]")
    out = os.environ.get("NAVAAN_OUT") or (f"{D}/final_16x9.mp4" if mode == "16x9" else f"{D}/final_reel_sync.mp4")
    run([tool("ffmpeg"), "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
         "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    print("wrote", out, [(f, round(a), round(b)) for f, a, b, _ in spans], flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2 or (len(sys.argv) > 2 and sys.argv[2] not in ("16x9", "reel")):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "16x9")
