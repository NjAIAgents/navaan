#!/usr/bin/env python3
"""Cut the Flow (Veo) clips into the animated cover video at lyric-matched moments.
usage: compose.py <slug> [16x9|reel]
  16x9 -> songs/<slug>/final_16x9.mp4   (YouTube, 1920x1080)
  reel -> songs/<slug>/final_reel.mp4   (Instagram, 1080x1920, clips letterboxed on a blurred fill)
Clips live in songs/song-001/clips (shared by both language versions).
Needs songs/<slug>/anim_<mode>.mp4 from animate.py.
"""
import sys, os, json, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIPS = f"{ROOT}/songs/song-001/clips"
FPS, XF = 25, 1.0
PAN = {"c3_koel.mp4": (.35,.55), "c4_rain.mp4": (.30,.50), "c1_diya.mp4": (.30, .52), "c2_river.mp4": (.30, .42), "c5_dawn.mp4": (.45, .58)}  # crop-window centre sweep, fraction of clip width
# (file, fraction of the vocal span where the matching lyric starts)
STORY = [("c1_diya.mp4", 0.0), ("c3_koel.mp4", 0.28), ("c2_river.mp4", 0.36), ("c4_rain.mp4", 0.56), ("c5_dawn.mp4", 0.84)]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-2000:]); sys.exit(1)


def dur(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                capture_output=True, text=True).stdout)


def starts_16x9(slug, total):
    """Use caption timing when it exists (Maithili: exact line positions), else proportional."""
    p = f"{ROOT}/songs/{slug}/caption_timing.json"
    if slug == "song-001" and os.path.exists(p):
        t = json.load(open(p))
        idx = {"c1_diya.mp4": None, "c3_koel.mp4": 14, "c2_river.mp4": 18, "c4_rain.mp4": 28, "c5_dawn.mp4": 42}
        out = []
        for f, _ in STORY:
            out.append((f, 0.0 if idx[f] is None else t[idx[f]][0]))
        return out
    on, off = 15.0, total - 12.0
    return [(f, 0.0 if fr == 0 else on + (off - on) * fr) for f, fr in STORY]


def boom(i):
    return f"split[f{i}][r{i}];[r{i}]reverse[rv{i}];[f{i}][rv{i}]concat=n=2:v=1,setpts=PTS*1.25"


def build(slug, mode):
    D = f"{ROOT}/songs/{slug}"
    base = f"{D}/anim_{mode}.mp4"
    total = dur(base)
    W, H = (1920, 1080) if mode == "16x9" else (1080, 1920)
    if mode == "16x9":
        plan = starts_16x9(slug, total)
    else:   # reel: moon opener, river, dawn finish
        plan = [("c1_diya.mp4", 0.0), ("c3_koel.mp4", 11.0), ("c2_river.mp4", 22.0), ("c4_rain.mp4", 33.0), ("c5_dawn.mp4", 44.0)]
    inputs = ["-i", base]
    fc, last = [], "[0:v]"
    for i, (f, t0) in enumerate(plan, start=1):
        L = 20 if mode == "16x9" else 12
        t0 = round(min(t0, total - L - 1.0), 2)
        inputs += ["-i", f"{CLIPS}/{f}"]
        if mode == "16x9":
            v = (f"[{i}:v]fps={FPS},{boom(i)},scale={W}:{H}:flags=lanczos,unsharp=5:5:0.6,noise=alls=3:allf=t,setsar=1,format=yuva420p,"
                 f"fade=t=in:st=0:d={XF}:alpha=1,fade=t=out:st={L - XF}:d={XF}:alpha=1,setpts=PTS-STARTPTS+{t0}/TB[c{i}]")
        else:   # punch-in: half-width window of the clip, panned, over a blurred fill
            a, b = PAN[f]
            v = (f"[{i}:v]fps={FPS},{boom(i)},split[a{i}][b{i}];"
                 f"[a{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:6,eq=brightness=-0.08[bg{i}];"
                 f"[b{i}]crop=640:720:'(iw-640)*({a}+({b}-{a})*t/{L})':0,scale={W}:-2:flags=lanczos,unsharp=5:5:0.6[fg{i}];"
                 f"[bg{i}][fg{i}]overlay=0:(H-h)/2,setsar=1,format=yuva420p,"
                 f"fade=t=in:st=0:d={XF}:alpha=1,fade=t=out:st={L - XF}:d={XF}:alpha=1,setpts=PTS-STARTPTS+{t0}/TB[c{i}]")
        fc.append(v)
        fc.append(f"{last}[c{i}]overlay=0:0:eof_action=pass:enable='between(t,{t0},{t0 + L + .05})'[m{i}]")
        last = f"[m{i}]"
    out = f"{D}/final_{mode}.mp4"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc), "-map", last, "-map", "0:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "copy",
         "-movflags", "+faststart", out])
    print("wrote", out, [(f, round(t, 1)) for f, t in plan], flush=True)
    return out


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "16x9")
