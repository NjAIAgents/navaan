#!/usr/bin/env python3
"""shots_render.py <slug> [--reel]

--reel renders the vertical 9:16 reel (final_reel_9x16.mp4, 30 s or more) for the YouTube Short and the Instagram Reel. It starts at the hook of the song (reel_hook.py writes reel_start.json),
shows each 16:9 picture whole over a blurred copy of itself, and both videos carry a small channel mark (watermark.py).

Local render of a music video from the user's own pictures. No Flow, no credits.
  layout static  one cover picture held for the whole song (ffmpeg)
  layout video   the approved shots.json: each shot a picture with a slow camera move, cross faded (Remotion, Shots composition)
Audio is songs/<slug>/final.mp3. Writes final_16x9.mp4 (1920x1080, 24 fps) plus the covers the later steps use:
cover_16x9.png, cover_1x1.png, thumb_16x9.jpg (the YouTube thumbnail). Existing covers the user made are kept."""
import os, sys, json, re, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import inspire_render as R
import visuals_cfg as V
import motion_clips
import watermark

W, H, FPS = 1920, 1080, 24
OUT = "final_16x9.mp4"
RW, RH = 1080, 1920
REEL_OUT, REEL_AUDIO, REEL_THUMB = "final_reel_9x16.mp4", "reel_audio.mp3", "thumb_9x16.jpg"
REEL_MAX, REEL_DEFAULT = 58.0, 45.0


def prep_images(D, rels, sub="shots"):
    """Shrink pictures to at most 2560 px wide copies inside the song folder (Remotion reads from there), keep the originals."""
    cd = os.path.join(D, ".cache", sub); os.makedirs(cd, exist_ok=True); out = {}
    for rel in rels:
        dst = os.path.join(cd, os.path.splitext(os.path.basename(rel))[0] + ".jpg")
        if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(os.path.join(D, rel)):
            C.run([C.tool("ffmpeg"), "-y", "-v", "error", "-i", os.path.join(D, rel), "-vf", "scale='min(2560,iw)':-2", "-q:v", "2", dst])
        out[rel] = os.path.relpath(dst, D)
    return out


def vert_rel(D, rel):
    """images/vert/pic_NN.png when a native 9:16 picture was made for images/pic_NN.png (song_images_openai.py --vertical), else None."""
    r = os.path.join("images", "vert", os.path.basename(rel))
    return r if os.path.exists(os.path.join(D, r)) else None


def loop_rel(D, rel):
    """The moving loop of a picture when motion_clips made one, else None (the still is used)."""
    lp = motion_clips.loop_path(D, rel)
    return os.path.relpath(lp, D) if os.path.exists(lp) else None


def covers(D, first):
    ff = C.tool("ffmpeg"); src = os.path.join(D, first)
    def one(name, vf, extra=()):
        p = os.path.join(D, name)
        if not os.path.exists(p): C.run([ff, "-y", "-v", "error", "-i", src, "-vf", vf, "-frames:v", "1", *extra, p])
    one("cover_16x9.png", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}")
    one("cover_1x1.png", "scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080")
    one("thumb_16x9.jpg", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720", ("-q:v", "2"))


def render_static(D, mp3, img, out):
    C.run([C.tool("ffmpeg"), "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", os.path.join(D, img), "-i", mp3,
           "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}" + (("," + watermark.drawtext_vf(D)) if watermark.drawtext_vf(D) else "") + ",format=yuv420p", "-c:v", "libx264", "-tune", "stillimage", "-crf", "20",
           "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out])


def render_video(D, mp3, sj, out):
    shots = sj["shots"]
    if not shots: sys.exit("navaan: shots.json has no shots")
    imgs = prep_images(D, sorted({s["image"] for s in shots}))
    dur = round(C.duration(mp3), 2)
    ps = []
    for s in sorted(shots, key=lambda s: float(s["start"])):
        ps.append({"start": float(s["start"]), "end": float(s["end"]), "image": imgs[s["image"]], "loop": loop_rel(D, s["image"]), "camera": s.get("camera", "hold"), "focus": s.get("focus") or [0.5, 0.5]})
    ps[0]["start"] = 0.0; ps[-1]["end"] = dur
    for i in range(len(ps) - 1): ps[i]["end"] = ps[i + 1]["start"]  # no gaps, no overlap in the plan; the composition adds the cross fade
    props = {"width": W, "height": H, "fps": FPS, "duration": dur, "audio": os.path.relpath(mp3, D), "shots": ps, "loopSeconds": motion_clips.LOOP_SECONDS, "fade": 1.2, "grade": {"dim": 0.08, "vignette": 0.35}, "fadeOut": 2, "watermark": watermark.text(D)}
    pp = os.path.join(D, "shots_props.json"); json.dump(props, open(pp, "w", encoding="utf-8"), indent=2)
    rd = R.remotion_dir()
    if not R.remotion_ready(): sys.exit(f"navaan: remotion is not installed. Run: cd {rd} && npm install")
    cmd = ["npx", "--no-install", "remotion", "render", "src/index.ts", "Shots", out, f"--props={pp}", f"--public-dir={D}",
           "--codec=h264", "--crf=18", "--pixel-format=yuv420p", "--log=error", "--overwrite", "--concurrency=4"]
    chrome = os.environ.get("NAVAAN_CHROME") or next((c for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium") if os.path.exists(c)), "")
    if chrome: cmd += [f"--browser-executable={chrome}", "--chrome-mode=chrome-for-testing"]
    env = dict(os.environ); env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")
    print(f"rendering {dur}s with {len(ps)} shots (this takes a few minutes) ...", flush=True)
    subprocess.run(cmd, cwd=rd, check=True, env=env)


def main(slug):
    D = C.song_dir(slug); v = V.load(D)
    if v.get("mode") != "own": sys.exit("navaan: this song uses Flow visuals, not its own pictures")
    pr = V.problems(D, v)
    if pr: sys.exit("navaan: " + pr[0])
    mp3 = next((os.path.join(D, n) for n in ("final.mp3", "final_tagged.mp3") if os.path.exists(os.path.join(D, n))), None)
    if not mp3: sys.exit("navaan: final.mp3 is missing")
    out = os.path.join(D, OUT); part = os.path.join(D, "final_16x9.part.mp4")
    if os.path.exists(part): os.remove(part)
    imgs = V.own_images(D)
    if v.get("layout") == "static":
        render_static(D, mp3, v.get("cover") or imgs[0], part); first = v.get("cover") or imgs[0]
    else:
        sj = C.load_json(os.path.join(D, "shots.json"))
        if not sj: sys.exit("navaan: shots.json is missing. Run the director step first.")
        render_video(D, mp3, sj, part); first = sorted(sj["shots"], key=lambda s: float(s["start"]))[0]["image"]
    info = R.probe(part)
    errs = []
    if (info["width"], info["height"]) != (W, H): errs.append(f"size is {info['width']}x{info['height']}, need {W}x{H}")
    if info["codec"] != "h264": errs.append(f"codec is {info['codec']}")
    if not info["has_audio"]: errs.append("no audio track")
    if abs(info["duration"] - C.duration(mp3)) > 1.0: errs.append(f"length {info['duration']}s differs from the song {C.duration(mp3):.1f}s")
    if errs:
        os.remove(part); sys.exit("navaan: render failed checks: " + "; ".join(errs))
    os.replace(part, out)
    covers(D, first)
    json.dump({"layout": v.get("layout"), "checks": "passed", **info}, open(os.path.join(D, "render_report.json"), "w"), indent=2)
    print(f"done: {OUT} {info['width']}x{info['height']} {info['duration']}s {info['bytes'] // 1024} KB")


# ---------------------------------------------------------------- vertical reel (YouTube Short and Instagram Reel)

def snap_to_pause(mp3, t, span=4.0):
    """Move t to the nearest end of a quiet moment within span seconds, so the reel does not start mid word. Returns t when nothing is found."""
    off = max(0.0, t - span)
    r = subprocess.run([C.tool("ffmpeg"), "-v", "info", "-ss", f"{off:.2f}", "-t", f"{2 * span:.2f}", "-i", mp3, "-af", "silencedetect=noise=-32dB:d=0.2", "-f", "null", "-"],
                       capture_output=True, text=True)
    ends = [off + float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr or "")]
    return min(ends, key=lambda e: abs(e - t)) if ends else t


def pick_window(D, mp3):
    """(start, dur) of the reel in the song. reel_start.json {"start": s, "dur": d} wins; otherwise the first chorus (timing estimated from the line counts), snapped to a pause."""
    total = C.duration(mp3)
    want = min(REEL_MAX, float(C.cfg("video.reel_seconds", REEL_DEFAULT) or REEL_DEFAULT))
    rs = C.load_json(os.path.join(D, "reel_start.json"), default=None)
    if isinstance(rs, dict) and rs.get("start") is not None:
        start = max(0.0, float(rs["start"])); dur = min(REEL_MAX, float(rs.get("dur") or want))
    else:
        import shots_prep
        start = None
        try:
            for sec in shots_prep.build_context(D)["sections"]:
                if re.search(r"chorus|hook|refrain", sec["label"], re.I) and not re.search(r"pre", sec["label"], re.I):
                    start = float(sec["start"]); break
        except SystemExit:
            pass
        if start is None: start = total * 0.3
        start = snap_to_pause(mp3, start); dur = want
    dur = min(dur, max(5.0, total - start))
    if start + dur > total: start = max(0.0, total - dur)
    return round(start, 2), round(dur, 2)


def reel_plan(shots, start, dur, fallback_image):
    """The shots of the full video that fall inside the reel window, moved so the reel starts at 0 and covers 0..dur without gaps."""
    out = []
    for sh in sorted(shots, key=lambda x: float(x["start"])):
        a, b = max(float(sh["start"]), start) - start, min(float(sh["end"]), start + dur) - start
        if b - a < 0.5: continue
        out.append({"start": a, "end": b, "image": sh["image"], "camera": sh.get("camera", "hold"), "focus": sh.get("focus") or [0.5, 0.5]})
    if not out: out = [{"start": 0.0, "end": dur, "image": fallback_image, "camera": "push_in", "focus": [0.5, 0.5]}]
    out[0]["start"] = 0.0; out[-1]["end"] = dur
    for i in range(len(out) - 1): out[i]["end"] = out[i + 1]["start"]
    return out


def render_reel(slug):
    D = C.song_dir(slug); v = V.load(D)
    if v.get("mode") != "own": sys.exit("navaan: this song uses Flow visuals, not its own pictures")
    pr = V.problems(D, v)
    if pr: sys.exit("navaan: " + pr[0])
    mp3 = next((os.path.join(D, n) for n in ("final.mp3", "final_tagged.mp3") if os.path.exists(os.path.join(D, n))), None)
    if not mp3: sys.exit("navaan: final.mp3 is missing")
    start, dur = pick_window(D, mp3)
    imgs = V.own_images(D)
    if v.get("layout") == "static": shots, first = [], (v.get("cover") or imgs[0])
    else:
        sj = C.load_json(os.path.join(D, "shots.json"))
        if not sj: sys.exit("navaan: shots.json is missing. Run the director step first.")
        shots = sj["shots"]; first = sorted(shots, key=lambda x: float(x["start"]))[0]["image"]
    ap = os.path.join(D, REEL_AUDIO)
    C.run([C.tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{start}", "-t", f"{dur}", "-i", mp3, "-af", f"afade=t=in:d=0.4,afade=t=out:st={max(0, dur - 1.5):.2f}:d=1.5", "-q:a", "2", ap])
    cache = prep_images(D, sorted({sh["image"] for sh in shots} | {first}))
    ps = reel_plan(shots, start, dur, first)
    for sh in ps:
        vr = vert_rel(D, sh["image"])
        if vr:   # a native vertical picture: no crop, no moving loop (the loops are 16:9), people sit low so aim the move there
            sh["loop"] = None; sh["focus"] = [0.5, 0.62]; sh["image"] = prep_images(D, [vr], "vert")[vr]
        else:
            sh["loop"] = loop_rel(D, sh["image"]); sh["image"] = cache[sh["image"]]
            sh["fit"] = bool(C.cfg("video.reel_fit", True))   # a 16:9 picture is shown whole over a blurred copy of itself instead of cropped to fill
    props = {"width": RW, "height": RH, "fps": FPS, "duration": dur, "audio": REEL_AUDIO, "shots": ps, "loopSeconds": motion_clips.LOOP_SECONDS, "fade": 1.0, "grade": {"dim": 0.08, "vignette": 0.35}, "fadeOut": 1.5, "watermark": watermark.text(D)}
    pp = os.path.join(D, "reel_props.json"); json.dump(props, open(pp, "w", encoding="utf-8"), indent=2)
    rd = R.remotion_dir()
    if not R.remotion_ready(): sys.exit(f"navaan: remotion is not installed. Run: cd {rd} && npm install")
    part = os.path.join(D, "final_reel.part.mp4"); out = os.path.join(D, REEL_OUT)
    if os.path.exists(part): os.remove(part)
    cmd = ["npx", "--no-install", "remotion", "render", "src/index.ts", "Shots", part, f"--props={pp}", f"--public-dir={D}",
           "--codec=h264", "--crf=18", "--pixel-format=yuv420p", "--log=error", "--overwrite", "--concurrency=4"]
    chrome = os.environ.get("NAVAAN_CHROME") or next((c for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium") if os.path.exists(c)), "")
    if chrome: cmd += [f"--browser-executable={chrome}", "--chrome-mode=chrome-for-testing"]
    env = dict(os.environ); env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")
    print(f"rendering the {dur}s reel starting at {start}s with {len(ps)} shots ...", flush=True)
    subprocess.run(cmd, cwd=rd, check=True, env=env)
    info = R.probe(part); errs = []
    if (info["width"], info["height"]) != (RW, RH): errs.append(f"size is {info['width']}x{info['height']}, need {RW}x{RH}")
    if info["codec"] != "h264": errs.append(f"codec is {info['codec']}")
    if not info["has_audio"]: errs.append("no audio track")
    if info["duration"] > 60.5 or abs(info["duration"] - dur) > 1.0: errs.append(f"length {info['duration']}s, expected {dur}s and at most 60s")
    if errs:
        os.remove(part); sys.exit("navaan: reel failed checks: " + "; ".join(errs))
    os.replace(part, out)
    C.run([C.tool("ffmpeg"), "-y", "-v", "error", "-ss", "1", "-i", out, "-frames:v", "1", "-q:v", "2", os.path.join(D, REEL_THUMB)])
    json.dump({"start": start, "dur": dur, "checks": "passed", **info}, open(os.path.join(D, "reel_report.json"), "w"), indent=2)
    print(f"done: {REEL_OUT} {info['width']}x{info['height']} {info['duration']}s from {start}s of the song. To start elsewhere, write reel_start.json {{\"start\": seconds}} and redo.")


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    render_reel(sys.argv[1]) if "--reel" in sys.argv[2:] else main(sys.argv[1])
