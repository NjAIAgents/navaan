#!/usr/bin/env python3
"""media_cfg.py  which services make the pictures, the narration and the music, and the keys they need.

load() / save(updates)   the choices, in <conf>/media.json (not secret). Unknown keys and bad values are refused.
key_state()              which keys are saved: {"openai": bool, "elevenlabs": bool}. A key is never returned to the page.
key_save(provider, key)  test the key against the provider first, then write <conf>/openai.env or elevenlabs.env (mode 600).
get_key(provider)        the key for a step that needs it: the environment variable first, then the file.
usage() / add_usage()    this month's ElevenLabs seconds and OpenAI dollars, so a run can be stopped at the cap.
The conf folder is ~/.config/navaan (NAVAAN_CONF_DIR overrides it). On the server the files are synced to Vault.
"""
import os, re, json, time, datetime, urllib.request, urllib.error

# Voices the narration can use. The ids are not secret. Frank is the default.
VOICES = {
    "frank": {"label": "Frank (deep, wise)", "id": "V2bPluzT7MuirpucVAKH"},
    "nj": {"label": "NJ (my own voice)", "id": "r3RejoyX9duc0wFH79cE"},
}
CHOICES = {
    "image_provider": ("flow", "openai"),
    "image_quality": ("low", "medium", "high"),
    "narration_source": ("upload", "elevenlabs"),
    "voice": tuple(VOICES),
    "eleven_model": ("eleven_v4", "eleven_v3", "eleven_multilingual_v2", "eleven_flash_v2_5", "eleven_turbo_v2_5"),
    "music": ("auto", "library", "none"),
    "motion": ("off", "subtle", "gentle"),
}
NUMBERS = {  # key: (default, min, max)
    "max_run_usd": (0.5, 0.05, 20.0),            # one run may not spend more than this on OpenAI images
    "eleven_monthly_seconds": (1500, 60, 36000),  # ElevenLabs audio allowed per calendar month
}
DEFAULTS = {"image_provider": "flow", "image_quality": "medium", "narration_source": "upload", "voice": "frank",
            "eleven_model": "eleven_v4", "music": "auto", "motion": "subtle", "max_run_usd": 0.5, "eleven_monthly_seconds": 1500}
KEYS = {  # provider: (file, variable, pattern, live test url, auth header builder)
    "openai": ("openai.env", "OPENAI_API_KEY", r"sk-[A-Za-z0-9_\-]{20,300}", "https://api.openai.com/v1/models", lambda k: {"Authorization": "Bearer " + k}),
    "elevenlabs": ("elevenlabs.env", "ELEVENLABS_API_KEY", r"[A-Za-z0-9_\-]{20,200}", "https://api.elevenlabs.io/v1/user", lambda k: {"xi-api-key": k}),
}


def conf_dir():
    return os.environ.get("NAVAAN_CONF_DIR") or os.path.expanduser("~/.config/navaan")


def _atomic_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".new"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load():
    """The choices with defaults filled in. A bad value in the file falls back to the default."""
    raw = _read_json(os.path.join(conf_dir(), "media.json"), {})
    out = dict(DEFAULTS)
    for k, opts in CHOICES.items():
        if raw.get(k) in opts:
            out[k] = raw[k]
    for k, (d, lo, hi) in NUMBERS.items():
        try:
            v = float(raw.get(k, d))
            out[k] = min(hi, max(lo, v))
        except (TypeError, ValueError):
            out[k] = d
    return out


def save(updates):
    """Validate and store the given choices; the others stay as they are."""
    if not isinstance(updates, dict):
        raise ValueError("send an object of settings")
    cur = load()
    for k, v in updates.items():
        if k in CHOICES:
            if v not in CHOICES[k]:
                raise ValueError("%s must be one of: %s" % (k, ", ".join(CHOICES[k])))
            cur[k] = v
        elif k in NUMBERS:
            d, lo, hi = NUMBERS[k]
            try:
                n = float(v)
            except (TypeError, ValueError):
                raise ValueError("%s must be a number" % k)
            if not lo <= n <= hi:
                raise ValueError("%s must be between %s and %s" % (k, lo, hi))
            cur[k] = n
        else:
            raise ValueError("unknown setting: " + str(k))
    _atomic_write(os.path.join(conf_dir(), "media.json"), json.dumps(cur, indent=1))
    return cur


def _read_env(path):
    out = {}
    try:
        for line in open(path, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k and v.strip():
                out[k] = v.strip().strip("\"'")
    except OSError:
        pass
    return out


def get_key(provider):
    file, var = KEYS[provider][0], KEYS[provider][1]
    return os.environ.get(var) or _read_env(os.path.join(conf_dir(), file)).get(var) or ""


def key_state():
    return {p: bool(get_key(p)) for p in KEYS}


def _live_test(provider, key):
    """One cheap read call. Returns (ok, why). Never echoes the key."""
    url, hdr = KEYS[provider][3], KEYS[provider][4](key)
    try:
        urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=20).read(1)
        return True, ""
    except urllib.error.HTTPError as e:
        return False, "%s refused the key (HTTP %s)." % (provider.capitalize(), e.code)
    except Exception as e:
        return False, "Could not reach %s: %s" % (provider.capitalize(), str(e).replace(key, "<key>")[:120])


def key_save(provider, key):
    """Paste a key. It is tested first so a wrong paste never replaces a working key."""
    if provider not in KEYS:
        raise ValueError("provider must be openai or elevenlabs")
    file, var, pat = KEYS[provider][:3]
    k = (key or "").strip().strip("\"'")
    if "=" in k:
        k = k.split("=", 1)[1].strip().strip("\"'")
    if not re.fullmatch(pat, k):
        raise ValueError("That does not look like an %s key. No spaces or line breaks." % provider.capitalize())
    ok, why = _live_test(provider, k)
    if not ok:
        raise ValueError(why)
    _atomic_write(os.path.join(conf_dir(), file), "%s=%s\n" % (var, k))
    return {"ok": True, "provider": provider}


def _month():
    return datetime.date.today().strftime("%Y-%m")


def usage():
    u = _read_json(os.path.join(conf_dir(), "media_usage.json"), {})
    if u.get("month") != _month():
        u = {"month": _month(), "eleven_seconds": 0.0, "openai_usd": 0.0}
    return u


def add_usage(eleven_seconds=0.0, openai_usd=0.0):
    u = usage()
    u["eleven_seconds"] = round(float(u.get("eleven_seconds", 0)) + float(eleven_seconds), 2)
    u["openai_usd"] = round(float(u.get("openai_usd", 0)) + float(openai_usd), 4)
    _atomic_write(os.path.join(conf_dir(), "media_usage.json"), json.dumps(u))
    return u


def status():
    s = load()
    return {"settings": s, "keys": key_state(), "usage": usage(), "voices": {k: v["label"] for k, v in VOICES.items()},
            "choices": {k: list(v) for k, v in CHOICES.items()}}
