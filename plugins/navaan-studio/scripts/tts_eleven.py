#!/usr/bin/env python3
"""tts_eleven.py  narration from ElevenLabs, with a cache and a monthly cap so test runs do not burn credits.

synth(text, out, voice=None, model=None, force=False)   one take. The same text, voice and model is never generated twice:
                                                        the earlier file is copied (cached: true). Over the monthly cap it refuses.
estimate(text)                                          rough seconds the take will use, before any spend.
CLI: tts_eleven.py --text-file lines.txt --out voiceover.mp3 [--voice suno1|suno2|suno3|frank|nj] [--model eleven_v4] [--estimate] [--force]
Voice and model default to the Settings choices (media.json). The key comes from ELEVENLABS_API_KEY or elevenlabs.env.
"""
import os, re, sys, json, shutil, hashlib, argparse, subprocess, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_cfg as M
import navaan_log as L
LOG = L.get("tts_eleven")

CHARS_PER_SECOND = 12.0   # measured: 235 characters of English came out as 19 seconds at a slow, soft pace
TAG_MODELS = ("eleven_v4", "eleven_v3")   # measured on the live service: these take the speed setting and ignore it, but they obey direction tags in the text; the other models obey the speed setting
PACES = {"slow": 0.75, "calm": 0.85, "normal": 1.0}   # ElevenLabs speed: 0.7 slowest, 1.0 as the voice speaks, 1.2 fastest


def estimate(text, speed=1.0):
    return round(len(text.strip()) / CHARS_PER_SECOND / max(0.5, float(speed or 1.0)), 1)


def directed(text, speed):
    """The text with direction tags for a pace below 1.0 (eleven_v4 / v3 only). Slow: warm, soft, slow, a pause between lines and after each comma."""
    if not speed or speed >= 1.0: return text
    slow = speed <= 0.8
    body = re.sub(r"\n\s*\n", " [pause] ", text.strip())
    if slow:   # measured on the live service: the tag alone does not slow v4 (5.76 s for a sentence); an ellipsis between phrases does (7.84 s for the same words)
        body = re.sub(r",\s+", "... ", body)
        body = re.sub(r"(?<![.])(?<!even)\s+(?=(?:to|and|for|but|when|without|your|even)\b)", "... ", body)
    return ("[warmly] [softly] [slowly] " if slow else "[warmly] [softly] ") + body


def cache_dir():
    # not the config folder: on the server that is a 16 MB memory disk that holds the tokens (a few takes would fill it)
    return os.path.join(os.environ.get("NAVAAN_CACHE_DIR") or os.path.join(os.path.expanduser("~"), ".cache", "navaan"), "tts_cache")


def _key(text, voice_id, model, speed=1.0):
    return hashlib.sha1(("%s|%s|%s|%s" % (voice_id, model, speed, text.strip())).encode("utf-8")).hexdigest()


def _seconds(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=30)
        return round(float(r.stdout.strip()), 2)
    except Exception as _e:
        L.soft(LOG, "seconds_error")
        return 0.0


def synth(text, out, voice=None, model=None, force=False, speed=None):
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
    speed = None if speed is None else round(min(1.2, max(0.7, float(speed))), 2)
    spoken, setting = text, speed
    if model in TAG_MODELS: spoken, setting = directed(text, speed), None   # this model is paced by tags, not by the speed setting
    hit = os.path.join(cache_dir(), _key(spoken, vid, model, speed or 1.0) + ".mp3")
    if os.path.exists(hit) and not force:
        shutil.copyfile(hit, out)
        return {"file": out, "cached": True, "seconds": _seconds(out), "voice": voice, "model": model, "spent_seconds": 0.0}
    cap, used, est = s["eleven_monthly_seconds"], M.usage()["eleven_seconds"], estimate(text, speed or 1.0)
    if used + est > cap:
        raise RuntimeError("The monthly ElevenLabs cap would be passed (%.0f s used of %.0f s, this take needs about %.0f s). Raise the cap in Settings or wait for next month." % (used, cap, est))
    key = M.get_key("elevenlabs")
    if not key:
        raise RuntimeError("No ElevenLabs key is saved. Add it under Settings, Narration.")
    def ask(settings):
        body = {"text": spoken, "model_id": model}
        if settings: body["voice_settings"] = settings
        req = urllib.request.Request("https://api.elevenlabs.io/v1/text-to-speech/%s?output_format=mp3_44100_128" % vid, data=json.dumps(body).encode("utf-8"),
                                     headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        return urllib.request.urlopen(req, timeout=180).read()
    try:
        try: data = ask({"speed": setting, "stability": 0.6, "similarity_boost": 0.8} if setting else None)
        except urllib.error.HTTPError as e:
            if setting and e.code in (400, 422): data = ask(None)   # this model does not take the speed setting: speak at its own pace rather than fail
            else: raise
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
