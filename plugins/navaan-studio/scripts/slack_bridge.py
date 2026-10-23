"""Author: Navjyot Nishant
Created: 2026-10-23
Last updated: 2026-10-23
Description: the Slack side of NAVAAN Studio, run as its own service (compose.yml `slack`, `navaan.py slack`), so a Slack failure never stalls a pipeline (epic NAV-153).

  NAV-154  outbox      every 20 s it looks at the items and posts what is new once: an approval waiting, a failed run, a QA verdict, a needs-attention alert.
                       What was sent is kept in slack_sent.json (state dir), so a restart or a retry never posts twice; a post that fails is tried again later.
  NAV-155  approvals   the media, quote and originality approvals carry an Approve button (media shows the QA verdict); the rest say "Open in Studio".
  NAV-156  /navaan status [item]
  NAV-157  /navaan new <inspiration|aha|blog> <idea>   asks Start/Cancel first, then makes the item the way the Studio form does and starts its run.
  NAV-158  a message in the channel is read by Claude and mapped onto the same actions, each confirmed with a button before anything happens.

Slack reaches us over Socket Mode (slack_ws.py): the studio hosts sit behind a password gate, so Slack cannot call in. Every envelope is acknowledged at once (Slack wants it within 3 s)
and handled in a thread. Everyone in the channel may read; only the Slack user who connected (slack.json owner_user_id) may approve or start anything. Every action goes through the
functions Studio uses (navaan.set_gate, new_song.create, the job queue), and the item's history says "via slack:<member id>".
"""
import os, sys, re, json, time, threading, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_log as L
import slack_cfg as S
LOG = L.get("slack")

TICK = 20                      # seconds between two looks at the items
BACKOFF = 300                  # after Slack refused a post, wait this long before the next pass
ALIVE_FILE = os.environ.get("NAVAAN_SLACK_ALIVE_FILE", "/tmp/navaan-slack.alive")
BUTTON_GATES = ("media", "quote", "originality")      # approvable from Slack; the rest (credits, publishing, deleting) stay in Studio until the owner decides otherwise
NEW_TYPES = ("inspiration", "aha", "blog")
PATHS = {"music": "songs", "inspiration": "inspiration", "aha": "aha", "reel": "reels", "blog": "blog"}
GATE_NAMES = {"media": "the video", "quote": "the quote", "originality": "the originality check", "credits": "the spend", "lyrics": "the lyrics", "topic": "the topic",
              "shots": "the shot list", "edit_plan": "the edit plan", "instagram_caption": "the Instagram caption", "publish_youtube": "publishing to YouTube",
              "publish_short": "publishing the Short", "publish_instagram": "posting to Instagram", "go_public": "going public", "local_cleanup": "deleting local media"}
SECRETISH = re.compile(r"(xox[abp]-|xapp-|sk-ant-|sk-|Bearer\s)[A-Za-z0-9._-]+")


def scrub(t, n=300): return SECRETISH.sub(lambda m: m.group(1) + "…", " ".join(str(t or "").split()))[:n]


def state_path(): return os.path.join(os.environ.get("NAVAAN_STATE_DIR") or os.path.expanduser("~/.local/share/navaan"), "slack_sent.json")


def load_sent():
    try:
        with open(state_path(), encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return None   # expected: the first start; everything already there counts as seen
    except (OSError, ValueError): L.exc(LOG, "slack_sent_unreadable"); return {}


def save_sent(d):
    cut = time.time() - 30 * 86400; d = {k: v for k, v in d.items() if v > cut}
    os.makedirs(os.path.dirname(state_path()), exist_ok=True)
    tmp = state_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(d, f)
    os.replace(tmp, state_path())


def link(m, slug):
    host = os.environ.get("NAVAAN_STUDIO_HOST", "").strip()
    import navaan_common as C
    p = PATHS.get(C.item_type(m))
    return f"https://{host}/app/studio/{p}/{slug}" if host and p else ""


def items():
    import navaan_common as C, glob
    return sorted(os.path.basename(p) for p in glob.glob(f"{C.songs_root()}/*") if os.path.isdir(p) and not os.path.basename(p).startswith("_"))


def qa_of(slug):
    import navaan_common as C
    p = os.path.join(C.song_dir(slug), "qa.json")
    try: return C.load_json(p, default=None), int(os.path.getmtime(p))
    except OSError: return None, 0   # expected: no QA yet


# ---- NAV-154: what happened, as events with a key that is the same however often it is seen ------------------------------------------------------
def events():
    import navaan as N, navaan_common as C, jobs as J
    out = []
    for sl in items():
        try:
            m = N.meta(sl)
            if m.get("state") == "published": continue
            _, nxt = N.plan(sl); title = m.get("title") or sl
            qa, qa_at = qa_of(sl)
            if nxt.get("type") == "gate":
                g = nxt["gate"]; sig = N.gate_sha(C.song_dir(sl), g) if g in N.SHA_FILES else ""
                out.append({"key": f"gate:{sl}:{g}:{sig or ''}:{qa_at if g == 'media' else ''}", "kind": "gate", "slug": sl, "gate": g, "title": title, "link": link(m, sl),
                            "qa": qa if g == "media" else None})
            elif qa and qa.get("verdict") and not (m.get("approvals") or {}).get("media"):   # a verdict before the video is approved (a fix that stopped the run); at the approval it rides along
                out.append({"key": f"qa:{sl}:{qa_at}", "kind": "qa", "slug": sl, "title": title, "link": link(m, sl), "qa": qa})
            v = J.view(sl)
            if v.get("status") == "failed":
                out.append({"key": f"fail:{v['id']}", "kind": "fail", "slug": sl, "title": title, "link": link(m, sl), "error": v.get("error") or v.get("status_text") or ""})
        except Exception: L.exc(LOG, "slack_event_read_failed", item=sl)   # one unreadable item never stops the others
    try:
        import settings_api
        for a in settings_api.alerts(): out.append({"key": f"alert:{a['id']}:{time.strftime('%Y-%m-%d')}", "kind": "alert", "title": a.get("title", ""), "message": a.get("message", "")})
    except Exception: L.exc(LOG, "slack_alerts_failed")
    return out


def qa_line(qa):
    if not qa: return ""
    v = "passed" if qa.get("verdict") == "pass" else "asks for fixes"
    fixes = "".join(f"\n• {scrub(x, 200)}" for x in (qa.get("fixes") or [])[:5]) if qa.get("verdict") != "pass" else ""
    return f"\nQA {v}: {scrub(qa.get('summary') or qa.get('notify'), 400)}{fixes}"


def open_button(url): return {"type": "button", "text": {"type": "plain_text", "text": "Open in Studio"}, "url": url} if url else None


def message(e):
    """(text, blocks) for one event."""
    if e["kind"] == "alert": t = f":warning: {scrub(e['title'], 150)}. {scrub(e['message'], 400)}"; return t, None
    name = f"*{scrub(e['title'], 120)}* ({e['slug']})"
    if e["kind"] == "fail": t = f":x: {name}: the run stopped. {scrub(e['error'])}"
    elif e["kind"] == "qa": t = f":mag: {name}{qa_line(e['qa'])}"
    else:
        g = e["gate"]; t = f":raised_hand: {name} is waiting for your approval of {GATE_NAMES.get(g, g.replace('_', ' '))}.{qa_line(e.get('qa'))}"
        if g not in BUTTON_GATES: t += "\nThis one is approved in Studio."
    acts = [b for b in [open_button(e.get("link"))] if b]
    if e["kind"] == "gate" and e["gate"] in BUTTON_GATES:
        acts.insert(0, {"type": "button", "style": "primary", "text": {"type": "plain_text", "text": "Approve"}, "action_id": "approve", "value": json.dumps({"slug": e["slug"], "gate": e["gate"]})})
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": t}}] + ([{"type": "actions", "elements": acts}] if acts else [])
    return t, blocks


def post(text, blocks=None, channel=None):
    ch = channel or S._meta().get("channel_id")
    if not ch: raise ValueError("No Slack channel is chosen. Settings, Accounts, Slack.")
    return S._call("chat.postMessage", channel=ch, text=text, **({"blocks": json.dumps(blocks)} if blocks else {}))


def outbox_pass(sent, poster=post):
    """Post every event not yet sent. Returns (sent, how many posted). A post that fails stops the pass; the event stays unsent and is tried next time."""
    first = sent is None; sent = sent or {}; n = 0
    evs = events()
    if first:   # the first start: what is already waiting counts as seen, so connecting never floods the channel
        for e in evs: sent[e["key"]] = time.time()
        waiting = sum(1 for e in evs if e["kind"] == "gate")
        poster(f"NAVAAN Studio is listening here. {waiting} item{'s' if waiting != 1 else ''} waiting for you now; type /navaan status to see them.")
        return sent, 1
    for e in evs:
        if e["key"] in sent: continue
        t, b = message(e); poster(t, b); sent[e["key"]] = time.time(); n += 1
    return sent, n


# ---- who may act -------------------------------------------------------------------------------------------------------------------------------------
def owner(): return S._meta().get("owner_user_id", "")


def may_act(user): return bool(user) and user == owner()


def ephemeral(channel, user, text):
    try: S._call("chat.postEphemeral", channel=channel, user=user, text=text)
    except ValueError: L.exc(LOG, "slack_ephemeral_failed")


def respond(url, text, in_channel=True, blocks=None, replace=False):
    """Answer a slash command or a button press through its response_url (good for 30 minutes)."""
    body = {"response_type": "in_channel" if in_channel else "ephemeral", "text": text, **({"blocks": blocks} if blocks else {}), **({"replace_original": True} if replace else {})}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json"})
    if not url.startswith("https://hooks.slack.com/"): raise ValueError("not a Slack response address")
    try:
        with urllib.request.urlopen(req, timeout=15) as r: r.read()
    except (urllib.error.URLError, OSError): L.exc(LOG, "slack_respond_failed")


# ---- NAV-156: status ---------------------------------------------------------------------------------------------------------------------------------
def status_text(slug=""):
    import navaan as N, jobs as J
    if slug:
        if slug not in items(): return f"No item called {slug}."
        m = N.meta(slug); rows, nxt = N.plan(slug); v = J.view(slug)
        head = f"*{scrub(m.get('title') or slug, 120)}* ({slug}), {m.get('state', '?')}: " + ("running " + (v.get("status_text") or "") if v.get("running") else
                ("waiting for your approval of " + GATE_NAMES.get(nxt["gate"], nxt["gate"]) if nxt.get("type") == "gate" else ("stopped: " + scrub(v.get("error")) if v.get("status") == "failed" else "next: " + (nxt.get("step") or "done"))))
        steps = "\n".join(f"{'✓' if r['status'] == 'done' else '·'} {r['label']}  _{r['status']}_" for r in rows)
        url = link(m, slug)
        return head + "\n" + steps + (f"\n<{url}|Open in Studio>" if url else "")
    lines = []
    for sl in items():
        try:
            m = N.meta(sl)
            if m.get("state") == "published": continue
            _, nxt = N.plan(sl); v = J.view(sl)
            what = ("running" if v.get("running") else "waiting for you: " + GATE_NAMES.get(nxt["gate"], nxt["gate"]) if nxt.get("type") == "gate" else
                    "stopped" if v.get("status") == "failed" else "next: " + (nxt.get("step") or "done"))
            lines.append(f"• *{sl}* {scrub(m.get('title') or '', 60)}: {what}")
        except Exception: L.exc(LOG, "slack_status_item_failed", item=sl)
    return ("Not published yet:\n" + "\n".join(lines)) if lines else "Nothing in progress: every item is published."


HELP = ("`/navaan status` what is in progress · `/navaan status <item>` one item's steps · `/navaan new <inspiration|aha|blog> <idea>` start a new item.\n"
        "Or just write here, for example \"how is insp-012 doing\" or \"start an aha about why toast lands butter side down\".")


# ---- NAV-157: a new item, after a Start press ----------------------------------------------------------------------------------------------------------
def confirm_new(kind, idea):
    v = json.dumps({"type": kind, "idea": idea[:1500]})
    t = f"Start a new {kind}: “{scrub(idea, 600)}”? It runs to its first approval; anything that spends money still waits for you."
    return t, [{"type": "section", "text": {"type": "mrkdwn", "text": t}},
               {"type": "actions", "elements": [{"type": "button", "style": "primary", "text": {"type": "plain_text", "text": "Start"}, "action_id": "new_start", "value": v},
                                                {"type": "button", "text": {"type": "plain_text", "text": "Cancel"}, "action_id": "cancel", "value": "{}"}]}]


def start_new(kind, idea, user):
    """The Studio form's path: new_song.create, the same narration choices (navaan_ui.short_options), then the run is queued like the Run button. Returns the new slug."""
    import new_song, navaan, navaan_ui
    if kind not in NEW_TYPES: raise ValueError("Use inspiration, aha or blog.")
    idea = " ".join(str(idea or "").split())
    if not idea: raise ValueError("Say what it is about.")
    try: sl = new_song.create(None, kind, idea)
    except SystemExit as e: raise ValueError(str(e.code).replace("navaan: ", ""))
    navaan_ui.short_options(sl, kind, {"narrate": "eleven"} if kind != "blog" else {})
    navaan.edit_meta(sl, lambda m: navaan.log_hist(m, f"created from Slack via slack:{user}"))
    navaan_ui.start_job(sl, True)
    return sl


# ---- NAV-155: a button press ----------------------------------------------------------------------------------------------------------------------------
def on_action(p):
    import navaan as N
    user = (p.get("user") or {}).get("id", ""); url = p.get("response_url", ""); ch = (p.get("channel") or {}).get("id", "")
    for a in p.get("actions") or []:
        aid = a.get("action_id")
        if aid not in ("approve", "new_start", "cancel", "status_item"): continue
        if not may_act(user): ephemeral(ch, user, f"Only <@{owner()}> can do that."); return
        try: v = json.loads(a.get("value") or "{}")
        except ValueError: v = {}   # expected: a button of an old message; treated as empty and refused below
        try:
            if aid == "cancel": respond(url, "Cancelled.", replace=True); return
            if aid == "status_item": respond(url, status_text(v.get("slug", ""))); return
            if aid == "new_start":
                sl = start_new(v.get("type"), v.get("idea"), user)
                respond(url, f":rocket: Started *{sl}* ({v.get('type')}) for <@{user}>. I will post here when it needs you.", replace=True); return
            slug, gate = str(v.get("slug") or ""), str(v.get("gate") or "")
            if gate not in BUTTON_GATES or slug not in items(): raise ValueError("That approval is not possible from Slack.")
            _, nxt = N.plan(slug)
            if nxt.get("type") != "gate" or nxt.get("gate") != gate: respond(url, f"{slug} is no longer waiting for {GATE_NAMES.get(gate, gate)}.", replace=True); return
            N.set_gate(slug, gate, True, f"slack:{user}")
            L.event(LOG, "info", "slack_approved", item=slug, gate=gate, user=user)
            respond(url, f":white_check_mark: {slug}: {GATE_NAMES.get(gate, gate)} approved by <@{user}> via Slack.", replace=True)
        except (ValueError, SystemExit) as e: ephemeral(ch, user, scrub(getattr(e, "code", None) or e, 300))   # expected: said to the person in words


# ---- NAV-156/157: /navaan -------------------------------------------------------------------------------------------------------------------------------
def on_command(p):
    user, url, text = p.get("user_id", ""), p.get("response_url", ""), " ".join(str(p.get("text") or "").split())
    ch = S._meta().get("channel_id")
    if p.get("channel_id") != ch: return respond(url, f"Use /navaan in <#{ch}>.", in_channel=False)
    word, _, rest = text.partition(" ")
    if word in ("", "help"): return respond(url, HELP, in_channel=False)
    if word == "status": return respond(url, status_text(rest.strip()))
    if word == "new":
        if not may_act(user): return respond(url, f"Only <@{owner()}> can start new work.", in_channel=False)
        kind, _, idea = rest.partition(" ")
        if kind not in NEW_TYPES or not idea.strip(): return respond(url, "Usage: /navaan new <inspiration|aha|blog> <idea>", in_channel=False)
        t, b = confirm_new(kind, idea.strip()); return respond(url, t, blocks=b)
    respond(url, "I do not know that one. " + HELP, in_channel=False)


# ---- NAV-158: plain words, read by Claude, mapped onto the same actions ----------------------------------------------------------------------------------
PROMPT = """You turn a message from the owner of a content studio into ONE action. Answer with JSON only, no prose around it:
{"action": "status" | "status_item" | "new" | "approve" | "none", "slug": "...", "type": "inspiration|aha|blog", "idea": "...", "gate": "media|quote|originality", "reply": "one short sentence"}
- status: what is in progress. status_item: one item (slug). new: start an item of that type about that idea. approve: approve that gate of that item (only media, quote, originality).
- none: anything else; put a short helpful answer in reply. Never invent a slug: use only the items below.
Items now (slug: what it waits for):
<items>
"""


def plan_text(text, runner=None):
    import comment_reply, navaan_common as C
    C.load_claude_env()
    lines = []
    for e in events():
        if e["kind"] == "gate": lines.append(f"{e['slug']}: {e['gate']} ({scrub(e['title'], 60)})")
    prompt = PROMPT + "\n".join(lines or ["(none waiting)"]) + "\n</items>\n<message>\n" + text[:1000] + "\n</message>"
    out = (runner or (lambda pr: comment_reply.run_claude(pr, timeout=120)))(prompt)
    m = re.search(r"\{.*\}", out, re.S)
    try: d = json.loads(m.group(0)) if m else {}
    except ValueError: d = {}   # expected: Claude wrote no JSON; treated as "none" below
    return d if d.get("action") in ("status", "status_item", "new", "approve", "none") else {"action": "none", "reply": "I could not tell what to do. " + HELP}


def on_message(ev, runner=None):
    user, ch, text = ev.get("user", ""), ev.get("channel", ""), str(ev.get("text") or "").strip()
    if ch != S._meta().get("channel_id") or ev.get("subtype") or ev.get("bot_id") or not text or ev.get("thread_ts"): return
    if not may_act(user): return   # only the owner talks to the studio; others' messages are left alone
    try: d = plan_text(text, runner)
    except RuntimeError as e: post(f"<@{user}> {scrub(e, 200)}"); return   # expected: Claude missing or slow, said in the channel
    a, slug = d["action"], str(d.get("slug") or "")
    if a == "status": post(status_text()); return
    if a == "status_item": post(status_text(slug)); return
    if a == "new" and d.get("type") in NEW_TYPES and str(d.get("idea") or "").strip():
        t, b = confirm_new(d["type"], str(d["idea"]).strip()); post(t, b); return
    if a == "approve" and d.get("gate") in BUTTON_GATES and slug in items():
        g = d["gate"]; t = f"Approve {GATE_NAMES.get(g, g)} of *{slug}*?"
        post(t, [{"type": "section", "text": {"type": "mrkdwn", "text": t}}, {"type": "actions", "elements": [
            {"type": "button", "style": "primary", "text": {"type": "plain_text", "text": "Approve"}, "action_id": "approve", "value": json.dumps({"slug": slug, "gate": g})},
            {"type": "button", "text": {"type": "plain_text", "text": "Cancel"}, "action_id": "cancel", "value": "{}"}]}]); return
    post(f"<@{user}> {scrub(d.get('reply') or HELP, 500)}")


# ---- the service ------------------------------------------------------------------------------------------------------------------------------------------
def ready():
    st = S.status()
    return st["connected"] and st["app_token"] and st["channel_id"]


def alive():
    try: open(ALIVE_FILE, "w").write(str(time.time()))
    except OSError as e: L.ignored(LOG, "cannot touch the alive file", e)


def outbox_loop(stop):
    sent = load_sent()
    while not stop.is_set():
        alive(); wait = TICK
        if ready():
            try: sent, n = outbox_pass(sent); save_sent(sent)
            except ValueError as e: L.event(LOG, "warning", "slack_post_refused", error=scrub(e, 200)); wait = BACKOFF
            except Exception: L.exc(LOG, "slack_outbox_failed"); wait = BACKOFF
        stop.wait(wait)


def dispatch(env):
    t, p = env.get("type"), env.get("payload") or {}
    try:
        if t == "slash_commands": on_command(p)
        elif t == "interactive" and p.get("type") == "block_actions": on_action(p)
        elif t == "events_api" and (p.get("event") or {}).get("type") == "message": on_message(p["event"])
    except Exception: L.exc(LOG, "slack_dispatch_failed", kind=t)


def socket_url():
    st, r = S.HTTP("POST", S.API + "apps.connections.open", headers={"Authorization": "Bearer " + S._env().get("SLACK_APP_TOKEN", "")}, data={})
    if not r.get("ok"): raise ValueError("Slack would not open the connection: " + str(r.get("error") or st))
    return r["url"]


def socket_loop(stop):
    import slack_ws
    while not stop.is_set():
        if not ready(): stop.wait(30); continue
        try:
            ws = slack_ws.connect(socket_url()); L.event(LOG, "info", "slack_socket_open")
            while not stop.is_set():
                alive(); raw = ws.recv(30)
                if raw is None: break
                if not raw: continue
                env = json.loads(raw)
                if env.get("envelope_id"): ws.send(json.dumps({"envelope_id": env["envelope_id"]}))   # acknowledge first, always within Slack's 3 s
                if env.get("type") == "disconnect": break
                threading.Thread(target=dispatch, args=(env,), daemon=True).start()
            ws.close(); L.event(LOG, "info", "slack_socket_closed")
        except (ValueError, OSError, slack_ws.Closed) as e: L.event(LOG, "warning", "slack_socket_failed", error=scrub(e, 200)); stop.wait(30)


def main(argv=()):
    stop = threading.Event()
    L.event(LOG, "info", "slack_service_started")
    threading.Thread(target=outbox_loop, args=(stop,), name="slack-outbox", daemon=True).start()
    try: socket_loop(stop)
    except KeyboardInterrupt: stop.set()   # expected: Ctrl-C on a terminal ends the service
    return 0
