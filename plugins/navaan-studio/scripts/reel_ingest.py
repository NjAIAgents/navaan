#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: first step of a reel: shrink the uploaded footage to a small working copy, check it, throw the big original away, and gather what the director needs (still frames, scene cuts, sound facts).

  reel_ingest.py <slug>

Input: .cache/raw.<ext> (written by the upload route; a leftover raw.part is an interrupted upload and is ignored). If it is gone, an existing source.mp4 is analysed again.
Output: source.mp4 (H.264 CRF 24, at most 30 fps, long side at most reel.proxy.max_long_side, AAC 96k), probe.json, audio.json, frames/ + frames.json (about 8 to 24 stills with their times), scenes_auto.json.
The original is deleted only after the working copy is checked (it plays to its last second and its length matches), and only when reel.keep_original is not true. The sizes before and after go in probe.json.
Config (navaan.config.json): reel.proxy.max_long_side (2560), reel.proxy.crf (24), reel.proxy.preset (veryfast), reel.keep_original (false).
"""
import os, sys, re, json, glob, subprocess, array
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
LOG = L.get("reel_ingest")

VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".3gp", ".mpg", ".mpeg")


def find_raw(D):
    return next(iter(sorted(p for p in glob.glob(os.path.join(D, ".cache", "raw.*")) if not p.endswith(".part"))), None)


def probe(path):
    j = json.loads(subprocess.check_output([C.tool("ffprobe"), "-v", "error", "-show_entries",
                                            "stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate:stream_side_data=rotation:format=duration,size", "-of", "json", path]))
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not v: return {"has_video": False}
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    rot = next((int(sd.get("rotation", 0)) for sd in v.get("side_data_list", []) if "rotation" in sd), 0)
    if abs(rot) in (90, 270): w, h = h, w   # a phone clip stored sideways: ffmpeg turns it upright, so the shape that matters is the swapped one
    def rate(x):
        try:
            n, d = str(x).split("/"); return float(n) / float(d) if float(d) else 0.0
        except ValueError: return 0.0   # expected: "0/0" for a stream with no rate
    fps = rate(v.get("avg_frame_rate")) or rate(v.get("r_frame_rate")) or 30.0
    return {"has_video": True, "width": w, "height": h, "fps": round(fps, 3), "codec": v.get("codec_name"), "has_audio": bool(a), "duration": round(float(j["format"]["duration"]), 3), "bytes": int(j["format"]["size"])}


def proxy_cmd(raw, out, pr, max_long, crf, preset):
    fps = min(30, max(1, round(pr["fps"])))   # a phone's variable rate becomes a steady one, so cuts and sound stay in step
    vf = f"scale=w='if(gt(iw,ih),min(iw,{max_long}),-2)':h='if(gt(iw,ih),-2,min(ih,{max_long}))':flags=lanczos,format=yuv420p"
    cmd = [C.tool("ffmpeg"), "-y", "-v", "error", "-i", raw, "-map", "0:v:0", "-vf", vf, "-r", str(fps), "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
           "-maxrate", "10M", "-bufsize", "20M", "-g", str(fps), "-keyint_min", str(fps), "-movflags", "+faststart"]
    cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "44100"] if pr["has_audio"] else ["-an"]
    return cmd + [out]


def check_proxy(raw_pr, out):
    """The working copy must have video, a length close to the original's, and play to its last second. Returns its probe or raises."""
    pp = probe(out)
    if not pp.get("has_video"): raise RuntimeError("the shrunk copy has no video")
    if abs(pp["duration"] - raw_pr["duration"]) > max(0.5, 0.01 * raw_pr["duration"]):
        raise RuntimeError(f"the shrunk copy is {pp['duration']} s but the original is {raw_pr['duration']} s")
    t = max(0.0, pp["duration"] - 1.0)
    r = subprocess.run([C.tool("ffmpeg"), "-v", "error", "-ss", f"{t:.2f}", "-i", out, "-f", "null", "-"], capture_output=True, text=True)
    if r.returncode or r.stderr.strip(): raise RuntimeError("the shrunk copy does not play to the end: " + (r.stderr.strip()[:200] or "ffmpeg failed"))
    return pp


def scene_cuts(path):
    r = subprocess.run([C.tool("ffmpeg"), "-v", "info", "-i", path, "-an", "-vf", "select='gt(scene,0.3)',showinfo", "-f", "null", "-"], capture_output=True, text=True)
    ts = sorted({round(float(m.group(1)), 2) for m in re.finditer(r"pts_time:([0-9.]+)", r.stderr)})
    return ts[:200]


def stills(path, D, dur):
    """About one still per two seconds (8 to 24), downscaled, each marked with its time so the director can cite it."""
    from PIL import Image, ImageDraw
    n = min(24, max(8, int(dur / 2)))
    fd = os.path.join(D, "frames"); os.makedirs(fd, exist_ok=True)
    for old in glob.glob(os.path.join(fd, "f*.jpg")): os.remove(old)
    out = []
    for i in range(n):
        t = round((i + 0.5) * dur / n, 2); p = os.path.join(fd, f"f{i + 1:02d}.jpg")
        subprocess.run([C.tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=w='if(gt(iw,ih),640,-2)':h='if(gt(iw,ih),-2,640)'", "-q:v", "4", p], check=True)
        im = Image.open(p).convert("RGB"); d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 118, 26), fill=(0, 0, 0)); d.text((6, 6), f"t={t:.1f}s", fill=(255, 255, 255))
        im.save(p, quality=85); out.append({"file": f"frames/f{i + 1:02d}.jpg", "t": t})
        C.progress(88 + int(8 * (i + 1) / n), 100, "Taking still frames")
    return out


def envelope_db(path, secs=120):
    """20 ms frame levels (dB) of the voice band of the first `secs` seconds, in plain Python (no numpy in the main interpreter)."""
    r = subprocess.run([C.tool("ffmpeg"), "-v", "error", "-i", path, "-vn", "-t", str(secs), "-ac", "1", "-ar", "8000", "-af", "highpass=f=100,lowpass=f=3500", "-f", "s16le", "-"], capture_output=True)
    x = array.array("h"); x.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    out = []
    for i in range(0, len(x) - 160, 160):
        s = sum(v * v for v in x[i:i + 160]) / 160.0
        out.append(10 * __import__("math").log10(s + 1.0))
    return out


def speech_guess(env):
    """Speech is bursty: syllables 2 to 8 times a second with loud and quiet frames far apart. Steady wind, traffic or water is not.
    A guess from the shape of the sound, not a transcript: the numbers go to the director too."""
    if len(env) < 100: return {"speech": False, "confidence": "low", "range_db": 0.0, "bursts_per_s": 0.0}
    s = sorted(env); p20, p90 = s[int(len(s) * 0.2)], s[int(len(s) * 0.9)]
    rng = p90 - p20; thr = p20 + 0.5 * rng
    flips = sum(1 for a, b in zip(env, env[1:]) if (a < thr) != (b < thr))
    bursts = flips / 2.0 / (len(env) * 0.02)
    speech = rng >= 14 and 1.0 <= bursts <= 8.0
    conf = "high" if (rng >= 22 and 2.0 <= bursts <= 6.0) or rng < 8 else "medium" if rng >= 14 or rng < 11 else "low"
    return {"speech": bool(speech), "confidence": conf, "range_db": round(rng, 1), "bursts_per_s": round(bursts, 2)}


def audio_facts(path, pr):
    if not pr["has_audio"]: return {"has_audio": False, "has_speech": False, "speech_confidence": "high"}
    r = subprocess.run([C.tool("ffmpeg"), "-v", "info", "-i", path, "-vn", "-af", "volumedetect,silencedetect=noise=-35dB:d=0.5", "-f", "null", "-"], capture_output=True, text=True)
    mean = re.search(r"mean_volume:\s*(-?[0-9.]+) dB", r.stderr); peak = re.search(r"max_volume:\s*(-?[0-9.]+) dB", r.stderr)
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[0-9.]+)", r.stderr)]; ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", r.stderr)]
    silences = [{"start": round(max(0.0, a), 2), "end": round(b, 2)} for a, b in zip(starts, ends)]
    if len(starts) > len(ends): silences.append({"start": round(starts[-1], 2), "end": pr["duration"]})
    g = speech_guess(envelope_db(path))
    return {"has_audio": True, "mean_db": float(mean.group(1)) if mean else None, "peak_db": float(peak.group(1)) if peak else None, "silences": silences,
            "has_speech": g["speech"], "speech_confidence": g["confidence"], "range_db": g["range_db"], "bursts_per_s": g["bursts_per_s"],
            "note": "has_speech is a guess from the shape of the sound (bursts and loudness range), not a transcript"}


def main(slug):
    D = C.song_dir(slug); src = os.path.join(D, "source.mp4"); raw = find_raw(D)
    if raw:
        if os.path.splitext(raw)[1].lower() not in VIDEO_EXT: sys.exit(f"navaan: {os.path.basename(raw)} is not a video type ({', '.join(VIDEO_EXT)})")
        rp = probe(raw)
        if not rp.get("has_video"): sys.exit("navaan: the upload has no video stream")
        if rp["duration"] < 1: sys.exit("navaan: the upload is shorter than one second")
        max_long = int(C.cfg("reel.proxy.max_long_side", 2560)); crf = int(C.cfg("reel.proxy.crf", 24)); preset = str(C.cfg("reel.proxy.preset", "veryfast"))
        part = src + ".part.mp4"
        print(f"shrinking {os.path.basename(raw)} ({rp['width']}x{rp['height']}, {rp['duration']:.1f} s, {rp['bytes'] // 1048576} MB) ...", flush=True)
        try:
            C.run_ffmpeg(proxy_cmd(raw, part, rp, max_long, crf, preset), rp["duration"], "Shrinking the video", 0, 85)
            pp = check_proxy(rp, part)
        except (subprocess.CalledProcessError, RuntimeError) as e:
            if os.path.exists(part): os.remove(part)
            sys.exit(f"navaan: could not make the working copy ({e}). The original is kept: {raw}")
        os.replace(part, src)
        deleted = False
        if not C.cfg("reel.keep_original", False):
            os.remove(raw); deleted = True   # only after the copy was checked above; this is the one irreversible thing the step does
        info = {**pp, "source_bytes": rp["bytes"], "source_width": rp["width"], "source_height": rp["height"], "source_seconds": rp["duration"], "raw_deleted": deleted}
        print(f"working copy {pp['bytes'] // 1048576} MB (was {rp['bytes'] // 1048576} MB); original {'deleted' if deleted else 'kept'}", flush=True)
    elif os.path.exists(src):
        info = {**(C.load_json(os.path.join(D, "probe.json"), default={}) or {}), **probe(src)}
    else:
        sys.exit("navaan: no footage yet. Upload a video first (.cache/raw.<ext> or source.mp4 in the item folder).")
    json.dump(info, open(os.path.join(D, "probe.json"), "w"), indent=2)
    C.progress(86, 100, "Looking for scene changes")
    json.dump({"cuts": scene_cuts(src)}, open(os.path.join(D, "scenes_auto.json"), "w"))
    C.progress(88, 100, "Taking still frames")
    json.dump(stills(src, D, info["duration"]), open(os.path.join(D, "frames.json"), "w"), indent=1)
    C.progress(97, 100, "Listening to the sound")
    json.dump(audio_facts(src, info), open(os.path.join(D, "audio.json"), "w"), indent=2)
    C.progress(100, 100, "Done")
    print("ingest done")


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1])
