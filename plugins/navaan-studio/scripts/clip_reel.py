#!/usr/bin/env python3
"""clip_reel.py <slug>  cut a vertical reel (and a cover image) from the best part of a finished song.

Reads songs/<slug>/reel_clip.json:
  {"start": 184.5, "end": 210.4, "hook": "line shown on the cover", "title": "optional, default title.txt",
   "bg": "final_16x9.mp4", "crop_x": [560, 760]}
  start, end   seconds in the full song. The lyric lines come from caption_cues.json between them.
  bg           the full video the pictures are taken from (default final_16x9.mp4, the one without captions).
  bg_image     a still picture in the song folder to use instead of the video (it gets the same slow push-in and grading).
  crop_x       left edge of the 9:16 window cut out of the 16:9 picture, at the start and the end (a slow drift). Default centred.
Writes final_reel_9x16.mp4 (1080x1920, 30 fps), thumb_9x16.jpg (the Reel cover) and reel_clip_report.json.
The Instagram step picks final_reel_9x16.mp4 first. No generation credits are used.
"""
import os, sys, json, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import inspire_render as R

OUT, THUMB = "final_reel_9x16.mp4", "thumb_9x16.jpg"
END_GAP, END_CARD = 0.5, 3.0


def main(slug):
    D = C.song_dir(slug)
    cfgp = os.path.join(D, "reel_clip.json")
    if not os.path.exists(cfgp): sys.exit(f"navaan: {cfgp} missing. See --help in the script header.")
    cc = C.load_json(cfgp)
    t0, t1 = float(cc["start"]), float(cc["end"])
    ff = C.tool("ffmpeg")
    bg = os.path.join(D, cc.get("bg", "final_16x9.mp4"))
    audio_src = next((os.path.join(D, n) for n in ("final.mp3", "final_tagged.mp3") if os.path.exists(os.path.join(D, n))), None)
    bg_image = cc.get("bg_image")
    if bg_image and not os.path.exists(os.path.join(D, bg_image)): sys.exit(f"navaan: bg_image {bg_image} is not in the song folder")
    if (not bg_image and not os.path.exists(bg)) or not audio_src: sys.exit("navaan: need the full video (or a bg_image) and final.mp3 in the song folder")
    cues = [c for c in C.load_json(os.path.join(D, "caption_cues.json")) if t0 - 0.3 <= c[0] < t1]
    if not cues: sys.exit("navaan: no lyric lines between start and end in caption_cues.json")
    rel = [{"text": c[2], "start": round(max(0.0, c[0] - t0), 2), "end": round(c[1] - t0, 2)} for c in cues]
    rel[0]["start"] = max(rel[0]["start"], 0.5)  # let the picture arrive before the first line
    body = rel[-1]["end"]
    handle_s = round(body + END_GAP, 2)
    dur = round(handle_s + END_CARD, 2)
    # director: split the clip into acts by language, so the picture and type can change at the turns
    def _lang(tx):
        return "hi" if any("\u0900" <= ch <= "\u097f" for ch in tx) else "en"
    runs = []
    for c in rel:
        l = _lang(c["text"])
        if runs and runs[-1]["lang"] == l: runs[-1]["to"] = c["end"]
        else: runs.append({"lang": l, "from": c["start"], "to": c["end"]})
    acts = []
    for i, r in enumerate(runs):
        kind = "confess" if r["lang"] == "en" else ("ache" if not any(a["kind"] == "ache" for a in acts) and not any(a["kind"] == "confess" for a in acts) else "hope")
        acts.append({"kind": kind, "from": 0.0 if i == 0 else round((runs[i - 1]["to"] + r["from"]) / 2, 2), "to": r["to"]})
    for i in range(len(acts) - 1): acts[i]["to"] = acts[i + 1]["from"]
    acts[-1]["to"] = round(handle_s + END_CARD, 2)
    title = cc.get("title") or (open(os.path.join(D, "title.txt"), encoding="utf-8").read().strip() if os.path.exists(os.path.join(D, "title.txt")) else slug)
    handle = (C.cfg("publish.instagram_handle", "") or "").lstrip("@") or "NAVAAN"
    x0, x1 = (cc.get("crop_x") or [656, 656])
    # 1) picture: a 9:16 window from the 16:9 frame, drifting slowly, 30 fps, no sound
    bgp = os.path.join(D, "reel_bg.mp4")
    vf = f"crop=608:1080:x='{x0}+({x1}-{x0})*t/{dur}':y=0,scale=1080:1920:flags=lanczos,fps=30,setsar=1,format=yuv420p"
    if not bg_image: C.run([ff, "-y", "-v", "error", "-ss", f"{t0:.2f}", "-t", f"{dur:.2f}", "-i", bg, "-an", "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "16", bgp])
    # 2) sound: the part of the song, faded in, and out soon after the last lyric line so the next section does not leak in
    ap = os.path.join(D, "reel_audio.mp3")
    a_len = body + 1.1
    af = f"afade=t=in:st=0:d=0.4,afade=t=out:st={max(0.0, a_len - 1.6):.2f}:d=1.6,loudnorm=I=-15:TP=-1.5:LRA=9,apad=whole_dur={dur:.2f}"
    C.run([ff, "-y", "-v", "error", "-ss", f"{t0:.2f}", "-t", f"{a_len:.2f}", "-i", audio_src, "-af", af, "-t", f"{dur:.2f}", "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", ap])
    # 3) cover picture: a calm frame from the picture
    cb = os.path.join(D, "reel_cover_bg.jpg")
    if not bg_image: C.run([ff, "-y", "-v", "error", "-ss", "3", "-i", bgp, "-frames:v", "1", "-q:v", "2", cb])
    props = {"width": 1080, "height": 1920, "fps": 30, "duration": dur, "bg": bg_image or "reel_bg.mp4", "bg_is_image": bool(bg_image), "audio": "reel_audio.mp3", "cues": rel, "title": title,
             "hook": cc.get("hook") or rel[0]["text"], "handle": {"text": handle, "icon": "instagram", "start": handle_s},
             "style": {"color": "#FFFFFF", "accent": "#FF4D7E", "dim": 0.42}, "mode": "reel", "acts": acts}
    pp = os.path.join(D, "reel_props.json"); json.dump(props, open(pp, "w"), indent=2, ensure_ascii=False)
    cp = dict(props, bg=bg_image or "reel_cover_bg.jpg", bg_is_image=True, audio=None, mode="cover"); cpp = os.path.join(D, "reel_cover_props.json"); json.dump(cp, open(cpp, "w"), indent=2, ensure_ascii=False)
    rd = R.remotion_dir()
    if not R.remotion_ready(): sys.exit("navaan: Remotion is not installed. Run npm ci in the plugin's remotion folder.")
    env = dict(os.environ); env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")
    base = ["npx", "--no-install", "remotion"]
    extra = ["--log=error", "--overwrite", f"--public-dir={D}"]
    chrome = os.environ.get("NAVAAN_CHROME") or next((c for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium") if os.path.exists(c)), "")
    if chrome: extra += [f"--browser-executable={chrome}", "--chrome-mode=chrome-for-testing"]
    out = os.path.join(D, OUT)
    print(f"rendering {dur:.1f}s reel ({len(rel)} lines) ...", flush=True)
    subprocess.run(base + ["render", "src/index.ts", "Lyrics", out, f"--props={pp}", "--codec=h264", "--crf=18", "--pixel-format=yuv420p"] + extra, cwd=rd, check=True, env=env)
    thumb = os.path.join(D, THUMB)
    png = os.path.join(D, "reel_cover.png")
    subprocess.run(base + ["still", "src/index.ts", "LyricsCover", png, f"--props={cpp}"] + extra, cwd=rd, check=True, env=env)
    C.run([ff, "-y", "-v", "error", "-i", png, "-q:v", "2", thumb]); os.remove(png)
    info = R.probe(out)
    errs, warns = R.validate(info, {"duration": dur}, max_s=90)
    json.dump({"engine": "remotion", "checks": "failed" if errs else "passed", "errors": errs, "warnings": warns, "start": t0, "end": t1, **info}, open(os.path.join(D, "reel_clip_report.json"), "w"), indent=2)
    if errs: sys.exit("navaan: " + "; ".join(errs))
    print(f"done: {OUT} {dur:.1f}s, {THUMB}")


if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
