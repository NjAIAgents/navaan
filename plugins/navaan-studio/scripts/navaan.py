#!/usr/bin/env python3
"""navaan.py  workflow orchestrator and local web UI for NAVAAN Studio. Standard library only.

  navaan.py init                      create navaan.config.json (artist profile) interactively
  navaan.py new <slug>                create <local_dir>/songs/<slug>
  navaan.py status [slug]             show every song, or the steps of one song
  navaan.py next <slug>               print the next action
  navaan.py start <slug> [idea words]  create the song, then run the whole pipeline end to end, waiting at each gate
  navaan.py import <suno-url-or-id> [slug]  bring in a song already made on Suno (title, lyrics, style, audio, cover), then run the pipeline from there
  navaan.py pipeline <slug> [--wait] [--poll 10] [--until STEP] [--timeout SEC]   run every step in order; stop at a gate, or with --wait keep waiting until you approve
  navaan.py run <slug> [--step ID] [--dry]   run only the next ready step (retries, logs, state)
  navaan.py redo <slug> <step> [--run]  redo a finished step: its files go to _prev/ (nothing deleted), its gates are revoked, then it runs again with --run
  navaan.py approve <slug> <gate>     record a human approval (asks you to type yes)
  navaan.py revoke <slug> <gate>
  navaan.py serve [--port 8765]       local web UI on 127.0.0.1: create, review, approve, run

Steps: lyrics, suno (or suno_import for an imported song), visuals, captions (only when captions.enabled is true, off by default), video, publish_youtube, archive, publish_instagram.
Gates (human only): lyrics, listen, credits, captions_setup, media, publish_youtube, publish_instagram, cloud_upload. Approvals live in <local_dir>/songs/<slug>/meta.json.
Songs live in storage.local_dir from navaan.config.json (outside the plugin and its repository). After a song is final, the archive step uploads it to your cloud bucket.
Claude steps run `claude -p` with an allowlist of tools, because headless runs cannot answer permission prompts (override the command with NAVAAN_CLAUDE_CMD, the flags with NAVAAN_CLAUDE_FLAGS). Browser steps (Suno, Flow) need Claude in Chrome enabled; set
NAVAAN_CLAUDE_BROWSER_FLAG=--chrome if your Claude Code needs the flag. Scripts steps run the tools in this folder.
"""
import os, sys, json, time, glob, shlex, subprocess, datetime, threading, secrets, mimetypes, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import setup_captions
from navaan_common import find_root, song_dir, load_json, cfg, GATES, songs_root

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
now = lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def files(D, pat): return sorted(glob.glob(os.path.join(D, pat)))
def has(D, *names): return all(os.path.exists(os.path.join(D, n)) for n in names)
def yt_done(m): return bool(m.get("published", {}).get("youtube_items"))
def ig_done(m): return bool(m.get("published", {}).get("instagram"))
def fresh(D, outs, src):
    """True when every file in outs exists and is newer than the newest source file, so a new clip makes the videos stale."""
    ss = [os.path.getmtime(p) for pat in src for p in glob.glob(os.path.join(D, pat))]
    return all(os.path.exists(os.path.join(D, o)) and (not ss or os.path.getmtime(os.path.join(D, o)) >= max(ss)) for o in outs)
def sc(name, *args): return [PY, os.path.join(HERE, name), *args]


def steps(slug, D):
    reel_meta = ["--meta", "tags.json"]
    imported = load_json(os.path.join(D, "meta.json"), default={}).get("source") == "suno_import"
    head = [
        dict(id="suno_import", outputs=['final.mp3', 'lyrics.txt', 'style.txt', 'title.txt', 'takes/imported.*'], label="Import the song from Suno", kind="claude", skill="suno-import", chrome=True, state="draft",
             done=lambda m: has(D, "lyrics.txt", "style.txt", "title.txt", "final.mp3"), after="listen", sets="accepted"),
    ] if imported else [
        dict(id="lyrics", outputs=['lyrics.txt', 'style.txt', 'title.txt'], label="Write lyrics and style", kind="claude", skill="lyrics", chrome=False, state="draft",
             done=lambda m: has(D, "lyrics.txt", "style.txt", "title.txt"), after="lyrics", sets="lyrics_ok"),
        dict(id="suno", outputs=['final.mp3'], label="Generate the song on Suno", kind="claude", skill="suno-generate", chrome=True, before="credits", state="lyrics_ok",
             done=lambda m: has(D, "final.mp3"), after="listen", sets="accepted"),
    ]
    CAP = bool(cfg("captions.enabled", False))  # lyric captions over the video are off unless the profile turns them on
    cap_steps = [
        dict(id="captions", outputs=['caption_cues.json', 'reel_start.json', '.cache'], label="Measure lyric timing", kind="script", before=(None if setup_captions.ready() else "captions_setup"),
             cmds=([sc("setup_captions.py", "--yes")] if not setup_captions.ready() else []) + [sc("captions_run.py", slug)],
             done=lambda m: has(D, "caption_cues.json", "reel_start.json")),
    ] if CAP else []
    REELS = bool(cfg("video.make_reel", False))  # YouTube makes Shorts from the full video in its editor, so a separate vertical reel is optional
    FULL = "final_16x9_cap.mp4" if CAP else "final_16x9.mp4"
    REEL = "final_reel_cap.mp4" if CAP else "final_reel_sync.mp4"
    return head + [
        dict(id="visuals", outputs=['clips/*.mp4', 'cover_1x1.png', 'cover_16x9.png', 'cover_flow.jpg', 'thumb_16x9.jpg', 'scenes/*.txt'], label="Cover art and Flow clips", kind="claude", skill="flow-visuals", chrome=True, before="credits",
             done=lambda m: len(files(D, "clips/*.mp4")) > 0 and has(D, "cover_1x1.png")),
        *cap_steps,
        dict(id="video", outputs=['final_16x9*.mp4', 'final_reel*.mp4', 'final_tagged.mp3'], label=("Render videos, captions, tags" if CAP else ("Render videos and tags" if REELS else "Render the video and tags")), kind="script", sets_after="media_ready",
             cmds=[sc("clipvideo.py", slug, "16x9")] + ([sc("clipvideo.py", slug, "reel")] if REELS else []) + ([sc("caption_clips.py", slug, "16x9")] + ([sc("caption_clips.py", slug, "reel")] if REELS else []) if CAP else []) + [sc("tag_mp3.py", slug)],
             done=lambda m: fresh(D, [FULL] + ([REEL] if REELS else []) + ["final_tagged.mp3"], ["clips/*.mp4"]), after="media", sets="approved"),
        dict(id="publish_youtube", outputs=[], redo=False, label="Upload to YouTube (API)", kind="script", before="publish_youtube",
             cmds=[sc("publish_youtube.py", "upload", slug, "--file", FULL, "--privacy", os.environ.get("NAVAAN_YT_PRIVACY", "private"), "--yes")],
             done=lambda m: yt_done(m), sets_after="published"),
        dict(id="archive", outputs=[], redo=False, label="Archive the finished song to cloud storage", kind="script", before="cloud_upload", optional_cloud=True,
             cmds=[sc("upload_cloud.py", slug, "--yes")], done=lambda m: bool(m.get("cloud", {}).get("uploaded_at"))),
        dict(id="publish_instagram", outputs=[], redo=False, label="Publish Reel to Instagram (API)", kind="script", before="publish_instagram", optional=True,
             cmds=None, done=lambda m: ig_done(m)),
    ]


def meta(slug): return load_json(os.path.join(song_dir(slug), "meta.json"), default={})


def save_meta(slug, m):
    p = os.path.join(song_dir(slug), "meta.json")
    json.dump(m, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False); open(p, "a").write("\n")


def log_hist(m, text): m.setdefault("history", []).append(f"{now()} {text}")


def plan(slug):
    """Walk the steps in order and return (rows, next_action). Everything is derived from files plus approvals."""
    D = song_dir(slug); m = meta(slug); ap = m.get("approvals", {}); rows = []; nxt = None
    legacy = m.get("state") == "published" and any(a.get("via") == "legacy backfill" for a in ap.values())  # songs finished before navaan-studio
    for s in steps(slug, D):
        if s.get("optional") and not (cfg("publish.instagram_handle") or os.environ.get("NAVAAN_WITH_INSTAGRAM")):
            continue
        if s.get("optional_cloud") and cfg("storage.cloud_provider", "none") in ("none", None, ""):
            continue
        d = s["done"](m) or (legacy and s["id"] != "archive")
        row = {"id": s["id"], "label": s["label"], "kind": s["kind"], "done": d, "redo": s.get("redo", True), "spends": s.get("before") == "credits", "gate_before": s.get("before"), "gate_after": s.get("after")}
        gb, ga = s.get("before"), s.get("after")
        if d:
            row["status"] = "waiting for approval" if (ga and not ap.get(ga)) else "done"
            row["needs_gate"] = ga if (ga and not ap.get(ga)) else None
        else:
            row["needs_gate"] = gb if (gb and not ap.get(gb)) else None
            row["status"] = "waiting for approval" if row["needs_gate"] else ("blocked" if (nxt and nxt["type"] == "gate") else "ready")
        rows.append(row)
        if nxt is None:
            if row["needs_gate"]: nxt = {"type": "gate", "step": s["id"], "gate": row["needs_gate"]}
            elif not d: nxt = {"type": "run", "step": s["id"]}
    return rows, (nxt or {"type": "done"})


def run_cmd(cmd, logf):
    logf.write(f"\n$ {' '.join(shlex.quote(c) for c in cmd)}\n"); logf.flush()
    return subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT, cwd=find_root()).returncode


DEFAULT_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash(python3:*)", "Bash(python:*)", "Bash(ffmpeg:*)", "Bash(ffprobe:*)",
                 "Bash(ls:*)", "Bash(sleep:*)", "Bash(cat:*)", "Bash(mkdir:*)", "Bash(cp:*)", "Bash(mv:*)", "Bash(open:*)"]
CHROME_TOOLS = ["mcp__claude-in-chrome__*"]


def claude_cmd(slug, s):
    """Headless `claude -p` cannot answer permission prompts, so list exactly the tools a step may use. Publishing, deleting and
    credit spending are not on the list; the gates in meta.json stay the real control. NAVAAN_CLAUDE_FLAGS replaces the flags."""
    D = song_dir(slug)
    base = shlex.split(os.environ.get("NAVAAN_CLAUDE_CMD", "claude -p"))
    chrome = bool(s.get("chrome"))
    prompt = (f"Use the {s['skill']} skill for song {slug} in this project. Follow the navaan-studio AGENTS.md. Do only this step, update {D}/meta.json history, "
              f"then stop. Approvals recorded in meta.json are the only permission you have: do not publish, delete or spend credits beyond them. "
              + ("Use Claude in Chrome (the mcp__claude-in-chrome tools), not Playwright. " if chrome else "")
              + "Ask for a human at any login, CAPTCHA or file picker.")
    if "NAVAAN_CLAUDE_FLAGS" in os.environ:
        flags = shlex.split(os.environ["NAVAAN_CLAUDE_FLAGS"])
    else:
        tools = DEFAULT_TOOLS + (CHROME_TOOLS if chrome else [])
        flags = ["--permission-mode", "acceptEdits", "--allowedTools", ",".join(tools), "--add-dir", D]
        dl = os.path.expanduser("~/Downloads")
        if chrome and os.path.isdir(dl): flags += ["--add-dir", dl]
        if chrome: flags += ["--chrome"]
    if chrome and "NAVAAN_CLAUDE_BROWSER_FLAG" in os.environ: flags += shlex.split(os.environ["NAVAAN_CLAUDE_BROWSER_FLAG"])
    return base + [prompt] + flags


def run(slug, step=None, dry=False, retries=2):
    D = song_dir(slug); rows, nxt = plan(slug)
    if nxt["type"] == "done": print("all steps done"); return 0
    if nxt["type"] == "gate": print(f"waiting for your approval: gate '{nxt['gate']}' (step {nxt['step']}). Run: navaan.py approve {slug} {nxt['gate']}"); return 3
    sid = step or nxt["step"]; s = next((x for x in steps(slug, D) if x["id"] == sid), None)
    if not s: print(f"no such step: {sid}"); return 2
    bg = s.get("before")
    if bg and bg not in meta(slug).get("approvals", {}):
        print(f"waiting for your approval: gate '{bg}' (step {sid}). Run: navaan.py approve {slug} {bg}"); return 3
    if s["id"] == "publish_instagram" and not s.get("cmds"):
        bucket = cfg("storage.cloud_bucket") if cfg("storage.cloud_provider") == "oci" else None
        if not bucket: print("Instagram needs a public video URL. Use an OCI bucket in the profile (storage.cloud_provider oci), or run publish_instagram.py yourself with --video-url."); return 4
        rf = "final_reel_cap.mp4" if cfg("captions.enabled", False) else "final_reel_sync.mp4"
        if not os.path.exists(os.path.join(D, rf)): print(f"Instagram needs a vertical reel and {rf} does not exist. Set video.make_reel to true in the profile and redo the video step, or make the reel another way."); return 4
        cap = os.path.join(D, "publish"); os.makedirs(cap, exist_ok=True)
        s["cmds"] = [["bash", "-c", f'U=$(NAVAAN_BUCKET={shlex.quote(bucket)} bash {shlex.quote(os.path.join(HERE, "oci_public_url.sh"))} {shlex.quote(os.path.join(D, "final_reel_cap.mp4" if cfg("captions.enabled", False) else "final_reel_sync.mp4"))}) && '
                      f'{shlex.quote(PY)} {shlex.quote(os.path.join(HERE, "publish_instagram.py"))} publish {shlex.quote(slug)} --video-url "$U" --caption-file instagram.txt --yes']]
    cmds = [claude_cmd(slug, s)] if s["kind"] == "claude" else s["cmds"]
    if dry:
        for c in cmds: print(" ".join(shlex.quote(x) for x in c))
        return 0
    os.makedirs(os.path.join(D, "logs"), exist_ok=True)
    lp = os.path.join(D, "logs", f"{sid}.log")
    for attempt in range(1, retries + 2):
        RUN[slug] = {"step": sid, "attempt": attempt, "attempts": retries + 1, "started": time.time(), "failed": None}
        with open(lp, "a", encoding="utf-8") as lf:
            lf.write(f"\n=== {now()} {sid} attempt {attempt} ===\n")
            ok = all(run_cmd(c, lf) == 0 for c in cmds)
        m = meta(slug)
        if ok and s["done"](m):
            if s.get("sets_after"): m["state"] = s["sets_after"]
            log_hist(m, f"step {sid} done (attempt {attempt})"); save_meta(slug, m); RUN.pop(slug, None); print("done", sid); return 0
        log_hist(m, f"step {sid} attempt {attempt} did not finish"); save_meta(slug, m)
        if os.path.exists(os.path.join(D, "needs_you.txt")):
            RUN[slug] = {"step": None, "failed": sid, "log": lp}
            print(f"step {sid} is waiting for you: {open(os.path.join(D, 'needs_you.txt'), encoding='utf-8').read().strip()}"); return 5
        if attempt <= retries: time.sleep(5 * attempt)
    RUN[slug] = {"step": None, "failed": sid, "log": lp}
    print(f"step {sid} failed after {retries + 1} attempts. See {lp}"); return 1


RUN = {}  # slug -> {"step", "attempt", "started", "failed"} live progress for the web UI
STATUS = {}  # slug -> short text for the web UI ("running lyrics", "waiting for you: gate lyrics")


def pipeline(slug, wait=False, poll=10, until=None, timeout=None, max_steps=40):
    """Run every step in order. Stops at a gate (or waits for you to approve it when wait=True), on a failed step, or when done.
    Approvals are only ever read here, never written."""
    t0 = time.time(); steps_run = 0
    while steps_run < max_steps:
        rows, nxt = plan(slug)
        if until and any(r["id"] == until and r["status"] == "done" for r in rows):
            STATUS[slug] = f"stopped after {until}"; print(STATUS[slug]); return 0
        if nxt["type"] == "done":
            STATUS[slug] = "all steps done"; print("all steps done"); return 0
        if nxt["type"] == "gate":
            g = nxt["gate"]; STATUS[slug] = f"waiting for you: approve gate {g}"
            print(f"waiting for your approval: gate '{g}' (before or after step {nxt['step']}). Approve in the web UI or run: navaan.py approve {slug} {g}", flush=True)
            if not wait: return 3
            while not meta(slug).get("approvals", {}).get(g):
                if timeout and time.time() - t0 > timeout: print("timed out waiting for approval"); return 3
                time.sleep(poll)
            print(f"gate {g} approved, continuing", flush=True); continue
        STATUS[slug] = f"running {nxt['step']}"; print(f"running {nxt['step']} ...", flush=True)
        rc = run(slug, step=nxt["step"]); steps_run += 1
        if rc != 0:
            STATUS[slug] = f"step {nxt['step']} is waiting for you, see the banner" if rc == 5 else f"step {nxt['step']} failed, see logs"; return rc
    print("stopped: too many steps in one run"); return 1


def start(slug, idea=""):
    """Create the song (if new), write the brief, then run the whole pipeline and wait at each gate."""
    root = songs_root()
    if not os.path.isdir(os.path.join(root, slug)):
        rc = subprocess.call([PY, os.path.join(HERE, "new_song.py"), slug])
        if rc: return rc
    D = song_dir(slug)
    if idea:
        bp = os.path.join(D, "brief.md")
        old = open(bp, encoding="utf-8").read() if os.path.exists(bp) else ""
        open(bp, "w", encoding="utf-8").write(old.rstrip() + f"\n\n## Idea\n\n{idea}\n")
    return pipeline(slug, wait=True)


def import_suno(src, slug=None):
    """Import an existing Suno song, then run the pipeline and wait at each gate. Importing spends no credits."""
    import suno_import
    slug = suno_import.init(src, slug)
    return pipeline(slug, wait=True)


def redo(slug, sid):
    """Redo a finished step. Its output files are moved to <song>/_prev/<time>/ (nothing is deleted) and the gates around it are
    revoked, so a step that spends credits needs a fresh approval. Publishing and archiving steps cannot be redone this way."""
    import shutil
    D = song_dir(slug); st = next((x for x in steps(slug, D) if x["id"] == sid), None)
    if not st: sys.exit(f"navaan: no such step for this song: {sid}")
    if st.get("redo", True) is False: sys.exit(f"navaan: {sid} touches an outside service and cannot be redone from here. Delete or re-upload there on purpose.")
    dest = os.path.join(D, "_prev", now().replace(":", "")); moved = 0
    for pat in st.get("outputs", []):
        for src in glob.glob(os.path.join(D, pat)):
            rel = os.path.relpath(src, D); tgt = os.path.join(dest, rel); os.makedirs(os.path.dirname(tgt), exist_ok=True)
            shutil.move(src, tgt); moved += 1
    m = meta(slug); ap = m.setdefault("approvals", {})
    # Only this step is redone. Later steps and their approvals stay as they are; only a credit gate is asked again.
    if st.get("before") == "credits":
        ap.pop("credits", None); m["redo_pending"] = sid  # the UI starts this step as soon as credits are approved again
    if m.get("state") in ("accepted", "media_ready", "approved") and sid in ("suno", "suno_import", "lyrics"): m["state"] = "draft"
    log_hist(m, f"step {sid} redo: {moved} file(s) moved to _prev/{os.path.basename(dest)}"); save_meta(slug, m)
    RUN.pop(slug, None); st["_dest"] = dest
    for nm in ("needs_you.txt",):
        pth = os.path.join(D, nm)
        if os.path.exists(pth): os.remove(pth)
    print(f"redo {sid}: {moved} file(s) moved to {dest if moved else '(nothing to move)'}")
    return dest if moved else None


def restore(slug, dest):
    """Put the files from a _prev folder back where they were."""
    import shutil
    D = song_dir(slug)
    for root, _, fs in os.walk(dest):
        for f in fs:
            src = os.path.join(root, f); tgt = os.path.join(D, os.path.relpath(src, dest))
            os.makedirs(os.path.dirname(tgt), exist_ok=True); shutil.move(src, tgt)


def redo_run(slug, sid):
    """Redo one step and run only it. Every other step keeps its files and approvals, so the new output simply replaces the old one.
    If the new run fails, the old files are put back."""
    st = next((x for x in steps(slug, song_dir(slug)) if x["id"] == sid), {})
    dest = redo(slug, sid)
    if st.get("before") == "credits":
        print(f"redo {sid}: spends credits. Approve the credits gate, then run this step."); return 0
    rc = run(slug, step=sid)
    row = next((r for r in plan(slug)[0] if r["id"] == sid), {})
    if rc != 0 or row.get("status") != "done":
        if dest and os.path.isdir(dest):
            restore(slug, dest); __import__('shutil').rmtree(dest, ignore_errors=True); print(f"redo {sid}: failed, previous files put back")
        return rc or 1
    return 0


def set_gate(slug, gate, on, via):
    if gate not in GATES: sys.exit(f"unknown gate: {gate}. Gates: {', '.join(GATES)}")
    m = meta(slug); ap = m.setdefault("approvals", {})
    if on: ap[gate] = {"at": now(), "via": via}
    else: ap.pop(gate, None)
    D = song_dir(slug)
    for s in steps(slug, D):
        if on and s.get("after") == gate and s.get("sets"): m["state"] = s["sets"]
    log_hist(m, f"gate {gate} {'approved' if on else 'revoked'} via {via}"); save_meta(slug, m)


def status(slug=None):
    for sl in ([slug] if slug else sorted(os.path.basename(p) for p in glob.glob(f"{songs_root()}/*") if os.path.isdir(p) and not os.path.basename(p).startswith("_"))):
        rows, nxt = plan(sl); m = meta(sl)
        print(f"{sl}  state={m.get('state','?')}  next={nxt.get('step') or 'done'}{' (needs your approval: ' + nxt['gate'] + ')' if nxt['type'] == 'gate' else ''}")
        if slug:
            for r in rows: print(f"   {'x' if r['status']=='done' else ' '} {r['id']:18} {r['status']}")


def main(argv):
    if not argv: print(__doc__); return 0
    c, a = argv[0], argv[1:]
    if c == "init": return subprocess.call([PY, os.path.join(HERE, "setup_profile.py")] + a)
    if c == "new": return subprocess.call([PY, os.path.join(HERE, "new_song.py"), a[0]])
    if c == "start": return start(a[0], " ".join(a[1:]))
    if c == "import":
        if not a: sys.exit("usage: navaan.py import <suno-url-or-id> [slug]")
        return import_suno(a[0], a[1] if len(a) > 1 else None)
    if c == "pipeline":
        def opt(n, d=None): return a[a.index(n) + 1] if n in a else d
        return pipeline(a[0], wait="--wait" in a, poll=int(opt("--poll", 10)), until=opt("--until"), timeout=int(opt("--timeout", 0)) or None)
    if c == "status": status(a[0] if a else None); return 0
    if c == "next":
        _, n = plan(a[0]); print(json.dumps(n)); return 0
    if c == "redo":
        if len(a) < 2: sys.exit("usage: navaan.py redo <slug> <step> [--run]")
        if "--run" in a: return redo_run(a[0], a[1])
        redo(a[0], a[1]); return 0
    if c == "run":
        return run(a[0], step=(a[a.index("--step") + 1] if "--step" in a else None), dry="--dry" in a)
    if c in ("approve", "revoke"):
        slug, gate = a[0], a[1]
        if c == "approve":
            if not sys.stdin.isatty(): sys.exit("approve needs a terminal. An agent must never approve a gate for you. Use this command yourself or the web UI.")
            if input(f"Approve gate '{gate}' for {slug}? Type yes: ").strip().lower() != "yes": print("not approved"); return 1
        set_gate(slug, gate, c == "approve", "cli"); print(c + "d", gate); return 0
    if c == "serve":
        import navaan_ui; return navaan_ui.serve(int(a[a.index("--port") + 1]) if "--port" in a else 8765)
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
