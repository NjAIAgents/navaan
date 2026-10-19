#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: the owner's own scene video as the background of an inspiration short, instead of a generated picture: shrink the upload to a working copy, then fit it to the length of the short.

  inspire_scene.py <slug>          the pipeline step: shrink .cache/raw.<ext> (from the upload route) to scene_src.mp4 (no sound: the Suno audio is the sound), check it, delete the big original
  fit(D, total)                    called by inspire_prep once the length of the short is known: write scene_bg.mp4, 1080x1920 at 30 fps, exactly `total` seconds, and return what it did

How a scene is fitted to `total` (the audio plus the end card, so the credit page always ends the short):
  longer than the short      cut at the end of the short
  shorter, small gap         played at normal speed, then its last frame is held to the end
  shorter, big gap           slowed down (at most `max_slow` times), then its last frame is held for what remains
A gap is small up to `small_gap` seconds. Config (navaan.config.json): inspiration.scene.small_gap (3.0), inspiration.scene.max_slow (1.5); the working copy uses reel.proxy.* and reel.keep_original like a reel's footage.
"""
import os, sys, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
import reel_ingest as I
LOG = L.get("inspire_scene")

SRC, BG, INFO = "scene_src.mp4", "scene_bg.mp4", "scene.json"
W, H, FPS = 1080, 1920, 30


def plan(src_seconds, total, small_gap=None, max_slow=None):
    """How the scene meets the length of the short: {"stretch": slow-down factor (1 = normal), "play": seconds the scene is on screen, "hold": seconds its last frame is held, "cut": True when it is cut short}."""
    small = float(C.cfg("inspiration.scene.small_gap", 3.0) if small_gap is None else small_gap)
    slow = float(C.cfg("inspiration.scene.max_slow", 1.5) if max_slow is None else max_slow)
    if src_seconds >= total - 0.05:
        return {"stretch": 1.0, "play": round(total, 2), "hold": 0.0, "cut": src_seconds > total + 0.05}
    stretch = 1.0 if total - src_seconds <= small else min(slow, total / src_seconds)   # big gap: slow down just enough, never more than max_slow
    play = src_seconds * stretch
    return {"stretch": round(stretch, 4), "play": round(play, 2), "hold": round(max(0.0, total - play), 2), "cut": False}


def fit(D, total):
    """Write D/scene_bg.mp4 from scene_src.mp4 so it lasts exactly `total` seconds, framed to 9:16. Returns the plan with the source length."""
    import subprocess
    src = os.path.join(D, SRC)
    if not os.path.exists(src): raise FileNotFoundError(src)
    secs = I.probe(src)["duration"]; p = plan(secs, total)
    vf = [f"crop=w='trunc(min(iw,ih*9/16)/2)*2':h='trunc(min(ih,iw*16/9)/2)*2'", f"scale={W}:{H}:flags=lanczos", "setsar=1"]
    if p["stretch"] > 1.0: vf.append(f"setpts={p['stretch']:.4f}*PTS")
    vf.append(f"fps={FPS}")
    if p["hold"] > 0.01: vf.append(f"tpad=stop_mode=clone:stop_duration={p['hold']:.3f}")
    vf.append("format=yuv420p")
    out = os.path.join(D, BG); part = out + ".part.mp4"
    cmd = [C.tool("ffmpeg"), "-y", "-v", "error", "-i", src, "-an", "-vf", ",".join(vf), "-t", f"{total:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-g", str(FPS), "-pix_fmt", "yuv420p", "-movflags", "+faststart", part]
    subprocess.run(cmd, check=True); os.replace(part, out)
    info = {"src_seconds": round(secs, 2), "total": round(total, 2), **p}
    json.dump(info, open(os.path.join(D, INFO), "w"), indent=2)
    return info


def ingest(D):
    """The pipeline step: the uploaded video becomes scene_src.mp4. Nothing to do when the copy exists and no new upload is waiting."""
    raw = I.find_raw(D); src = os.path.join(D, SRC)
    if not raw:
        if os.path.exists(src): return
        sys.exit("navaan: no scene video yet. Upload one first (.cache/raw.<ext> or scene_src.mp4 in the item folder).")
    if os.path.splitext(raw)[1].lower() not in I.VIDEO_EXT: sys.exit(f"navaan: {os.path.basename(raw)} is not a video type ({', '.join(I.VIDEO_EXT)})")
    rp = I.probe(raw)
    if not rp.get("has_video"): sys.exit("navaan: the upload has no video stream")
    if rp["duration"] < 1: sys.exit("navaan: the scene video is shorter than one second")
    part = src + ".part.mp4"
    print(f"shrinking {os.path.basename(raw)} ({rp['width']}x{rp['height']}, {rp['duration']:.1f} s, {rp['bytes'] // 1048576} MB) ...", flush=True)
    import subprocess
    try:
        # the working copy has no sound: the Suno audio is the sound of the short
        cmd = I.proxy_cmd(raw, part, {**rp, "has_audio": False}, int(C.cfg("reel.proxy.max_long_side", 2560)), int(C.cfg("reel.proxy.crf", 24)), str(C.cfg("reel.proxy.preset", "veryfast")))
        C.run_ffmpeg(cmd, rp["duration"], "Shrinking the scene video", 0, 100)
        pp = I.check_proxy(rp, part)
    except (subprocess.CalledProcessError, RuntimeError) as e:
        if os.path.exists(part): os.remove(part)
        sys.exit(f"navaan: could not make the working copy ({e}). The original is kept: {raw}")
    os.replace(part, src)
    for stale in (BG, "timing.json"):   # made from the old scene: the typography step makes them again
        p = os.path.join(D, stale)
        if os.path.exists(p): os.remove(p)
    deleted = False
    if not C.cfg("reel.keep_original", False): os.remove(raw); deleted = True   # only after the copy was checked above
    json.dump({"src_seconds": pp["duration"], "width": pp["width"], "height": pp["height"], "source_bytes": rp["bytes"], "bytes": pp["bytes"], "raw_deleted": deleted}, open(os.path.join(D, "scene_upload.json"), "w"), indent=2)
    print(f"scene video ready: {pp['bytes'] // 1048576} MB (was {rp['bytes'] // 1048576} MB); original {'deleted' if deleted else 'kept'}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    ingest(C.song_dir(sys.argv[1]))
