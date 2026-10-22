#!/usr/bin/env python3
"""media_cfg.py  which services make the pictures, the narration and the music, and the keys they need.

load() / save(updates)   the choices, in <conf>/media.json (not secret). Unknown keys and bad values are refused.
key_state()              which keys are saved: {"openai": bool, "muse": bool, "elevenlabs": bool}. A key is never returned to the page.
key_save(provider, key)  test the key against the provider first, then write <conf>/openai.env, muse.env or elevenlabs.env (mode 600).
get_key(provider)        the key for a step that needs it: the environment variable first, then the file.
usage() / add_usage()    this month's ElevenLabs seconds and picture dollars (openai_usd counts Muse pictures too), so a run can be stopped at the cap.
The conf folder is ~/.config/navaan (NAVAAN_CONF_DIR overrides it). On the server the files are synced to Vault.
"""
import os, re, json, time, datetime, urllib.request, urllib.error
import navaan_log as L
LOG = L.get("media_cfg")

# Voices the narration can use. The ids are not secret. SunoCustom1 is the default.
VOICES = {
    "suno1": {"label": "SunoCustom1 (deep, unhurried)", "id": "RolbsV2FrXoOuw9WMoGA"},
    "suno2": {"label": "SunoCustom2 (deep, unhurried)", "id": "bPnfgYfv98trOeQJkL0s"},
    "suno3": {"label": "SunoCustom3 (deep, unhurried)", "id": "neLkJ2FTGxCOW53t1Gsi"},
    "frank": {"label": "Frank (deep, wise)", "id": "V2bPluzT7MuirpucVAKH"},
    "nj": {"label": "NJ (my own voice)", "id": "r3RejoyX9duc0wFH79cE"},
}
CHOICES = {
    "image_provider": ("flow", "openai"),       # "openai" means an image API paints the pictures (not Flow); image_engine says which one
    "image_engine": ("openai", "muse"),         # the image API: OpenAI (default) or Meta Muse Image
    "picture_director": ("openai", "claude"),   # who writes the picture plan: OpenAI chat model (default) or Claude
    "image_model": ("gpt-image-2.5-flare", "gpt-image-2.5-sunburst", "gpt-image-2"),   # flare: fast and cheap (default); sunburst: more precise; gpt-image-2: the older one
    "image_quality": ("low", "medium", "high", "xhigh", "max"),   # on the 2.5 models high is about the old medium
    "image_size_landscape": ("1792x1008", "1536x864"),   # songs, exactly 16:9; 1536x864 is the smaller, cheaper size
    "image_size": ("1152x2048", "1024x1536"),   # 1152x2048 is exactly 9:16; 1024x1536 is the smaller, cheaper size
    "narration_source": ("upload", "elevenlabs"),
    "voice": tuple(VOICES),
    "eleven_model": ("eleven_v4", "eleven_v3", "eleven_multilingual_v2", "eleven_flash_v2_5", "eleven_turbo_v2_5"),
    "music": ("auto", "library", "none"),
    "motion": ("off", "subtle", "gentle"),
}
NUMBERS = {  # key: (default, min, max)
    "max_run_usd": (0.8, 0.05, 20.0),            # one run may not spend more than this on OpenAI images
    "song_pictures": (16, 6, 40),                 # pictures the director plans per song (16 at high 1792x1008 on flare is about 0.77 dollars)
    "eleven_monthly_seconds": (1500, 60, 36000),  # ElevenLabs audio allowed per calendar month
}
DEFAULTS = {"image_provider": "flow", "image_engine": "openai", "picture_director": "openai", "image_model": "gpt-image-2.5-flare", "image_quality": "high", "image_size": "1152x2048", "image_size_landscape": "1792x1008", "narration_source": "upload", "voice": "suno1",
            "eleven_model": "eleven_v4", "music": "auto", "motion": "subtle", "max_run_usd": 0.8, "song_pictures": 16, "eleven_monthly_seconds": 1500}
KEYS = {  # provider: (file, variable, pattern, live test url, auth header builder)
    "openai": ("openai.env", "OPENAI_API_KEY", r"sk-[A-Za-z0-9_\-]{20,300}", "https://api.openai.com/v1/models", lambda k: {"Authorization": "Bearer " + k}),
    "elevenlabs": ("elevenlabs.env", "ELEVENLABS_API_KEY", r"[A-Za-z0-9_\-]{20,200}", "https://api.elevenlabs.io/v1/user", lambda k: {"xi-api-key": k}),
    "devto": ("devto.env", "DEVTO_API_KEY", r"[A-Za-z0-9_\-]{16,120}", "https://dev.to/api/users/me", lambda k: {"api-key": k, "Accept": "application/vnd.forem.api-v1+json"}),   # the owner's key from dev.to Settings, Extensions (NAV-78)
    "linkedin": ("linkedin.env", "LINKEDIN_TOKEN", r"[A-Za-z0-9_\-.~+/=]{20,2500}", "https://api.linkedin.com/v2/userinfo", lambda k: {"Authorization": "Bearer " + k}),   # an access token with w_member_social; saved by linkedin_save, with the member's URN
    "muse": ("muse.env", "MUSE_API_KEY", r"[A-Za-z0-9_\-|.]{16,400}", None, lambda k: {"Authorization": "Bearer " + k}),   # Meta Model API; no free read call is documented, so the key is not live-tested
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
    except (OSError, ValueError) as _e:
        L.ignored(LOG, "_read_json: OSError/ValueError (optional or expected)", _e)
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
        except (TypeError, ValueError) as _e:
            L.ignored(LOG, "load: TypeError/ValueError (optional or expected)", _e)
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
    except OSError as _e:
        L.ignored(LOG, "_read_env: OSError (optional or expected)", _e)
        pass
    return out


def get_key(provider):
    file, var = KEYS[provider][0], KEYS[provider][1]
    return os.environ.get(var) or _read_env(os.path.join(conf_dir(), file)).get(var) or ""


def key_state():
    return {p: bool(get_key(p)) for p in KEYS}


def _live_test(provider, key):
    """One cheap read call. Returns (ok, why, note). Never echoes the key. A provider that says the key is genuine but lacks the permission this test needs (ElevenLabs: missing_permissions)
    counts as a good key, with a note: the key is recognised, and what it is for is only found out when it is used."""
    url, hdr = KEYS[provider][3], KEYS[provider][4](key)
    name = {"elevenlabs": "ElevenLabs", "openai": "OpenAI", "devto": "dev.to", "linkedin": "LinkedIn"}.get(provider, provider.capitalize())
    if not url: return True, "", ""   # Muse: no free read call is documented, so its key is not live-tested
    try:
        urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=20).read(1)
        return True, "", ""
    except urllib.error.HTTPError as e:
        L.ignored(LOG, "_live_test: HTTPError (optional or expected)", e)
        status, msg = "", ""
        try:
            d = json.loads(e.read().decode("utf-8", "replace")); d = d.get("detail", d) if isinstance(d, dict) else {}
            if isinstance(d, dict): status, msg = str(d.get("status") or ""), str(d.get("message") or "")
        except Exception as _e: L.ignored(LOG, "_live_test: unreadable error body", _e)   # expected: not every refusal has a JSON body
        if status == "missing_permissions":
            return True, "", "%s recognised the key but it has no permission to read the account, so it could not be checked further. It is saved; narration works if the key has Text to Speech." % name
        why = "%s refused the key (HTTP %s)" % (name, e.code)
        if status == "invalid_api_key" or e.code == 401 and not msg: why += ": it is not a valid key. Copy it again from API Keys (it is shown only once) with no spaces."
        elif msg: why += ": " + msg.replace(key, "<key>")[:160]
        return False, why + ("." if not why.endswith(".") else ""), ""
    except Exception as e:
        L.soft(LOG, "live_test_error")
        return False, "Could not reach %s: %s" % (name, str(e).replace(key, "<key>")[:120]), ""


def key_save(provider, key):
    """Paste a key. It is tested first so a wrong paste never replaces a working key."""
    if provider not in KEYS:
        raise ValueError("provider must be one of: " + ", ".join(KEYS))
    file, var, pat = KEYS[provider][:3]
    k = (key or "").strip().strip("\"'")
    if "=" in k:
        k = k.split("=", 1)[1].strip().strip("\"'")
    if not re.fullmatch(pat, k):
        raise ValueError("That does not look like an %s key. No spaces or line breaks." % provider.capitalize())
    ok, why, note = _live_test(provider, k)
    if not ok:
        raise ValueError(why)
    _atomic_write(os.path.join(conf_dir(), file), "%s=%s\n" % (var, k))
    return {"ok": True, "provider": provider, "note": note}


def linkedin_author():
    """The member's URN (urn:li:person:<id>) saved with the LinkedIn token, or ''."""
    return _read_env(os.path.join(conf_dir(), KEYS["linkedin"][0])).get("LINKEDIN_AUTHOR", "")


def linkedin_save(token, author=""):
    """Paste a LinkedIn access token (permission w_member_social) and, when it cannot be asked for, the member id. The token is not tested by posting: it is tested by asking LinkedIn who it belongs to, which
    needs the openid scope; a token without it is kept if the member id is given. Nothing is written when neither works, so a wrong paste never replaces a working login."""
    file, var, pat = KEYS["linkedin"][:3]
    t = (token or "").strip().strip("\"'")
    if "=" in t: t = t.split("=", 1)[1].strip().strip("\"'")
    if not re.fullmatch(pat, t): raise ValueError("That does not look like a LinkedIn access token. No spaces or line breaks.")
    a = (author or "").strip()
    if a and not re.fullmatch(r"(urn:li:person:)?[A-Za-z0-9_\-]{3,60}", a): raise ValueError("The member id is letters, digits, - and _ (or urn:li:person:<id>).")
    if a and not a.startswith("urn:li:"): a = "urn:li:person:" + a
    note = ""
    try:
        req = urllib.request.Request(KEYS["linkedin"][3], headers=KEYS["linkedin"][4](t)); me = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace"))
        if not a and me.get("sub"): a = "urn:li:person:" + str(me["sub"]); note = "LinkedIn says this token is for " + (str(me.get("name") or "your profile")) + "."
    except urllib.error.HTTPError as e:
        L.ignored(LOG, "linkedin_save: userinfo refused", e)
        if e.code == 401: raise ValueError("LinkedIn refused the token (HTTP 401): it is wrong or has expired. Make a new one.")
        if not a: raise ValueError("LinkedIn would not say whose token this is (it needs the openid and profile scopes). Add your member id too, or make the token with those scopes.")
    except Exception as e:
        L.soft(LOG, "linkedin_save_error")
        if not a: raise ValueError("Could not reach LinkedIn: " + str(e).replace(t, "<token>")[:120])
    if not a: raise ValueError("LinkedIn did not give a member id. Add it in the second box.")
    _atomic_write(os.path.join(conf_dir(), file), "%s=%s\nLINKEDIN_AUTHOR=%s\n" % (var, t, a))
    return {"ok": True, "provider": "linkedin", "note": note or "Saved. Posting uses " + a + "."}


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
