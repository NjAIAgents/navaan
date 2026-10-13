#!/usr/bin/env python3
"""settings_api.py  what the portal's Settings page shows and does: the login files behind every account.

status()                       one entry per content type (music, inspiration, ...) with the Instagram login, the market login
                               (Facebook, for peer data), the YouTube login and the cloud bucket: present, who it is, when it expires.
ig_refresh(ctype, kind)        extend an Instagram Login token by 60 days (Meta's refresh_access_token) and store the new expiry.
ig_save(ctype, kind, token)    validate a pasted token and write it into the account's login file (login or market).
yt_signin(ctype)               start publish_youtube.py auth for that account in the background (it opens the browser on this Mac).
Tokens are only ever written to the login files under ~/.config/navaan with mode 600. They are never returned to the page.
"""
import os, sys, json, time, datetime, subprocess, threading, urllib.request, urllib.parse, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~/.config/navaan")
YT = {"running": False, "ctype": None, "rc": None, "tail": "", "started": 0}
_cache = {"at": 0, "data": None}


def _env_path(ctype):
    a = C.account(ctype)
    return a["ig_env"] or os.path.join(HOME, "instagram.env")


def _yt_path(ctype):
    a = C.account(ctype)
    return a["yt_token"] or os.path.join(HOME, "youtube_token.json")


def _read_env(path):
    out = {}
    if path and os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip()
    return out


def _write_env(path, updates):
    """Replace or add the given keys, keep every other line as it is, mode 600."""
    lines = [l for l in (open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []) if l.split("=", 1)[0].strip() not in updates]
    lines += [f"{k}={v}" for k, v in updates.items() if v is not None]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)


def _get(url, params, timeout=20):
    u = url + "?" + urllib.parse.urlencode(params)
    try:
        return json.loads(urllib.request.urlopen(u, timeout=timeout).read()), ""
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try: msg = json.loads(body)["error"]["message"]
        except Exception: msg = body[:200]
        return None, f"{e.code}: {msg}"
    except Exception as e:
        return None, str(e)[:200]


def _days(iso):
    try:
        d = datetime.datetime.strptime(iso[:10], "%Y-%m-%d").date()
        return (d - datetime.date.today()).days
    except Exception:
        return None


def _ig_status(env, host_key, uid_key, tok_key, exp_key):
    """Instagram Login host: /me proves the token works, the expiry is what we stored at save or refresh time.
    Facebook host: debug_token gives the real expiry."""
    host = env.get(host_key) or ("https://graph.facebook.com" if host_key.startswith("NAVAAN_IG_MARKET") else "https://graph.instagram.com")
    uid, tok = env.get(uid_key), env.get(tok_key)
    if not tok or not uid:
        return {"present": False}
    out = {"present": True, "host": host, "user_id_tail": uid[-4:], "expires": env.get(exp_key) or None}
    if "facebook" in host:
        d, err = _get(f"{host}/v21.0/debug_token", {"input_token": tok, "access_token": tok})
        if d:
            info = d.get("data", {})
            exp = info.get("expires_at") or 0
            out["expires"] = datetime.datetime.fromtimestamp(exp).strftime("%Y-%m-%d") if exp else "never"
            out["ok"] = bool(info.get("is_valid"))
            out["scopes"] = info.get("scopes", [])
        else:
            out["ok"] = False; out["error"] = err
    else:
        d, err = _get(f"{host}/v21.0/me", {"fields": "id,username", "access_token": tok})
        out["ok"] = bool(d); out["username"] = (d or {}).get("username"); out["error"] = err if not d else ""
    out["days_left"] = _days(out["expires"]) if out.get("expires") and out["expires"] != "never" else None
    return out


def _yt_status(path):
    if not os.path.exists(path):
        return {"present": False}
    out = {"present": True}
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        t = json.load(open(path))
        creds = Credentials.from_authorized_user_info(t)
        if not creds.valid:
            creds.refresh(Request())
            with open(path, "w") as f: f.write(creds.to_json())
            os.chmod(path, 0o600)
        items = build("youtube", "v3", credentials=creds).channels().list(part="snippet", mine=True).execute().get("items", [])
        out["ok"] = True; out["channel"] = items[0]["snippet"]["title"] if items else "(no channel)"
        out["account"] = t.get("account") or ""
    except Exception as e:
        msg = str(e)
        out["ok"] = False
        out["error"] = "sign in again (refresh token expired or revoked)" if "invalid_grant" in msg else msg[:200]
    return out


headless = C.headless


def claude_status():
    """Which credential the Claude steps use and whether the last step could use it. Never the value itself."""
    C.load_claude_env()
    kind = "API key" if os.environ.get("ANTHROPIC_API_KEY") else "subscription token" if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") else ""
    if not kind and not headless(): kind = "this computer's Claude login"
    st = C.CLAUDE_STATE["problem"] or ("ok" if kind else "missing")
    return {"credential": kind, "state": st, "since": C.CLAUDE_STATE["at"], "headless": headless()}


def status(force=False):
    if not force and _cache["data"] and time.time() - _cache["at"] < 600:
        d = dict(_cache["data"]); d["yt_job"] = dict(YT); d["claude"] = claude_status(); return d
    types = ["music"] + sorted(k for k in (C.cfg("accounts") or {}).keys() if k != "music")
    accounts = []
    for t in types:
        a = C.account(t); env_path = _env_path(t); env = _read_env(env_path); yt_path = _yt_path(t)
        accounts.append({"type": t, "handle": a.get("handle") or "", "youtube_channel": a.get("youtube_channel") or "", "configured": a["configured"],
                         "ig_env": env_path, "ig": _ig_status(env, "NAVAAN_IG_HOST", "NAVAAN_IG_USER_ID", "NAVAAN_IG_TOKEN", "NAVAAN_IG_TOKEN_EXPIRES"),
                         "market": _ig_status(env, "NAVAAN_IG_MARKET_HOST", "NAVAAN_IG_MARKET_USER_ID", "NAVAAN_IG_MARKET_TOKEN", "NAVAAN_IG_MARKET_EXPIRES"),
                         "yt_token": yt_path, "yt": _yt_status(yt_path)})
    data = {"accounts": accounts, "cloud": {"provider": C.cfg("storage.cloud_provider", "none"), "bucket": C.cfg("storage.cloud_bucket", ""), "region": C.cfg("storage.cloud_region", "")},
            "secret_present": os.path.exists(os.path.join(HOME, "youtube_client_secret.json")), "checked_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    _cache.update(at=time.time(), data=data)
    d = dict(data); d["yt_job"] = dict(YT); d["claude"] = claude_status(); return d


def ig_refresh(ctype, kind="login"):
    """Instagram Login tokens can be refreshed any time after 24 hours of age and get a fresh 60 days."""
    env_path = _env_path(ctype); env = _read_env(env_path)
    if kind != "login": raise ValueError("only the Instagram Login token can be refreshed here; the Facebook token is replaced by pasting a new one")
    tok, host = env.get("NAVAAN_IG_TOKEN"), env.get("NAVAAN_IG_HOST") or "https://graph.instagram.com"
    if not tok: raise ValueError("no Instagram token in " + env_path)
    if "facebook" in host: raise ValueError("this account uses a Facebook Login token; paste a new one instead")
    d, err = _get(f"{host}/refresh_access_token", {"grant_type": "ig_refresh_token", "access_token": tok})
    if not d: raise ValueError("Instagram refused the refresh: " + err)
    exp = (datetime.date.today() + datetime.timedelta(seconds=int(d.get("expires_in") or 0))).isoformat()
    _write_env(env_path, {"NAVAAN_IG_TOKEN": d["access_token"], "NAVAAN_IG_TOKEN_EXPIRES": exp})
    _cache["at"] = 0
    return {"expires": exp}


def ig_save(ctype, kind, token):
    token = (token or "").strip()
    if not token or " " in token or len(token) < 20: raise ValueError("that does not look like a token")
    env_path = _env_path(ctype); env = _read_env(env_path)
    if kind == "login":
        host = env.get("NAVAAN_IG_HOST") or "https://graph.instagram.com"
        d, err = _get(f"{host}/v21.0/me", {"fields": "id,user_id,username", "access_token": token})
        if not d: raise ValueError("Instagram rejected the token: " + err)
        want = (C.account(ctype).get("handle") or "").lstrip("@").lower()
        if want and d.get("username", "").lower() != want:
            raise ValueError(f"that token belongs to @{d.get('username')}, this account publishes as @{want}")
        exp = (datetime.date.today() + datetime.timedelta(days=60)).isoformat()
        up = {"NAVAAN_IG_TOKEN": token, "NAVAAN_IG_TOKEN_EXPIRES": exp}
        if d.get("user_id"): up["NAVAAN_IG_USER_ID"] = str(d["user_id"])
        _write_env(env_path, up); _cache["at"] = 0
        return {"username": d.get("username"), "expires": exp}
    if kind == "market":
        d, err = _get("https://graph.facebook.com/v21.0/me/accounts", {"fields": "id,name,instagram_business_account{id,username}", "access_token": token})
        if not d: raise ValueError("Facebook rejected the token: " + err)
        linked = [p for p in d.get("data", []) if p.get("instagram_business_account")]
        if not linked: raise ValueError("this token sees no Facebook Page linked to an Instagram account")
        ig = linked[0]["instagram_business_account"]
        t, err = _get(f"https://graph.facebook.com/v21.0/{ig['id']}", {"fields": "business_discovery.username(instagram){username}", "access_token": token})
        if not t: raise ValueError("token works but Business Discovery is refused: " + err + ". It needs instagram_basic, instagram_manage_insights, pages_read_engagement, pages_show_list.")
        dbg, _ = _get("https://graph.facebook.com/v21.0/debug_token", {"input_token": token, "access_token": token})
        exp = (dbg or {}).get("data", {}).get("expires_at") or 0
        expd = datetime.datetime.fromtimestamp(exp).strftime("%Y-%m-%d") if exp else "never"
        _write_env(env_path, {"NAVAAN_IG_MARKET_USER_ID": str(ig["id"]), "NAVAAN_IG_MARKET_TOKEN": token, "NAVAAN_IG_MARKET_HOST": "https://graph.facebook.com", "NAVAAN_IG_MARKET_EXPIRES": expd})
        _cache["at"] = 0
        return {"username": ig.get("username"), "expires": expd}
    raise ValueError("kind must be login or market")


def yt_signin(ctype):
    """Runs publish_youtube.py auth for this account. The Google sign-in opens in the browser on this computer."""
    if YT["running"]: return False
    path = _yt_path(ctype); a = C.account(ctype)
    env = dict(os.environ); env["NAVAAN_YT_TOKEN"] = path
    if a.get("yt_secret"): env["NAVAAN_YT_CLIENT_SECRETS"] = a["yt_secret"]
    YT.update(running=True, ctype=ctype, rc=None, tail="", started=int(time.time()))

    def work():
        try:
            if os.path.exists(path): os.rename(path, path + ".old")  # force a fresh browser sign-in instead of a silent refresh
            p = subprocess.run([sys.executable, os.path.join(HERE, "publish_youtube.py"), "auth"], capture_output=True, text=True, timeout=600, env=env)
            YT.update(rc=p.returncode, tail=((p.stdout or "") + (p.stderr or "")).strip()[-600:])
            if p.returncode != 0 and not os.path.exists(path) and os.path.exists(path + ".old"): os.rename(path + ".old", path)
        except Exception as e:
            YT.update(rc=2, tail=str(e)[:300])
            if not os.path.exists(path) and os.path.exists(path + ".old"): os.rename(path + ".old", path)
        finally:
            YT["running"] = False; _cache["at"] = 0
            if os.path.exists(path + ".old"):
                try: os.remove(path + ".old")
                except OSError: pass
    threading.Thread(target=work, daemon=True).start()
    return True


def add_account(ctype, handle, channel):
    """Create accounts.<type> in navaan.config.json with its own login files, so a new content type can never post to NAVAAN's channels."""
    import re
    ctype = (ctype or "").strip().lower()
    if not re.match(r"^[a-z][a-z0-9_]{1,23}$", ctype) or ctype == "music": raise ValueError("type must be a short lowercase word, not music")
    p = os.path.join(C.find_root(), "navaan.config.json")
    cfg = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    acc = cfg.setdefault("accounts", {})
    acc[ctype] = {"instagram_handle": (handle or "").strip().lstrip("@"), "youtube_channel": (channel or "").strip(),
                  "instagram_env": f"~/.config/navaan/instagram_{ctype}.env", "youtube_token": f"~/.config/navaan/youtube_token_{ctype}.json",
                  "youtube_client_secret": "~/.config/navaan/youtube_client_secret.json"}
    json.dump(cfg, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    _cache["at"] = 0
    return acc[ctype]


def save_secret(content):
    """Store the Google OAuth client JSON (Desktop app) as ~/.config/navaan/youtube_client_secret.json."""
    try:
        j = json.loads(content)
    except Exception:
        raise ValueError("that is not the JSON file Google gave you")
    if "installed" not in j and "web" not in j: raise ValueError("this JSON is not an OAuth client (expected an 'installed' key: create a Desktop app client)")
    os.makedirs(HOME, exist_ok=True)
    p = os.path.join(HOME, "youtube_client_secret.json")
    with open(p, "w", encoding="utf-8") as f: f.write(json.dumps(j))
    os.chmod(p, 0o600); _cache["at"] = 0
    return {"saved": p}
