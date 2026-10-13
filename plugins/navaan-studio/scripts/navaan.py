#!/usr/bin/env python3
"""navaan.py  workflow orchestrator and local web UI for NAVAAN Studio. Standard library only.

  navaan.py init                      create navaan.config.json (artist profile) interactively
  navaan.py new [slug] [--type music|inspiration] [--idea TEXT]   create an item (the slug is optional, the type picks the pipeline)
  navaan.py account <type>            show where a content type publishes and what is missing
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
  navaan.py caption <slug> [--set TEXT | --file PATH | --feedback TEXT]   show the Instagram caption awaiting approval, replace it, or have the agent rewrite it
  navaan.py question <slug>           show a question the agent is waiting on
  navaan.py answer <slug> [--choice ID] [--text TEXT]   answer it (the web UI shows the same question as a card)
  navaan.py serve [--port 8765]       local web UI on 127.0.0.1: create, review, approve, run

Steps: lyrics, suno (or suno_import for an imported song), visuals_mode (your own pictures, the default, or Flow; with own pictures the steps are shots, a director's shot list you approve, then a local render, see docs/VISUALS.md), visuals (Flow), captions (only when captions.enabled is true, off by default), video, youtube_meta, publish_youtube (private), youtube_short (private), instagram_caption, go_public (video and Short public), publish_instagram, archive (uploads the whole song and records the bucket URLs in meta.json), cleanup (last: deletes the local media after the bucket is checked).
Gates (human only): lyrics, suno_download, listen, credits, captions_setup, media, publish_youtube, publish_short, instagram_caption, publish_instagram, cloud_upload, local_cleanup, go_public. Approvals live in <local_dir>/songs/<slug>/meta.json.
Songs live in storage.local_dir from navaan.config.json (outside the plugin and its repository). After a song is final, the archive step uploads it to your cloud bucket.
Claude steps run `claude -p` with an allowlist of tools, because headless runs cannot answer permission prompts (override the command with NAVAAN_CLAUDE_CMD, the flags with NAVAAN_CLAUDE_FLAGS). Browser steps (Suno, Flow) need Claude in Chrome enabled; set
NAVAAN_CLAUDE_BROWSER_FLAG=--chrome if your Claude Code needs the flag. Scripts steps run the tools in this folder.
"""
import os, sys, json, time, glob, shlex, subprocess, datetime, threading, secrets, mimetypes, re, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import setup_captions
from navaan_common import find_root, song_dir, load_json, cfg, GATES, songs_root, item_type, account
import publish_schedule as PS
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
now = lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def files(D, pat): return sorted(glob.glob(os.path.join(D, pat)))
def has(D, *names): return all(os.path.exists(os.path.join(D, n)) for n in names)
def yt_done(m): return bool(m.get("published", {}).get("youtube_items"))
def public_done(m):
    p = m.get("published", {}); its = list(p.get("youtube_items", [])) + ([p["youtube_short"]] if p.get("youtube_short", {}).get("id") else [])
    return bool(its) and all(i.get("privacy") == "public" for i in its)
def ig_done(m): return bool(m.get("published", {}).get("instagram"))
SHA_FILES = {"instagram_caption": "instagram.txt", "quote": "quote.json", "shots": "shots.json"}  # these approvals are tied to the file's hash, so an edit after approval needs a new approval
def file_sha(D, name):
    p = os.path.join(D, name)
    return hashlib.sha256(open(p, encoding="utf-8").read().strip().encode("utf-8")).hexdigest() if os.path.exists(p) else None
def gate_sha(D, g): return file_sha(D, SHA_FILES[g]) if g in SHA_FILES else None
def caption_sha(D):
    """Hash of instagram.txt. The caption approval is tied to this hash, so any edit after approval needs a new approval."""
    p = os.path.join(D, "instagram.txt")
    return hashlib.sha256(open(p, encoding="utf-8").read().strip().encode("utf-8")).hexdigest() if os.path.exists(p) else None
def gate_ok(D, ap, g, published=False):
    if published and g == "instagram_caption": return True  # already posted, nothing left to approve
    a = ap.get(g)
    if not a: return False
    return a.get("sha") == gate_sha(D, g) if g in SHA_FILES else True
def fresh(D, outs, src):
    """True when every file in outs exists and is newer than the newest source file, so a new clip makes the videos stale."""
    ss = [os.path.getmtime(p) for pat in src for p in glob.glob(os.path.join(D, pat))]
    return all(os.path.exists(os.path.join(D, o)) and (not ss or os.path.getmtime(os.path.join(D, o)) >= max(ss)) for o in outs)
def sc(name, *args): return [PY, os.path.join(HERE, name), *args]


def music_steps(slug, D):
    reel_meta = ["--meta", "tags.json"]
    imported = load_json(os.path.join(D, "meta.json"), default={}).get("source") == "suno_import"
    head = [
        dict(id="suno_import", outputs=['final.mp3', 'lyrics.txt', 'style.txt', 'title.txt', 'takes/imported.*'], label="Import the song from Suno", kind="claude", skill="suno-import", chrome=True, state="draft", before="suno_download",
             done=lambda m: has(D, "lyrics.txt", "style.txt", "title.txt", "final.mp3"), after="listen", sets="accepted"),
    ] if imported else [
        dict(id="lyrics", outputs=['lyrics.txt', 'style.txt', 'title.txt'], label="Write lyrics and style", kind="claude", skill="lyrics", chrome=False, state="draft",
             done=lambda m: has(D, "lyrics.txt", "style.txt", "title.txt"), after="lyrics", sets="lyrics_ok"),
        dict(id="suno", outputs=['final.mp3'], label="Generate the song on Suno", kind="claude", skill="suno-generate", chrome=True, before="credits", state="lyrics_ok",
             done=lambda m: has(D, "final.mp3"), after="listen", sets="accepted"),
    ]
    VJ = load_json(os.path.join(D, "visuals.json"), default={}) or {}
    vmode = VJ.get("mode")  # "own" (the user's pictures, rendered here, the default) or "flow" (Google Flow clips); songs from before this choice count as flow
    has_visuals = len(files(D, "clips/*.mp4")) > 0 or has(D, "final_16x9.mp4") or has(D, "cover_1x1.png") or bool(load_json(os.path.join(D, "meta.json"), default={}).get("cleanup"))
    choose = dict(id="visuals_mode", outputs=["visuals.json"], label="Choose the visuals: your own pictures (default) or Flow", kind="script", before="visuals_mode",
                  cmds=[sc("visuals_cfg.py", slug)], done=lambda m: bool(vmode) or has_visuals)
    own_static = VJ.get("layout") == "static"
    own_steps = ([] if own_static else [
        dict(id="shots", outputs=["shots.json", "shots_context.json", "shots_props.json"], label="Director's shot list from the lyrics (you approve or edit it)", kind="claude", skill="director-shots", chrome=False,
             done=lambda m: has(D, "shots.json"), after="shots")]) + [
        dict(id="video", outputs=["final_16x9.mp4", "final_tagged.mp3", "cover_1x1.png", "cover_16x9.png", "thumb_16x9.jpg", "render_report.json"], label="Render the video here from your pictures and tag the mp3", kind="script", sets_after="media_ready",
             cmds=[sc("shots_render.py", slug), sc("tag_mp3.py", slug)],
             done=lambda m: fresh(D, ["final_16x9.mp4", "final_tagged.mp3"], ["visuals.json", "images/*"] + ([] if own_static else ["shots.json"])), after="media", sets="approved"),
    ]
    CAP = bool(cfg("captions.enabled", False))  # lyric captions over the video are off unless the profile turns them on
    cap_steps = [
        dict(id="captions", outputs=['caption_cues.json', 'reel_start.json', '.cache'], label="Measure lyric timing", kind="script", before=(None if setup_captions.ready() else "captions_setup"),
             cmds=([sc("setup_captions.py", "--yes")] if not setup_captions.ready() else []) + [sc("captions_run.py", slug)],
             done=lambda m: has(D, "caption_cues.json", "reel_start.json")),
    ] if CAP else []
    REELS = bool(cfg("video.make_reel", False))  # YouTube makes Shorts from the full video in its editor, so a separate vertical reel is optional
    FULL = "final_16x9_cap.mp4" if (CAP and vmode != "own") else "final_16x9.mp4"
    REEL = "final_reel_cap.mp4" if CAP else "final_reel_sync.mp4"
    flow_steps = [
        dict(id="visuals", outputs=['clips/*.mp4', 'cover_1x1.png', 'cover_16x9.png', 'cover_flow.jpg', 'cover_art.*', 'thumb_16x9.jpg', 'scenes/*.txt'], label="Cover art and Flow clips", kind="claude", skill="flow-visuals", chrome=True, before="credits",
             done=lambda m: len(files(D, "clips/*.mp4")) > 0 and has(D, "cover_1x1.png")),
        *cap_steps,
        dict(id="video", outputs=['final_16x9*.mp4', 'final_reel*.mp4', 'final_tagged.mp3'], label=("Render videos, captions, tags" if CAP else ("Render videos and tags" if REELS else "Render the video and tags")), kind="script", sets_after="media_ready",
             cmds=[sc("clipvideo.py", slug, "16x9")] + ([sc("clipvideo.py", slug, "reel")] if REELS else []) + ([sc("caption_clips.py", slug, "16x9")] + ([sc("caption_clips.py", slug, "reel")] if REELS else []) if CAP else []) + [sc("tag_mp3.py", slug)],
             done=lambda m: fresh(D, [FULL] + ([REEL] if REELS else []) + ["final_tagged.mp3"], ["clips/*.mp4"]), after="media", sets="approved"),
    ]
    tail = [
        dict(id="youtube_meta", outputs=["youtube.json"], redo=True, label="Write the YouTube title, description and tags from the lyrics", kind="claude", skill="youtube-meta",
             done=lambda m: has(D, "youtube.json") or yt_done(m)),
        dict(id="publish_youtube", outputs=[], redo=False, label="Upload to YouTube (API)", kind="script", before="publish_youtube",
             cmds=[sc("publish_youtube.py", "upload", slug, "--file", FULL, "--meta", "youtube.json", *(["--thumbnail", "thumb_16x9.jpg"] if has(D, "thumb_16x9.jpg") and cfg("publish.youtube_thumbnail", True) else []), "--privacy", os.environ.get("NAVAAN_YT_PRIVACY", "private"), "--yes")],
             done=lambda m: yt_done(m), sets_after="published"),
        dict(id="youtube_short", outputs=[], redo=False, label="Make the Short in YouTube Studio and download it", kind="claude", skill="youtube-short", chrome=True, before="publish_short",
             done=lambda m: bool(m.get("published", {}).get("youtube_short")) and has(D, "short.mp4")),
        dict(id="go_public", outputs=[], redo=False, label="Make the YouTube video and Short public", kind="script", before="go_public",
             cmds=[sc("publish_youtube.py", "go-public", slug, "--yes")], done=lambda m: public_done(m)),
        dict(id="instagram_caption", outputs=[], redo=False, label="Write the Instagram caption from the lyrics (you review and can edit it)", kind="claude", skill="instagram-caption", optional=True, after="instagram_caption",
             done=lambda m: has(D, "instagram.txt")),
        dict(id="publish_instagram", outputs=[], redo=False, label="Publish Reel to Instagram (API)", kind="script", before="publish_instagram", optional=True,
             cmds=None, done=lambda m: ig_done(m)),
        dict(id="archive", outputs=[], redo=False, label="Archive the finished song to cloud storage", kind="script", before="cloud_upload", optional_cloud=True,
             cmds=[sc("upload_cloud.py", slug, "--yes")], done=lambda m: bool(m.get("cloud", {}).get("uploaded_at")) and m["cloud"].get("verified", True)),
        dict(id="cleanup", outputs=[], redo=False, label="Clean up the local copy (last step, only after the bucket is checked)", kind="script", before="local_cleanup", optional_cloud=True,
             cmds=[sc("cleanup.py", slug, "--yes")], done=lambda m: bool(m.get("cleanup", {}).get("at"))),
    ]
    return head + [choose] + (own_steps if vmode == "own" else flow_steps) + tail


def brief_opt(D, key, default=""):
    """Read an option line such as `- music: auto` from brief.md."""
    p = os.path.join(D, "brief.md")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            m = re.match(rf"^\s*[-*]?\s*{key}\s*:\s*(.+?)\s*$", ln, re.I)
            if m and m.group(1).strip(): return m.group(1).strip()
    return default


def ig_enabled(m):
    """Instagram steps are on when the profile names a handle. Inspiration always shows them: it has its own account, checked before any post."""
    return item_type(m) == "inspiration" or bool(cfg("publish.instagram_handle") or os.environ.get("NAVAAN_WITH_INSTAGRAM"))


def inspiration_steps(slug, D):
    """Quote, originality check, background, typography and music, render, review, then publish to YouTube Shorts and Instagram from the item's own account."""
    FINAL = "final_reel_9x16.mp4"
    gen = brief_opt(D, "background", "generate").lower() == "generate"
    has_bg = lambda m: any(glob.glob(os.path.join(D, f"background.{e}")) for e in ("jpg", "jpeg", "png", "webp"))
    return [
        dict(id="quote", outputs=["quote.json", "title.txt"], label="Write or pick the quote", kind="claude", skill="inspiration-quote", chrome=False, state="draft",
             done=lambda m: has(D, "quote.json", "title.txt"), after="quote", sets="quote_ok"),
        dict(id="originality", outputs=["originality.json"], label="Check originality and attribution on the web", kind="claude", skill="inspiration-check", chrome=False, tools=["WebSearch", "WebFetch"],
             done=lambda m: has(D, "originality.json"), after="originality"),
        dict(id="background", outputs=["background.*", "scenes/background.txt"], label=("Create the background image (Flow)" if gen else "Pick the background image"), kind="claude", skill="inspiration-visual", chrome=gen,
             before=("credits" if gen else None), done=has_bg),
        dict(id="typeset", outputs=["timing.json", "music.mp3", "beats.json"], label="Plan typography, timing and music", kind="script", cmds=[sc("inspire_prep.py", slug)],
             done=lambda m: fresh(D, ["timing.json"], ["quote.json", "background.*", "voiceover.*"])),
        dict(id="render", outputs=[FINAL, "thumb_9x16.jpg", "render_report.json"], label="Render the vertical video (9:16, 10 to 30 s)", kind="script", sets_after="media_ready",
             cmds=[sc("inspire_render.py", slug)], done=lambda m: fresh(D, [FINAL], ["timing.json", "background.*", "music.mp3", "voiceover.*"]), after="media", sets="approved"),
        dict(id="youtube_meta", outputs=["youtube.json"], redo=True, label="Write the YouTube Shorts title, description and tags", kind="claude", skill="inspiration-meta",
             done=lambda m: has(D, "youtube.json") or yt_done(m)),
        dict(id="publish_youtube", outputs=[], redo=False, label="Upload to YouTube as a Short (API, private)", kind="script", before="publish_youtube",
             cmds=[sc("publish_youtube.py", "upload", slug, "--file", FINAL, "--meta", "youtube.json", "--privacy", os.environ.get("NAVAAN_YT_PRIVACY", "private"), "--yes")],
             done=lambda m: yt_done(m), sets_after="published"),
        dict(id="instagram_caption", outputs=[], redo=False, label="Write the Instagram caption (you review and can edit it)", kind="claude", skill="inspiration-caption", optional=True, after="instagram_caption",
             done=lambda m: has(D, "instagram.txt")),
        dict(id="go_public", outputs=[], redo=False, label="Make the YouTube Short public", kind="script", before="go_public",
             cmds=[sc("publish_youtube.py", "go-public", slug, "--yes")], done=lambda m: public_done(m)),
        dict(id="publish_instagram", outputs=[], redo=False, label="Publish Reel to Instagram (API)", kind="script", before="publish_instagram", optional=True,
             cmds=None, done=lambda m: ig_done(m)),
        dict(id="archive", outputs=[], redo=False, label="Archive to cloud storage", kind="script", before="cloud_upload", optional_cloud=True,
             cmds=[sc("upload_cloud.py", slug, "--yes")], done=lambda m: bool(m.get("cloud", {}).get("uploaded_at")) and m["cloud"].get("verified", True)),
        dict(id="cleanup", outputs=[], redo=False, label="Clean up the local copy (last step, only after the bucket is checked)", kind="script", before="local_cleanup", optional_cloud=True,
             cmds=[sc("cleanup.py", slug, "--yes")], done=lambda m: bool(m.get("cleanup", {}).get("at"))),
    ]


STEPSETS = {"music": music_steps, "inspiration": inspiration_steps}


def steps(slug, D):
    """The step list for this item's content type. Gates, approvals, publishing and archiving are shared; the production steps differ."""
    t = item_type(load_json(os.path.join(D, "meta.json"), default={}))
    fn = STEPSETS.get(t)
    if not fn: sys.exit(f"navaan: the {t} pipeline is planned, not built yet.")
    return fn(slug, D)


def account_env(slug):
    """Environment for a step's commands. Non-music items publish with their own login files, never the NAVAAN ones."""
    t = item_type(meta(slug))
    if t == "music": return None
    a = account(t); env = dict(os.environ)
    for k in list(env):
        if k.startswith("NAVAAN_IG_") and k not in ("NAVAAN_IG_HOST", "NAVAAN_IG_API_VERSION"): del env[k]  # a shell-exported token must not win over this account's file
    env.pop("NAVAAN_YT_TOKEN", None); env.pop("NAVAAN_YT_CLIENT_SECRETS", None)
    if a.get("ig_env"): env["NAVAAN_IG_ENV"] = a["ig_env"]
    if a.get("yt_token"): env["NAVAAN_YT_TOKEN"] = a["yt_token"]
    if a.get("yt_secret"): env["NAVAAN_YT_CLIENT_SECRETS"] = a["yt_secret"]
    return env


def account_problem(slug, sid):
    """Why a publishing step must not run yet, or "". Starts with ACCOUNT: so the portal can tell it from an agent's needs_you note."""
    t = item_type(meta(slug))
    if t == "music" or sid not in ("publish_youtube", "go_public", "publish_instagram"): return ""
    a = account(t)
    if not a["configured"]:
        return (f"ACCOUNT: {t} content publishes to its own account and none is set up yet. Add accounts.{t} to navaan.config.json "
                f"(instagram_handle, youtube_channel, instagram_env, youtube_token), then run: navaan.py account {t}. Nothing was posted.")
    if a["same_as_music"]: return f"ACCOUNT: accounts.{t} points at the NAVAAN login files. Give {t} its own instagram_env and youtube_token files. Nothing was posted."
    if sid == "publish_instagram" and not a["ig_ready"]: return f"ACCOUNT: the Instagram login file for {t} is missing: {a['ig_env']}. Put NAVAAN_IG_USER_ID and NAVAAN_IG_TOKEN there (mode 600). Nothing was posted."
    if sid in ("publish_youtube", "go_public") and not a["yt_ready"]:
        return (f"ACCOUNT: the YouTube login for {t} is missing: {a['yt_token']}. Sign in with the {t} Google account: NAVAAN_YT_TOKEN={a['yt_token']} "
                f"python3 {os.path.join(HERE, 'publish_youtube.py')} auth. Nothing was posted.")
    return ""


def account_cmd(t):
    a = account(t)
    print(f"{t} account: handle={a['handle'] or '(not set)'} channel={a['youtube_channel'] or '(not set)'}")
    if t == "music": print("music uses the default NAVAAN login files."); return 0
    print(f"  configured={a['configured']}  instagram login file ready={a['ig_ready']}  youtube token ready={a['yt_ready']}  shares NAVAAN files={a['same_as_music']}")
    for sid in ("publish_youtube", "publish_instagram"):
        pr = account_problem_for(t, sid)
        if pr: print(" -", pr)
    return 0


def account_problem_for(t, sid):
    a = account(t)
    if not a["configured"]: return f"no accounts.{t} block in navaan.config.json. Needs instagram_handle, youtube_channel, instagram_env, youtube_token."
    if a["same_as_music"]: return "its login files are the NAVAAN ones."
    if sid == "publish_instagram" and not a["ig_ready"]: return f"Instagram login file missing: {a['ig_env']}"
    if sid == "publish_youtube" and not a["yt_ready"]: return f"YouTube token missing: {a['yt_token']}  (sign in: NAVAAN_YT_TOKEN={a['yt_token']} python3 {os.path.join(HERE, 'publish_youtube.py')} auth)"
    return ""


def meta(slug): return load_json(os.path.join(song_dir(slug), "meta.json"), default={})


def save_meta(slug, m):
    p = os.path.join(song_dir(slug), "meta.json")
    json.dump(m, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False); open(p, "a").write("\n")


def log_hist(m, text): m.setdefault("history", []).append(f"{now()} {text}")


def plan(slug):
    """Walk the steps in order and return (rows, next_action). Everything is derived from files plus approvals."""
    D = song_dir(slug); m = meta(slug); ap = m.get("approvals", {}); rows = []; nxt = None
    legacy = m.get("state") == "published" and any(a.get("via") == "legacy backfill" for a in ap.values())  # songs finished before navaan-studio
    cleaned = bool(m.get("cleanup"))  # local media was deleted after a verified archive, so earlier steps no longer have their files and must not look unfinished
    for s in steps(slug, D):
        if s.get("optional") and not ig_enabled(m):
            continue
        if s.get("optional_cloud") and cfg("storage.cloud_provider", "none") in ("none", None, ""):
            continue
        skip = (legacy or cleaned) and s["id"] not in ("archive", "cleanup")
        if s["id"] in ("instagram_caption", "publish_instagram") and not ig_done(m): skip = False  # never posted, so there is still a caption to write and approve
        reel_made = os.path.exists(os.path.join(D, "reel_clip.json")) and (s["id"] in ("instagram_caption", "publish_instagram") or (s["id"] in ("archive", "cleanup") and ig_done(m)))  # a reel was cut for Instagram from this older song, so those steps are live again, and once it is posted the song can be archived and cleaned up
        notused = legacy and s["id"] in ("instagram_caption", "publish_instagram", "archive", "cleanup") and not s["done"](m) and not reel_made  # older song, finished before these steps existed
        if notused: skip = True
        d = s["done"](m) or skip
        row = {"id": s["id"], "label": s["label"], "kind": s["kind"], "done": d, "redo": s.get("redo", True), "spends": s.get("before") == "credits", "gate_before": s.get("before"), "gate_after": s.get("after")}
        gb, ga = s.get("before"), s.get("after")
        if d:
            row["status"] = "waiting for approval" if (ga and not gate_ok(D, ap, ga, ig_done(m))) else "done"
            row["needs_gate"] = ga if (ga and not gate_ok(D, ap, ga, ig_done(m))) else None
        else:
            row["needs_gate"] = gb if (gb and not gate_ok(D, ap, gb, ig_done(m))) else None
            row["status"] = "waiting for approval" if row["needs_gate"] else ("blocked" if (nxt and nxt["type"] == "gate") else "ready")
        if notused: row["status"] = "done"; row["needs_gate"] = None; row["notused"] = True
        row["scheduled_for"] = PS.when(m, s["id"]) if not d else None
        rows.append(row)
        if nxt is None:
            if row["needs_gate"]: nxt = {"type": "gate", "step": s["id"], "gate": row["needs_gate"]}
            elif not d: nxt = {"type": "run", "step": s["id"]}
    return rows, (nxt or {"type": "done"})


def run_cmd(cmd, logf, env=None):
    logf.write(f"\n$ {' '.join(shlex.quote(c) for c in cmd)}\n"); logf.flush()
    return subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT, cwd=find_root(), env=env).returncode


DEFAULT_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash(python3:*)", "Bash(python:*)", "Bash(ffmpeg:*)", "Bash(ffprobe:*)",
                 "Bash(ls:*)", "Bash(sleep:*)", "Bash(cat:*)", "Bash(mkdir:*)", "Bash(cp:*)", "Bash(mv:*)", "Bash(open:*)"]
CHROME_TOOLS = ["mcp__claude-in-chrome__*"]


def qfile(D): return os.path.join(D, "question.json")


def read_question(slug):
    """The question an agent left for the human, or None. The id is a hash of the content, so the agent cannot reuse an old answer by reusing an id."""
    p = qfile(song_dir(slug))
    if not os.path.exists(p): return None
    try: q = json.load(open(p, encoding="utf-8"))
    except Exception: return None
    if not isinstance(q, dict) or not str(q.get("text", "")).strip(): return None
    opts = [{"id": re.sub(r"[^A-Za-z0-9_-]", "_", str(o.get("id", i)))[:40], "label": str(o.get("label", o.get("id", i))), "text": bool(o.get("text"))} for i, o in enumerate(q.get("options") or []) if isinstance(o, dict)]
    out = {"text": str(q["text"]).strip(), "options": opts, "allow_text": bool(q.get("allow_text")) or not opts}
    out["id"] = hashlib.sha1(json.dumps([out["text"], [o["label"] for o in opts]], ensure_ascii=False).encode("utf-8")).hexdigest()[:10]
    return out


def question_open(slug):
    """The question still waiting for an answer. An answered question is cleared, so the agent is never blocked by a stale file."""
    q = read_question(slug)
    if not q: return None
    if q["id"] in meta(slug).get("answers", {}):
        try: os.remove(qfile(song_dir(slug)))
        except OSError: pass
        return None
    return q


def set_answer(slug, choice=None, text=None, via="cli"):
    """Record the human's answer to the open question. Only a person calls this (web UI or terminal), never an agent."""
    q = question_open(slug)
    if not q: sys.exit("no open question for this song")
    lab = {o["id"]: o["label"] for o in q["options"]}
    if q["options"] and choice not in lab: sys.exit("pick one of: " + ", ".join(f"{k} ({v})" for k, v in lab.items()))
    if not q["options"] and not (text or "").strip(): sys.exit("type an answer")
    flagged = {o["id"] for o in q["options"] if o["text"]}
    if flagged:  # some buttons take the text box, the others ignore it, so typing a filename can never ride along with Cancel
        if choice in flagged and not (text or "").strip(): sys.exit("this answer needs the text box filled in")
        if choice not in flagged: text = ""
    m = meta(slug)
    m.setdefault("answers", {})[q["id"]] = {"at": now(), "via": via, "question": q["text"], "choice": choice or "", "choice_label": lab.get(choice, ""), "text": (text or "").strip()}
    log_hist(m, f"question answered via {via}: {lab.get(choice) or (text or '').strip()[:80]}"); save_meta(slug, m)
    try: os.replace(qfile(song_dir(slug)), os.path.join(song_dir(slug), "logs", f"question-{q['id']}.json"))
    except OSError: pass
    return q["id"]


def answers_text(slug):
    a = {k: r for k, r in meta(slug).get("answers", {}).items() if not r.get("consumed")}
    if not a: return ""
    lines = []
    for r in sorted(a.values(), key=lambda r: r.get("at", "")):
        ans = r.get("choice_label") or r.get("choice") or ""
        if r.get("text"): ans = (ans + ": " if ans else "") + r["text"]
        lines.append(f"- Q: {r.get('question', '')} A: {ans}")
    return "Answers the user gave in the web portal (these are real answers from the user, use them and do not ask again):\n" + "\n".join(lines)


USED = set()  # slugs whose open answers were handed to an agent in the current run


def consume_answers(slug):
    """An answer belongs to the run that follows it. After that run, it no longer applies, so a later Redo starts clean."""
    m = meta(slug); ch = False
    for r in m.get("answers", {}).values():
        if not r.get("consumed"): r["consumed"] = now(); ch = True
    if ch: save_meta(slug, m)


def question_cmd(slug, a):
    def opt(n): return a[a.index(n) + 1] if n in a and a.index(n) + 1 < len(a) else None
    if "--choice" in a or "--text" in a:
        if not sys.stdin.isatty(): sys.exit("answer needs a terminal. An agent must never answer for you. Use this command yourself or the web UI.")
        set_answer(slug, opt("--choice"), opt("--text"), "cli"); print("answered. Run the pipeline again, or the waiting pipeline continues by itself."); return 0
    q = question_open(slug)
    if not q: print("no open question"); return 0
    print("\n" + q["text"])
    for o in q["options"]: print(f"  [{o['id']}] {o['label']}")
    print(f"Answer: navaan.py answer {slug} " + ("--choice ID" if q["options"] else "--text \"...\"") + (" [--text \"...\"]" if q["options"] and q["allow_text"] else ""))
    return 0


def claude_cmd(slug, s):
    """Headless `claude -p` cannot answer permission prompts, so list exactly the tools a step may use. Publishing, deleting and
    credit spending are not on the list; the gates in meta.json stay the real control. NAVAAN_CLAUDE_FLAGS replaces the flags."""
    D = song_dir(slug)
    base = shlex.split(os.environ.get("NAVAAN_CLAUDE_CMD", "claude -p"))
    chrome = bool(s.get("chrome"))
    prompt = (f"Use the {s['skill']} skill for item {slug} in this project. Follow the navaan-studio AGENTS.md. Do only this step, update {D}/meta.json history, "
              f"then stop. Approvals recorded in meta.json are the only permission you have: do not publish, delete or spend credits beyond them. "
              + ("Use Claude in Chrome (the mcp__claude-in-chrome tools), not Playwright. " if chrome else "")
              + "You run headless: nobody can answer you in chat. Never write to the approvals or answers keys in meta.json. "
              + "If you need a human decision or action (a login, a CAPTCHA, a file picker, a choice), do not ask in chat. Write the file "
              + f"{D}/question.json as {{\"text\": \"one plain question\", \"options\": [{{\"id\": \"short_id\", \"label\": \"what the button says\"}}], \"allow_text\": false}} "
              + "(allow_text true adds a free text box; set \"text\": true on the option that needs what the user types, such as a filename), say nothing else, and stop. The user answers in the web portal and the step runs again with the answer below. "
              + answers_text(slug))
    if "NAVAAN_CLAUDE_FLAGS" in os.environ:
        flags = shlex.split(os.environ["NAVAAN_CLAUDE_FLAGS"])
    else:
        tools = DEFAULT_TOOLS + (CHROME_TOOLS if chrome else []) + list(s.get("tools", []))
        flags = ["--permission-mode", "acceptEdits", "--allowedTools", ",".join(tools), "--add-dir", D]
        dl = os.path.expanduser("~/Downloads")
        if chrome and os.path.isdir(dl): flags += ["--add-dir", dl]
        if chrome: flags += ["--chrome"]
    if chrome and "NAVAAN_CLAUDE_BROWSER_FLAG" in os.environ: flags += shlex.split(os.environ["NAVAAN_CLAUDE_BROWSER_FLAG"])
    return base + [prompt] + flags


def run(slug, step=None, dry=False, retries=2):
    try: return _run(slug, step, dry, retries)
    finally:
        if slug in USED: USED.discard(slug); consume_answers(slug)


def _run(slug, step=None, dry=False, retries=2):
    D = song_dir(slug); rows, nxt = plan(slug)
    if nxt["type"] == "done": print("all steps done"); return 0
    if nxt["type"] == "gate": show_gate(slug, nxt["gate"]); print(f"waiting for your approval: gate '{nxt['gate']}' (step {nxt['step']}). Run: navaan.py approve {slug} {nxt['gate']}"); return 3
    sid = step or nxt["step"]; s = next((x for x in steps(slug, D) if x["id"] == sid), None)
    if not s: print(f"no such step: {sid}"); return 2
    bg = s.get("before")
    ap_msg = account_problem(slug, sid); nyp = os.path.join(D, "needs_you.txt")
    if ap_msg and not dry:
        open(nyp, "w", encoding="utf-8").write(ap_msg + "\n"); RUN[slug] = {"step": None, "failed": sid, "log": None}
        print(ap_msg); return 5
    if os.path.exists(nyp) and open(nyp, encoding="utf-8").read().startswith("ACCOUNT:"): os.remove(nyp)  # the account is fine now
    if bg and not gate_ok(D, meta(slug).get("approvals", {}), bg):
        show_gate(slug, bg); print(f"waiting for your approval: gate '{bg}' (step {sid}). Run: navaan.py approve {slug} {bg}"); return 3
    hw = PS.hold(meta(slug), sid) if not dry else None
    if hw and slug not in PS.FIRING:
        print(f"scheduled: step {sid} waits until {hw} (UTC). The portal, or navaan.py schedule-run, starts it then. Clear the schedule to publish now."); return 7
    if sid in ("publish_youtube", "go_public") and not dry and slug not in PS.FIRING and not PS.get(meta(slug)):  # a hint only, it never blocks or schedules
        try:
            sg = PS.suggest(slug)
            if sg: print(f"Tip: the analytics suggest publishing at {PS.parse(sg['youtube_at'] or sg['instagram_at']).astimezone():%a %b %d %H:%M}. See it with: navaan.py schedule {slug} --suggest")
        except Exception: pass
    if s["id"] == "publish_instagram" and not public_done(meta(slug)): print("Publish to YouTube first: the Reel links to the public full video. Approve gate 'go_public' and run that step."); return 3
    if s["id"] == "publish_instagram" and not s.get("cmds"):
        bucket = cfg("storage.cloud_bucket") if cfg("storage.cloud_provider") == "oci" else None
        if not bucket: print("Instagram needs a public video URL. Use an OCI bucket in the profile (storage.cloud_provider oci), or run publish_instagram.py yourself with --video-url."); return 4
        cands = ["final_reel_9x16.mp4"] + (["final_reel_cap.mp4"] if cfg("captions.enabled", False) else []) + ["final_reel_sync.mp4", "short.mp4"]  # the tuned reel first, the YouTube Studio clip as fallback
        rf = next((c for c in cands if os.path.exists(os.path.join(D, c))), None)
        if not rf: print("Instagram needs a vertical video. Run the youtube_short step (it downloads short.mp4), or set video.make_reel to true in the profile and redo the video step."); return 4
        if not gate_ok(D, meta(slug).get("approvals", {}), "instagram_caption"): show_gate(slug, "instagram_caption"); print("The Instagram caption is missing or changed since you approved it. Approve gate 'instagram_caption' again."); return 3
        cap = os.path.join(D, "publish"); os.makedirs(cap, exist_ok=True)
        oci = f'NAVAAN_BUCKET={shlex.quote(bucket)} bash {shlex.quote(os.path.join(HERE, "oci_public_url.sh"))}'
        cover = os.path.join(D, "thumb_9x16.jpg")  # a cover made for this reel (clip_reel.py or the inspiration render), sent as the Reel cover
        cv_get, cv_arg = ((f'CV=$({oci} {shlex.quote(cover)}) && ', ' --cover-url "$CV"') if os.path.exists(cover) else ("", ""))
        s["cmds"] = [["bash", "-c", f'U=$({oci} {shlex.quote(os.path.join(D, rf))}) && {cv_get}'
                      f'{shlex.quote(PY)} {shlex.quote(os.path.join(HERE, "publish_instagram.py"))} publish {shlex.quote(slug)} --video-url "$U"{cv_arg} --caption-file instagram.txt --yes']]
    if s["kind"] == "claude" and question_open(slug) and not dry:
        print(f"step {sid} is waiting for your answer: {question_open(slug)['text']}"); return 6
    cmds = [claude_cmd(slug, s)] if s["kind"] == "claude" else s["cmds"]
    if s["kind"] == "claude" and not dry and answers_text(slug): USED.add(slug)
    if dry:
        for c in cmds: print(" ".join(shlex.quote(x) for x in c))
        return 0
    os.makedirs(os.path.join(D, "logs"), exist_ok=True)
    lp = os.path.join(D, "logs", f"{sid}.log"); env = account_env(slug)
    for attempt in range(1, retries + 2):
        RUN[slug] = {"step": sid, "attempt": attempt, "attempts": retries + 1, "started": time.time(), "failed": None}
        with open(lp, "a", encoding="utf-8") as lf:
            lf.write(f"\n=== {now()} {sid} attempt {attempt} ===\n")
            ok = all(run_cmd(c, lf, env) == 0 for c in cmds)
        m = meta(slug)
        if ok and s["done"](m):
            if s.get("sets_after"): m["state"] = s["sets_after"]
            log_hist(m, f"step {sid} done (attempt {attempt})"); save_meta(slug, m); RUN.pop(slug, None); print("done", sid); return 0
        log_hist(m, f"step {sid} attempt {attempt} did not finish"); save_meta(slug, m)
        q = question_open(slug)
        if q:
            RUN[slug] = {"step": None, "failed": sid, "log": lp}
            print(f"step {sid} is waiting for your answer: {q['text']}"); return 6
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
        if rc == 6:
            q = question_open(slug); STATUS[slug] = "waiting for you: answer the question in the portal"
            print(f"waiting for your answer. Answer in the web UI or run: navaan.py answer {slug} ...", flush=True)
            if not wait or not q: return 6
            while question_open(slug) and question_open(slug)["id"] == q["id"]:
                if timeout and time.time() - t0 > timeout: print("timed out waiting for an answer"); return 6
                time.sleep(min(poll, 3))
            print("answered, continuing", flush=True); steps_run -= 1; continue
        if rc == 7:
            STATUS[slug] = "scheduled: it publishes at the set time"; print(STATUS[slug], flush=True); return 7
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
    for nm in ("needs_you.txt", "question.json"):
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


def show_gate(slug, gate):
    """Print what the human is about to approve, so approval is never blind."""
    if gate != "instagram_caption": return
    p = os.path.join(song_dir(slug), "instagram.txt")
    if not os.path.exists(p): return
    print("\n--- Instagram caption for approval ---\n" + open(p, encoding="utf-8").read().strip() + "\n--------------------------------------")
    print(f"Change it: navaan.py caption {slug} --set \"new text\"  (or --file path, or edit songs/{slug}/instagram.txt, or use the web UI)")
    print(f"Ask the agent to rewrite: navaan.py caption {slug} --feedback \"what to change\"")


def caption_cmd(slug, a):
    D = song_dir(slug); p = os.path.join(D, "instagram.txt")
    def opt(n): return a[a.index(n) + 1] if n in a and a.index(n) + 1 < len(a) else None
    txt = opt("--set") if "--set" in a else (open(os.path.expanduser(opt("--file")), encoding="utf-8").read() if "--file" in a else None)
    if txt is not None:
        open(p, "w", encoding="utf-8").write(txt.strip() + "\n")
        m = meta(slug); m.get("approvals", {}).pop("instagram_caption", None); log_hist(m, "instagram caption edited by user, approval cleared"); save_meta(slug, m)
        print("caption saved. Approve gate 'instagram_caption' to continue.")
    elif "--feedback" in a:
        fb = opt("--feedback") or ""
        if not fb.strip(): sys.exit("usage: navaan.py caption <slug> --feedback \"what to change\"")
        if os.path.exists(p): os.replace(p, os.path.join(D, "instagram.prev.txt"))
        open(os.path.join(D, "caption_feedback.txt"), "w", encoding="utf-8").write(fb.strip() + "\n")
        m = meta(slug); m.get("approvals", {}).pop("instagram_caption", None); log_hist(m, "instagram caption rewrite requested"); save_meta(slug, m)
        rc = run(slug, step="instagram_caption")
        if rc != 0 and os.path.exists(os.path.join(D, "instagram.prev.txt")) and not os.path.exists(p): os.replace(os.path.join(D, "instagram.prev.txt"), p)
        if rc == 0: os.path.exists(p) and print("new caption written.")
    if not os.path.exists(p): print("no caption yet. Run the instagram_caption step."); return 1
    show_gate(slug, "instagram_caption"); return 0


def set_gate(slug, gate, on, via):
    if gate not in GATES: sys.exit(f"unknown gate: {gate}. Gates: {', '.join(GATES)}")
    m = meta(slug); ap = m.setdefault("approvals", {})
    if on and gate in SHA_FILES and not gate_sha(song_dir(slug), gate): sys.exit(f"no {SHA_FILES[gate]} to approve yet. Run that step first.")
    if on: ap[gate] = {"at": now(), "via": via, **({"sha": gate_sha(song_dir(slug), gate)} if gate in SHA_FILES else {})}
    else: ap.pop(gate, None)
    D = song_dir(slug)
    for s in steps(slug, D):
        if on and s.get("after") == gate and s.get("sets"): m["state"] = s["sets"]
    log_hist(m, f"gate {gate} {'approved' if on else 'revoked'} via {via}"); save_meta(slug, m)


def status(slug=None):
    for sl in ([slug] if slug else sorted(os.path.basename(p) for p in glob.glob(f"{songs_root()}/*") if os.path.isdir(p) and not os.path.basename(p).startswith("_"))):
        rows, nxt = plan(sl); m = meta(sl)
        print(f"{sl}  type={item_type(m)} state={m.get('state','?')}  next={nxt.get('step') or 'done'}{' (needs your approval: ' + nxt['gate'] + ')' if nxt['type'] == 'gate' else ''}")
        if slug:
            for r in rows: print(f"   {'x' if r['status']=='done' else ' '} {r['id']:18} {r['status']}")


def main(argv):
    if not argv: print(__doc__); return 0
    c, a = argv[0], argv[1:]
    if c == "init": return subprocess.call([PY, os.path.join(HERE, "setup_profile.py")] + a)
    if c == "new": return subprocess.call([PY, os.path.join(HERE, "new_song.py")] + a)
    if c == "account": return account_cmd(a[0] if a else "inspiration")
    if c == "start": return start(a[0], " ".join(a[1:]))
    if c == "import":
        if not a: sys.exit("usage: navaan.py import <suno-url-or-id> [slug]")
        return import_suno(a[0], a[1] if len(a) > 1 else None)
    if c == "pipeline":
        def opt(n, d=None): return a[a.index(n) + 1] if n in a else d
        return pipeline(a[0], wait="--wait" in a, poll=int(opt("--poll", 10)), until=opt("--until"), timeout=int(opt("--timeout", 0)) or None)
    if c == "caption":
        if not a: sys.exit("usage: navaan.py caption <slug> [--set TEXT | --file PATH | --feedback TEXT]")
        return caption_cmd(a[0], a[1:])
    if c in ("question", "answer"):
        if not a: sys.exit(f"usage: navaan.py {c} <slug>" + (" [--choice ID] [--text TEXT]" if c == "answer" else ""))
        return question_cmd(a[0], a[1:] if c == "answer" else [])
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
    if c == "schedule":
        def opt(n, d=None): return a[a.index(n) + 1] if n in a and a.index(n) + 1 < len(a) else d
        if a and ("--suggest" in a or "--accept" in a):
            sg = PS.suggest(a[0])
            if not sg: print("no timing suggestion: nothing left to schedule, or no analytics timing data yet. Run collect, or use --at."); return 1
            loc = lambda t: PS.parse(t).astimezone().strftime("%a %b %d %H:%M") if t else "auto, 15 minutes before the Reel"
            print(f"suggested: YouTube public {loc(sg['youtube_at'])}, Reel {loc(sg['instagram_at'])}  (confidence {sg['confidence']}; {', '.join(sg['basis']) or 'followers online'}) {sg['note']}")
            if "--accept" not in a: print(f"Schedule these times: navaan.py schedule {a[0]} --accept   (approvals stay yours)"); return 0
            try: s = PS.accept(a[0])
            except ValueError as e: sys.exit(f"navaan: {e}")
            print("scheduled:", PS.status_text({"schedule": s}), "\nStill needed from you before then: approve go_public, instagram_caption and publish_instagram. Keep the portal or `navaan.py schedule-run --loop` running."); return 0
        if not a or not opt("--at"): sys.exit('usage: navaan.py schedule <slug> --at "2026-10-16 18:30" [--youtube-at "2026-10-16 18:15"] | --suggest | --accept   (your computer\'s local time)')
        def utc(x): return PS.iso(datetime.datetime.strptime(x.replace("T", " "), "%Y-%m-%d %H:%M").astimezone())
        try: s = PS.set_schedule(a[0], utc(opt("--at")), utc(opt("--youtube-at")) if opt("--youtube-at") else None)
        except ValueError as e: sys.exit(f"navaan: {e}")
        print("scheduled:", PS.status_text({"schedule": s}), "\nStill needed from you before then: approve go_public, instagram_caption and publish_instagram. Keep the portal or `navaan.py schedule-run --loop` running."); return 0
    if c == "schedule-clear": PS.clear(a[0]); print("cleared"); return 0
    if c == "schedules":
        for sl in sorted(os.path.basename(p) for p in glob.glob(f"{songs_root()}/*") if os.path.isdir(p) and not os.path.basename(p).startswith("_")):
            t = PS.status_text(meta(sl))
            if t: print(sl, t)
        return 0
    if c == "schedule-run":
        fire = lambda sl, sid: run(sl, step=sid)
        if "--loop" in a: print("scheduler running, checking every minute. Ctrl+C to stop.", flush=True); PS.loop(fire); return 0
        print(PS.tick(fire) or "nothing due"); return 0
    if c == "serve":
        import navaan_ui; return navaan_ui.serve(int(a[a.index("--port") + 1]) if "--port" in a else 8765)
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
