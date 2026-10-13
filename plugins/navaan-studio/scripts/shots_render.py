#!/usr/bin/env python3
"""shots_render.py <slug>

Local render of a music video from the user's own pictures. No Flow, no credits.
  layout static  one cover picture held for the whole song (ffmpeg)
  layout video   the approved shots.json: each shot a picture with a slow camera move, cross faded (Remotion, Shots composition)
Audio is songs/<slug>/final.mp3. Writes final_16x9.mp4 (1920x1080, 24 fps) plus the covers the later steps use:
cover_16x9.png, cover_1x1.png, thumb_16x9.jpg (the YouTube thumbnail). Existing covers the user made are kept."""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import inspire_render as R
import visuals_cfg as V

W, H, FPS = 1920, 1080, 24
OUT = "final_16x9.mp4"


def prep_images(D, rels):
    """Shrink pictures to at most 2560 px wide copies inside the song folder (Remotion reads from there), keep the originals."""
    cd = os.path.join(D, ".cache", "shots"); os.makedirs(cd, exist_ok=True); out = {}
    for rel in rels:
        dst = os.path.join(cd, os.path.splitext(os.path.basename(rel))[0] + ".jpg")
        if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(os.path.join(D, rel)):
            C.run([C.tool("ffmpeg"), "-y", "-v", "error", "-i", os.path.join(D, rel), "-vf", "scale='min(2560,iw)':-2", "-q:v", "2", dst])
        out[rel] = os.path.relpath(dst, D)
    return out


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
           "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=yuv420p", "-c:v", "libx264", "-tune", "stillimage", "-crf", "20",
           "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out])


def render_video(D, mp3, sj, out):
    shots = sj["shots"]
    if not shots: sys.exit("navaan: shots.json has no shots")
    imgs = prep_images(D, sorted({s["image"] for s in shots}))
    dur = round(C.duration(mp3), 2)
    ps = []
    for s in sorted(shots, key=lambda s: float(s["start"])):
        ps.append({"start": float(s["start"]), "end": float(s["end"]), "image": imgs[s["image"]], "camera": s.get("camera", "hold"), "focus": s.get("focus") or [0.5, 0.5]})
    ps[0]["start"] = 0.0; ps[-1]["end"] = dur
    for i in range(len(ps) - 1): ps[i]["end"] = ps[i + 1]["start"]  # no gaps, no overlap in the plan; the composition adds the cross fade
    props = {"width": W, "height": H, "fps": FPS, "duration": dur, "audio": os.path.relpath(mp3, D), "shots": ps, "fade": 1.2, "grade": {"dim": 0.08, "vignette": 0.35}, "fadeOut": 2}
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


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1])
