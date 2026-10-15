#!/usr/bin/env python3
"""clipvideo.py <slug> [16x9|reel]

Build a video only from the song's Flow clips (songs/<slug>/clips/*.mp4), cross faded.
Loop mode (default): each clip is boomeranged (forward then backward) so one short clip can fill its time.
Story mode (story.json has "story": true): clips play forward only, like shots in a music video, one after another by lyric timing.
Audio comes from songs/<slug>/final.mp3.
  16x9 -> songs/<slug>/final_16x9.mp4   (whole song)
  reel -> songs/<slug>/final_reel_sync.mp4   (9:16, audio window from reel_start.json {"start": s, "dur": d}, default 30 and 60)

Optional songs/<slug>/story.json: {"story": true, "scenes": [{"clip": "c01_door.mp4", "at": 0.0, "pan": [0.3, 0.5], "loop": false}, ...]}
  at = fraction of the song where the scene starts, pan = horizontal crop sweep for the reel, loop = boomerang this clip (default true, false in story mode).
  A clip may appear in several scenes (a chorus shot reused in a later chorus). In story mode the reel keeps the same shots that fall inside its audio window.
Without story.json, clips are used in name order, evenly spaced.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import tool, song_dir, duration, run, load_json

XF, FPS = 1.5, 24


def boom(D, mode, f, pan, cache, loop=True):
    W, H = (1920, 1080) if mode == "16x9" else (1080, 1920)
    out = f"{cache}/{'boom' if loop else 'fwd'}_{mode}_{f}"
    if os.path.exists(out):
        return out
    pre = "split[f][r];[r]reverse[rv];[f][rv]concat=n=2:v=1,setpts=PTS*1.25" if loop else "setpts=PTS"
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
    """Returns (clip, at, pan, loop, story). at is a fraction of the song."""
    sj = load_json(f"{D}/story.json", default={})
    story, items = bool(sj.get("story")), sj.get("scenes")
    if items:
        return [(x["clip"], float(x.get("at", i / len(items))), tuple(x.get("pan", (0.3, 0.5))), bool(x.get("loop", not story)), story) for i, x in enumerate(items)]
    clips = sorted(f for f in os.listdir(f"{D}/clips") if f.lower().endswith(".mp4"))
    if not clips:
        sys.exit(f"navaan: no clips in {D}/clips")
    return [(c, i / len(clips), (0.3, 0.5), True, False) for i, c in enumerate(clips)]


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
    story = sc[0][4]
    if mode == "reel" and story:
        # keep the shots that fall inside the audio window, cut at the window edges (skip = how far into the clip the window starts)
        starts = [fr * song for _, fr, *_ in sc] + [song]
        spans = []
        for i, (f, _, p, lp, _) in enumerate(sc):
            lo, hi = max(starts[i], a0), min(starts[i + 1], a0 + total)
            if hi - lo > 0.4:
                spans.append((f, lo - a0, hi - a0, p, lp, max(0.0, a0 - starts[i])))
    elif mode == "reel":
        spans = [(f, k * total / len(sc), (k + 1) * total / len(sc), p, lp, 0.0) for k, (f, _, p, lp, _) in enumerate(sc)]
    else:
        spans = [(f, fr * total, (sc[i + 1][1] if i + 1 < len(sc) else 1.0) * total, p, lp, 0.0) for i, (f, fr, p, lp, _) in enumerate(sc)]
    if not spans:
        sys.exit("navaan: no scene falls inside the audio window")
    cache = f"{D}/.cache"; os.makedirs(cache, exist_ok=True)
    inputs, fc, last = [], [], None
    for i, (f, a, b, p, lp, skip) in enumerate(spans):
        L = (b - a) + (XF if i + 1 < len(spans) else 0)
        src = boom(D, mode, f, p, cache, lp)
        if not lp and duration(src) < (b - a) + skip - 0.3:
            print(f"warning: {f} is {duration(src):.1f}s but its shot needs {(b - a) + skip:.1f}s, so it repeats. Plan shots no longer than the clip.", flush=True)
        inputs += ["-stream_loop", "-1", *(["-ss", f"{skip:.2f}"] if skip else []), "-t", f"{L:.2f}", "-i", src]
        if i == 0:
            last = "[0:v]"
        else:
            fc.append(f"{last}[{i}:v]xfade=transition=fade:duration={XF}:offset={round(a, 2)}[x{i}]")
            last = f"[x{i}]"
    n = len(spans)
    inputs += ["-ss", f"{a0:.2f}", "-t", f"{total:.2f}", "-i", mp3]
    import watermark   # the channel mark
    wm = watermark.drawtext_vf(D, vertical=(mode == "reel"))
    fc.append(f"{last}vignette=PI/5,eq=saturation=1.05,noise=alls=2:allf=t{(","+wm) if wm else ""},fade=t=in:st=0:d=2,fade=t=out:st={total-3:.2f}:d=3[v]")
    fc.append(f"[{n}:a]afade=t=in:st=0:d=0.4,afade=t=out:st={max(total-2.5,0):.2f}:d=2.5[a]")
    out = os.environ.get("NAVAAN_OUT") or (f"{D}/final_16x9.mp4" if mode == "16x9" else f"{D}/final_reel_sync.mp4")
    run([tool("ffmpeg"), "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
         "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    print("wrote", out, [(f, round(a), round(b)) for f, a, b, *_ in spans], flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2 or (len(sys.argv) > 2 and sys.argv[2] not in ("16x9", "reel")):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "16x9")
