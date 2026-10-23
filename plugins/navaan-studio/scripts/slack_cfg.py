#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-23
Last updated: 2026-10-23
Description: connect NAVAAN Studio to a Slack workspace with Slack's OAuth v2 and pick the channel it talks in (NAV-151, the first story of the Slack epic NAV-153).

  app_save(client_id, client_secret, signing_secret, app_token)   the Slack app the owner made once (secrets, kept like every key: config dir, Vault)
  start()                         the address of Slack's authorize page, with a single-use state; the browser is sent there by the Connect button
  finish(query)                   the callback: the state is checked, the code is exchanged for the bot token, and the workspace and the person who connected are recorded
  channels() / set_channel(id)    the channels the bot can see; one is chosen and a hello is posted there to prove the bot can write in it
  disconnect()                    the bot token is revoked at Slack and forgotten here (the app's own keys stay)
  status(check=False)             what Settings shows; never a secret

Files in the config dir (refilled from Vault, listed in deploy/vault_sync.py KNOWN): slack.env (the secrets: client secret, signing secret, app-level token, bot token)
and slack.json (what is not secret: workspace, bot user, the person who connected, the channel). Only the person who connected may approve or start anything from Slack
(later stories). Every call to Slack goes through HTTP(), so the tests never reach Slack.
"""
import os, sys, re, json, time, secrets, urllib.request, urllib.error, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_cfg
import navaan_log as L
LOG = L.get("slack_cfg")

ENV, META = "slack.env", "slack.json"
AUTHORIZE = "https://slack.com/oauth/v2/authorize"
API = "https://slack.com/api/"
SCOPES = "chat:write,commands,channels:read,groups:read"   # post, slash commands (NAV-156/157), see the channels to pick one; more only when a story needs them (then: Reconnect)
STATE_TTL = 600            # Slack's code lives ten minutes; a Connect left longer starts again
STATES = {}                # state -> (expiry, who started it): Connects started from this server, single use (the web process is one process)
PATTERNS = {"SLACK_CLIENT_ID": r"\d{6,20}\.\d{6,20}", "SLACK_CLIENT_SECRET": r"[0-9a-f]{32}", "SLACK_SIGNING_SECRET": r"[0-9a-f]{32}", "SLACK_APP_TOKEN": r"xapp-[A-Za-z0-9-]{20,300}"}
NAMES = {"SLACK_CLIENT_ID": "Client ID", "SLACK_CLIENT_SECRET": "Client Secret", "SLACK_SIGNING_SECRET": "Signing Secret", "SLACK_APP_TOKEN": "App-level token"}


def HTTP(method, url, headers=None, data=None, timeout=20):
    """(status, parsed JSON or {}) from Slack. A refusal is returned, not raised."""
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    req = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": "navaan-studio", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, json.loads(r.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode("utf-8", "replace") or "{}")
        except ValueError: return e.code, {}   # expected: a refusal that is not JSON
    except (urllib.error.URLError, OSError, ValueError) as e: return 0, {"error": "could not reach Slack: " + str(e)[:120]}   # expected: no network; said to the owner, not raised


def _p(n): return os.path.join(media_cfg.conf_dir(), n)
def _env(): return media_cfg._read_env(_p(ENV))
def _meta(): return media_cfg._read_json(_p(META), {}) or {}


def _write_env(d): media_cfg._atomic_write(_p(ENV), "".join(f"{k}={v}\n" for k, v in d.items() if v))
def _write_meta(d): media_cfg._atomic_write(_p(META), json.dumps(d, indent=1, ensure_ascii=False))


def redirect_uri():
    """Where Slack sends the browser back: the studio host (NAVAAN_STUDIO_HOST), or NAVAAN_SLACK_REDIRECT. Slack requires https and the same address in the Slack app."""
    u = os.environ.get("NAVAAN_SLACK_REDIRECT", "").strip()
    if u: return u
    h = os.environ.get("NAVAAN_STUDIO_HOST", "").strip().lower()
    return f"https://{h}/api/slack/callback" if h else ""


def setup():
    """What the owner enters in the Slack app once (shown in Settings)."""
    return {"redirect_url": redirect_uri(), "bot_scopes": SCOPES.split(","), "socket_mode": True, "app_token_scope": "connections:write"}


def app_save(client_id, client_secret, signing_secret, app_token):
    """Save the Slack app's keys. A field left empty keeps what is saved; a value that does not look right is refused in words and nothing is written."""
    given = {"SLACK_CLIENT_ID": client_id, "SLACK_CLIENT_SECRET": client_secret, "SLACK_SIGNING_SECRET": signing_secret, "SLACK_APP_TOKEN": app_token}
    cur = _env()
    for k, v in given.items():
        v = str(v or "").strip()
        if not v: continue
        if not re.fullmatch(PATTERNS[k], v): raise ValueError(f"That does not look like the Slack app's {NAMES[k]}. Copy it from the Slack app's Basic Information page.")
        cur[k] = v
    missing = [NAMES[k] for k in ("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_SIGNING_SECRET") if not cur.get(k)]
    if missing: raise ValueError("Still needed: " + ", ".join(missing) + ".")
    _write_env(cur)
    return status()


def start(who=""):
    """The address of Slack's authorize page for a new Connect. ValueError in words when the app is not saved or there is no https address to come back to."""
    e = _env()
    if not e.get("SLACK_CLIENT_ID") or not e.get("SLACK_CLIENT_SECRET"): raise ValueError("Save the Slack app's Client ID and Client Secret first.")
    back = redirect_uri()
    if not back.startswith("https://"): raise ValueError("Slack sends you back only to an https address, and this studio has none (NAVAAN_STUDIO_HOST is not set). Connect from the studio's own site.")
    now = time.time()
    for s in [s for s, v in STATES.items() if v[0] < now]: STATES.pop(s, None)
    state = secrets.token_urlsafe(24); STATES[state] = (now + STATE_TTL, who)
    return AUTHORIZE + "?" + urllib.parse.urlencode({"client_id": e["SLACK_CLIENT_ID"], "scope": SCOPES, "redirect_uri": back, "state": state})


def finish(query):
    """The callback (its query as a dict of lists or strings). Returns who started the Connect; ValueError in words when anything is wrong, and nothing is saved then.
    The browser comes back from slack.com without the studio's session cookie (SameSite=Strict), so the state is the proof: unguessable, single use, ten minutes, made only for the owner."""
    q = {k: (v[0] if isinstance(v, list) else v) for k, v in (query or {}).items()}
    if q.get("error"): raise ValueError("Slack says the connection was not approved (" + str(q["error"])[:60] + ").")
    state, code = str(q.get("state") or ""), str(q.get("code") or "")
    exp, who_started = STATES.pop(state, None) if state in STATES else (None, "")   # single use: a state is gone after its first callback, right or wrong
    if not exp: raise ValueError("This sign-in did not start here, or it was already used. Press Connect Slack again.")
    if exp < time.time(): raise ValueError("The sign-in took too long (more than ten minutes). Press Connect Slack again.")
    if not code: raise ValueError("Slack sent no code back. Press Connect Slack again.")
    e = _env()
    st, r = HTTP("POST", API + "oauth.v2.access", data={"client_id": e.get("SLACK_CLIENT_ID", ""), "client_secret": e.get("SLACK_CLIENT_SECRET", ""), "code": code, "redirect_uri": redirect_uri()})
    if not r.get("ok"): raise ValueError("Slack refused the connection: " + str(r.get("error") or f"HTTP {st}")[:80] + ".")
    if r.get("token_type") != "bot" or not str(r.get("access_token", "")).startswith("xoxb-"): raise ValueError("Slack did not give a bot token. Check the Slack app has a bot user and the bot scopes.")
    team = r.get("team") or {}
    who = (r.get("authed_user") or {}).get("id") or ""   # Slack documents it with user scopes; when it is missing, the owner gives their Slack member id in Settings
    e["SLACK_BOT_TOKEN"] = r["access_token"]; _write_env(e)
    m = {"team_id": team.get("id", ""), "team_name": team.get("name", ""), "bot_user_id": r.get("bot_user_id", ""), "app_id": r.get("app_id", ""), "owner_user_id": who,
         "scopes": r.get("scope", ""), "connected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    old = _meta()
    if old.get("team_id") == m["team_id"] and old.get("channel_id"): m.update(channel_id=old["channel_id"], channel_name=old.get("channel_name", ""))   # a Reconnect keeps the channel
    _write_meta(m)
    L.event(LOG, "info", "slack_connected", team=m["team_id"], owner_known=bool(who), by=who_started)
    return who_started


def _bot():
    t = _env().get("SLACK_BOT_TOKEN", "")
    if not t: raise ValueError("Slack is not connected. Press Connect Slack.")
    return {"Authorization": "Bearer " + t}


def _call(method, **data):
    st, r = HTTP("POST", API + method, headers=_bot(), data=data)
    if not r.get("ok"):
        err = str(r.get("error") or f"HTTP {st}")
        if err in ("invalid_auth", "token_revoked", "account_inactive", "not_authed"): raise ValueError("Slack no longer accepts the connection (" + err + "). Press Reconnect.")
        raise ValueError("Slack said no: " + err[:80] + ".")
    return r


def channels():
    """The channels the bot can see: public ones, and private ones it was invited to. [{id, name, private, member}]"""
    out, cursor = [], ""
    for _ in range(10):   # 10 pages of 200 is more than one workspace needs here
        r = _call("conversations.list", types="public_channel,private_channel", exclude_archived="true", limit="200", **({"cursor": cursor} if cursor else {}))
        out += [{"id": c["id"], "name": c.get("name", ""), "private": bool(c.get("is_private")), "member": bool(c.get("is_member"))} for c in r.get("channels") or []]
        cursor = ((r.get("response_metadata") or {}).get("next_cursor") or "")
        if not cursor: break
    return sorted(out, key=lambda c: c["name"])


def set_channel(channel_id):
    """Use this channel. The bot must be a member; a hello is posted there so the owner sees it works."""
    cid = str(channel_id or "").strip()
    if not re.fullmatch(r"[CG][A-Z0-9]{6,20}", cid): raise ValueError("Pick a channel from the list.")
    info = _call("conversations.info", channel=cid).get("channel") or {}
    if not info.get("is_member"): raise ValueError(f"The NAVAAN bot is not in #{info.get('name', 'that channel')} yet. In Slack, open the channel and type /invite @ followed by the bot's name, then pick it again.")
    _call("chat.postMessage", channel=cid, text="NAVAAN Studio is connected to this channel. Approvals, status and new work will happen here.")
    m = _meta(); m.update(channel_id=cid, channel_name=info.get("name", "")); _write_meta(m)
    return status()


def set_owner(member_id):
    """The Slack member id of the person who may approve and start things, when Slack did not say who connected."""
    v = str(member_id or "").strip()
    if not re.fullmatch(r"[UW][A-Z0-9]{6,20}", v): raise ValueError("A Slack member id looks like U01ABCD2EFG (Slack: your profile, the three dots, Copy member ID).")
    m = _meta()
    if not m.get("team_id"): raise ValueError("Connect Slack first.")
    m["owner_user_id"] = v; _write_meta(m)
    return status()


def disconnect():
    """Revoke the bot token at Slack and forget it and the connection here. The app's own keys stay, so Connect works again."""
    e = _env(); t = e.pop("SLACK_BOT_TOKEN", "")
    if t:
        st, r = HTTP("POST", API + "auth.revoke", headers={"Authorization": "Bearer " + t}, data={})
        if not r.get("ok") and r.get("error") not in ("invalid_auth", "token_revoked", "not_authed"): L.event(LOG, "warning", "slack_revoke_failed", error=str(r.get("error") or st)[:80])
    _write_env(e); _write_meta({})
    return status()


_CHECK = {"at": 0.0, "problem": ""}


def status(check=False):
    """For Settings: what is saved and connected, never a secret. check=True asks Slack whether the token still works (auth.test), at most once a minute."""
    e, m = _env(), _meta()
    out = {"setup": setup(), "app_saved": bool(e.get("SLACK_CLIENT_ID") and e.get("SLACK_CLIENT_SECRET") and e.get("SLACK_SIGNING_SECRET")), "app_token": bool(e.get("SLACK_APP_TOKEN")),
           "connected": bool(e.get("SLACK_BOT_TOKEN")), "team": m.get("team_name", ""), "owner_user_id": m.get("owner_user_id", ""), "channel": m.get("channel_name", ""), "channel_id": m.get("channel_id", ""),
           "connected_at": m.get("connected_at", ""), "problem": ""}
    if out["connected"] and check and time.time() - _CHECK["at"] > 60:
        try: _call("auth.test"); _CHECK.update(problem="")
        except ValueError as x: _CHECK.update(problem=str(x))   # expected: shown on Settings as the problem, in words
        _CHECK["at"] = time.time()
    if out["connected"]: out["problem"] = _CHECK["problem"]
    return out
