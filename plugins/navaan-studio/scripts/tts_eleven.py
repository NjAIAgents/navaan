#!/usr/bin/env python3
"""tts_eleven.py  narration from ElevenLabs, with a cache and a monthly cap so test runs do not burn credits.

synth(text, out, voice=None, model=None, force=False)   one take. The same text, voice and model is never generated twice:
                                                        the earlier file is copied (cached: true). Over the monthly cap it refuses.
estimate(text)                                          rough seconds the take will use, before any spend.
CLI: tts_eleven.py --text-file lines.txt --out voiceover.mp3 [--voice frank|nj] [--model eleven_v4] [--estimate] [--force]
Voice and model default to the Settings choices (media.json). The key comes from ELEVENLABS_API_KEY or elevenlabs.env.
"""
import os, sys, json, shutil, hashlib, argparse, subprocess, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_cfg as M
import navaan_log as L
LOG = L.get("tts_eleven")

CHARS_PER_SECOND = 12.0   # measured: 235 characters of English came out as 19 seconds at a slow, soft pace


def estimate(text):
    return round(len(text.strip()) / CHARS_PER_SECOND, 1)


def cache_dir():
    return os.path.join(M.conf_dir(), "tts_cache")


def _key(text, voice_id, model):
    return hashlib.sha1(("%s|%s|%s" % (voice_id, model, text.strip())).encode("utf-8")).hexdigest()


def _seconds(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=30)
        return round(float(r.stdout.strip()), 2)
    except Exception as _e:
        L.soft(LOG, "seconds_error")
        return 0.0


def synth(text, out, voice=None, model=None, force=False):
    text = (text or "").strip()
    if not text:
        raise ValueError("there is no text to speak")
    s = M.load()
    voice = voice or s["voice"]
    model = model or s["eleven_model"]
    if voice not in M.VOICES:
        raise ValueError("voice must be one of: " + ", ".join(M.VOICES))
    if model not in M.CHOICES["eleven_model"]:
        raise ValueError("unknown ElevenLabs model " + str(model))
    vid = M.VOICES[voice]["id"]
    hit = os.path.join(cache_dir(), _key(text, vid, model) + ".mp3")
    if os.path.exists(hit) and not force:
        shutil.copyfile(hit, out)
        return {"file": out, "cached": True, "seconds": _seconds(out), "voice": voice, "model": model, "spent_seconds": 0.0}
    cap, used, est = s["eleven_monthly_seconds"], M.usage()["eleven_seconds"], estimate(text)
    if used + est > cap:
        raise RuntimeError("The monthly ElevenLabs cap would be passed (%.0f s used of %.0f s, this take needs about %.0f s). Raise the cap in Settings or wait for next month." % (used, cap, est))
    key = M.get_key("elevenlabs")
    if not key:
        raise RuntimeError("No ElevenLabs key is saved. Add it under Settings, Narration.")
    req = urllib.request.Request("https://api.elevenlabs.io/v1/text-to-speech/%s?output_format=mp3_44100_128" % vid,
                                 data=json.dumps({"text": text, "model_id": model}).encode("utf-8"),
                                 headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    try:
        data = urllib.request.urlopen(req, timeout=180).read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace").replace(key, "<key>")[:200]
        raise RuntimeError("ElevenLabs refused the request (HTTP %s): %s" % (e.code, body))
    os.makedirs(cache_dir(), exist_ok=True)
    with open(hit, "wb") as f:
        f.write(data)
    shutil.copyfile(hit, out)
    secs = _seconds(out)
    M.add_usage(eleven_seconds=secs)
    return {"file": out, "cached": False, "seconds": secs, "voice": voice, "model": model, "spent_seconds": secs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text-file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice")
    ap.add_argument("--model")
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    text = open(a.text_file, encoding="utf-8").read()
    if a.estimate:
        print(json.dumps({"estimated_seconds": estimate(text), "used_this_month": M.usage()["eleven_seconds"], "cap": M.load()["eleven_monthly_seconds"]}))
        return
    print(json.dumps(synth(text, a.out, a.voice, a.model, a.force)))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as e:
        L.ignored(LOG, "module: ValueError/RuntimeError (optional or expected)", e)
        sys.exit(str(e))
