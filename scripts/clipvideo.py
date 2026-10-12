#!/usr/bin/env python3
"""clipvideo.py <slug> [16x9|reel]  video built only from the Flow clips (no cover image).
Audio is copied from anim_<mode>.mp4 (same window as before)."""
import subprocess, sys, os, json
ROOT = os.path.expanduser("~/Desktop/github/njaiagents/navaan")
CLIPS = f"{ROOT}/songs/song-001/clips"
FF = "/opt/homebrew/bin/ffmpeg"
FP = "/opt/homebrew/bin/ffprobe"
XF = 1.5
FPS = 24
# story order with the fraction of the song where each scene starts
STORY = [("c1_diya.mp4", 0.0), ("c3_koel.mp4", .28), ("c2_river.mp4", .36), ("c4_rain.mp4", .56), ("c5_dawn.mp4", .84)]
PAN = {"c3_koel.mp4": (.35, .55), "c4_rain.mp4": (.30, .50), "c1_diya.mp4": (.30, .52), "c2_river.mp4": (.30, .42), "c5_dawn.mp4": (.45, .58)}


def run(c):
    subprocess.run(c, check=True)


def dur(p):
    return float(subprocess.check_output([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).strip())


def boom(slug, mode, f):
    """8s clip -> 20s boomerang, scaled/cropped to target."""
    W, H = (1920, 1080) if mode == "16x9" else (1080, 1920)
    out = f"/tmp/boom_{mode}_{f}"
    if os.path.exists(out):
        return out
    pre = "split[f][r];[r]reverse[rv];[f][rv]concat=n=2:v=1,setpts=PTS*1.25"
    if mode == "16x9":
        vf = f"fps={FPS},{pre},scale={W}:{H}:flags=lanczos,unsharp=5:5:0.6,setsar=1"
        fc = f"[0:v]{vf}[o]"
    else:
        a, b = PAN[f]
        fc = (f"[0:v]fps={FPS},{pre},split[x][y];"
              f"[x]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:6,eq=brightness=-0.08[bg];"
              f"[y]crop=640:720:'(iw-640)*({a}+({b}-{a})*t/20)':0,scale={W}:-2:flags=lanczos,unsharp=5:5:0.6[fg];"
              f"[bg][fg]overlay=0:(H-h)/2,setsar=1[o]")
    run([FF, "-y", "-v", "error", "-i", f"{CLIPS}/{f}", "-filter_complex", fc, "-map", "[o]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", out])
    return out


def main(slug, mode):
    D = f"{ROOT}/songs/{slug}"
    src = f"{D}/anim_{mode}.mp4"
    total = dur(src)
    spans = []
    for i, (f, fr) in enumerate(STORY):
        end = STORY[i + 1][1] if i + 1 < len(STORY) else 1.0
        spans.append((f, fr * total, end * total))
    if mode == "reel":   # 5 equal scenes
        spans = [(f, k * total / 5, (k + 1) * total / 5) for k, (f, _) in enumerate(STORY)]
    inputs, fc, last, t_acc = [], [], None, 0.0
    for i, (f, a, b) in enumerate(spans):
        L = (b - a) + (XF if i + 1 < len(spans) else 0)
        inputs += ["-stream_loop", "-1", "-t", f"{L:.2f}", "-i", boom(slug, mode, f)]
        if i == 0:
            last = "[0:v]"
        else:
            off = round(a, 2)
            fc.append(f"{last}[{i}:v]xfade=transition=fade:duration={XF}:offset={off}[x{i}]")
            last = f"[x{i}]"
    inputs += ["-i", src]
    ai = len(spans)
    fc.append(f"{last}vignette=PI/5,eq=saturation=1.05,noise=alls=2:allf=t,fade=t=in:st=0:d=2,fade=t=out:st={total-3:.2f}:d=3[v]")
    out = f"{D}/final_{mode}.mp4"
    run([FF, "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", f"{ai}:a",
         "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", out])
    print("wrote", out, [(f, round(a), round(b)) for f, a, b in spans], flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "16x9")
