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
  navaan.py approve <slug> <gate>     record a human approval (asks you to type yes)
  navaan.py revoke <slug> <gate>
  navaan.py serve [--port 8765]       local web UI on 127.0.0.1: create, review, approve, run

Steps: lyrics, suno (or suno_import for an imported song), visuals, captions, video, publish_youtube, archive, publish_instagram.
Gates (human only): lyrics, listen, credits, media, publish_youtube, publish_instagram, cloud_upload. Approvals live in <local_dir>/songs/<slug>/meta.json.
Songs live in storage.local_dir from navaan.config.json (outside the plugin and its repository). After a song is final, the archive step uploads it to your cloud bucket.
Claude steps run `claude -p` (override with NAVAAN_CLAUDE_CMD). Browser steps (Suno, Flow) need Claude in Chrome enabled; set
NAVAAN_CLAUDE_BROWSER_FLAG=--chrome if your Claude Code needs the flag. Scripts steps run the tools in this folder.
"""
import os, sys, json, time, glob, shlex, subprocess, datetime, threading, secrets, mimetypes, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import find_root, song_dir, load_json, cfg, GATES, songs_root

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
now = lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def files(D, pat): return sorted(glob.glob(os.path.join(D, pat)))
def has(D, *names): return all(os.path.exists(os.path.join(D, n)) for n in names)
def yt_done(m): return bool(m.get("published", {}).get("youtube_items"))
def ig_done(m): return bool(m.get("published", {}).get("instagram"))
def sc(name, *args): return [PY, os.path.join(HERE, name), *args]


def steps(slug, D):
    reel_meta = ["--meta", "tags.json"]
    imported = load_json(os.path.join(D, "meta.json"), default={}).get("source") == "suno_import"
    head = [
        dict(id="suno_import", label="Import the song from Suno", kind="claude", skill="suno-import", chrome=True, state="draft",
             done=lambda m: has(D, "lyrics.txt", "style.txt", "title.txt", "final.mp3"), after="listen", sets="accepted"),
    ] if imported else [
        dict(id="lyrics", label="Write lyrics and style", kind="claude", skill="lyrics", chrome=False, state="draft",
             done=lambda m: has(D, "lyrics.txt", "style.txt", "title.txt"), after="lyrics", sets="lyrics_ok"),
        dict(id="suno", label="Generate the song on Suno", kind="claude", skill="suno-generate", chrome=True, before="credits", state="lyrics_ok",
             done=lambda m: has(D, "final.mp3"), after="listen", sets="accepted"),
    ]
    return head + [
        dict(id="visuals", label="Cover art and Flow clips", kind="claude", skill="flow-visuals", chrome=True, before="credits",
             done=lambda m: len(files(D, "clips/*.mp4")) > 0 and has(D, "cover_1x1.png")),
        dict(id="captions", label="Measure lyric timing", kind="claude", skill="caption-sync", chrome=False,
             done=lambda m: has(D, "caption_cues.json", "reel_start.json")),
        dict(id="video", label="Render videos, captions, tags", kind="script", sets_after="media_ready",
             cmds=[sc("clipvideo.py", slug, "16x9"), sc("clipvideo.py", slug, "reel"), sc("caption_clips.py", slug, "16x9"),
                   sc("caption_clips.py", slug, "reel"), sc("tag_mp3.py", slug)],
             done=lambda m: has(D, "final_16x9_cap.mp4", "final_reel_cap.mp4", "final_tagged.mp3"), after="media", sets="approved"),
        dict(id="publish_youtube", label="Upload to YouTube (API)", kind="script", before="publish_youtube",
             cmds=[sc("publish_youtube.py", "upload", slug, "--file", "final_reel_cap.mp4", "--privacy", os.environ.get("NAVAAN_YT_PRIVACY", "private"), "--yes")],
             done=lambda m: yt_done(m), sets_after="published"),
        dict(id="archive", label="Archive the finished song to cloud storage", kind="script", before="cloud_upload", optional_cloud=True,
             cmds=[sc("upload_cloud.py", slug, "--yes")], done=lambda m: bool(m.get("cloud", {}).get("uploaded_at"))),
        dict(id="publish_instagram", label="Publish Reel to Instagram (API)", kind="script", before="publish_instagram", optional=True,
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
        row = {"id": s["id"], "label": s["label"], "kind": s["kind"], "done": d, "gate_before": s.get("before"), "gate_after": s.get("after")}
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


def claude_cmd(slug, s):
    D = song_dir(slug)
    base = shlex.split(os.environ.get("NAVAAN_CLAUDE_CMD", "claude -p"))
    prompt = (f"Use the {s['skill']} skill for song {slug} in this project. Follow the navaan-studio AGENTS.md. Do only this step, update {D}/meta.json history, "
              f"then stop. Approvals recorded in meta.json are the only permission you have: do not publish, delete or spend credits beyond them. "
              f"Ask for a human at any login, CAPTCHA or file picker.")
    extra = shlex.split(os.environ.get("NAVAAN_CLAUDE_BROWSER_FLAG", "")) if s.get("chrome") else []
    return base + extra + [prompt]


def run(slug, step=None, dry=False, retries=2):
    D = song_dir(slug); rows, nxt = plan(slug)
    if nxt["type"] == "done": print("all steps done"); return 0
    if nxt["type"] == "gate": print(f"waiting for your approval: gate '{nxt['gate']}' (step {nxt['step']}). Run: navaan.py approve {slug} {nxt['gate']}"); return 3
    sid = step or nxt["step"]; s = next(x for x in steps(slug, D) if x["id"] == sid)
    if s["id"] == "publish_instagram" and not s.get("cmds"):
        bucket = cfg("storage.cloud_bucket") if cfg("storage.cloud_provider") == "oci" else None
        if not bucket: print("Instagram needs a public video URL. Use an OCI bucket in the profile (storage.cloud_provider oci), or run publish_instagram.py yourself with --video-url."); return 4
        cap = os.path.join(D, "publish"); os.makedirs(cap, exist_ok=True)
        s["cmds"] = [["bash", "-c", f'U=$(NAVAAN_BUCKET={shlex.quote(bucket)} bash {shlex.quote(os.path.join(HERE, "oci_public_url.sh"))} {shlex.quote(os.path.join(D, "final_reel_cap.mp4"))}) && '
                      f'{shlex.quote(PY)} {shlex.quote(os.path.join(HERE, "publish_instagram.py"))} publish {shlex.quote(slug)} --video-url "$U" --caption-file instagram.txt --yes']]
    cmds = [claude_cmd(slug, s)] if s["kind"] == "claude" else s["cmds"]
    if dry:
        for c in cmds: print(" ".join(shlex.quote(x) for x in c))
        return 0
    os.makedirs(os.path.join(D, "logs"), exist_ok=True)
    lp = os.path.join(D, "logs", f"{sid}.log")
    for attempt in range(1, retries + 2):
        with open(lp, "a", encoding="utf-8") as lf:
            lf.write(f"\n=== {now()} {sid} attempt {attempt} ===\n")
            ok = all(run_cmd(c, lf) == 0 for c in cmds)
        m = meta(slug)
        if ok and s["done"](m):
            if s.get("sets_after"): m["state"] = s["sets_after"]
            log_hist(m, f"step {sid} done (attempt {attempt})"); save_meta(slug, m); print("done", sid); return 0
        log_hist(m, f"step {sid} attempt {attempt} did not finish"); save_meta(slug, m)
        if attempt <= retries: time.sleep(5 * attempt)
    print(f"step {sid} failed after {retries + 1} attempts. See {lp}"); return 1


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
            STATUS[slug] = f"step {nxt['step']} failed, see logs"; return rc
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
