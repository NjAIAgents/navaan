#!/usr/bin/env python3
"""publish_youtube.py  upload to YouTube with the official Data API v3.

  upload <slug> --file final_reel_cap.mp4 [--meta tags.json] [--privacy private|unlisted|public]
         [--thumbnail thumb_16x9.jpg] [--playlist "Name"] [--yes]
  update <slug> <videoId> [--meta youtube.json] [--thumbnail thumb_16x9.jpg] [--yes]   fix metadata of an uploaded video
  thumb <slug> <videoId> [--file thumb_16x9.jpg]   set the thumbnail alone (channel needs phone verification at youtube.com/verify)
  privacy <slug> <videoId> <private|unlisted|public> --yes
  go-public <slug> --yes   last publishing step: full video and Short to public (needs the go_public gate)
  stats <videoId> [<videoId> ...]

Safety: a real send needs --yes AND a human approval gate (navaan.py approve <slug> publish_youtube). Without --yes nothing is sent, the script only prints what it would do. Default privacy is private,
so an upload can be checked before it goes public. Making a video public always needs --yes, and an agent may only
pass --yes after the user gave an explicit yes in chat for that exact video.

Setup (one time, by the user): create an OAuth client of type Desktop app in Google Cloud, enable YouTube Data API v3,
save the client JSON as ~/.config/navaan/youtube_client_secret.json (or set NAVAAN_YT_CLIENT_SECRETS). The first run opens
a browser for consent and stores a token in ~/.config/navaan/youtube_token.json (mode 600). Credentials are never put in the project.
Install: pip install google-api-python-client google-auth-oauthlib

Meta JSON keys: title, description, tags (list), language (BCP-47 such as hi or en), playlist (optional).
Shorts need no special flag: a vertical video of 60 seconds or less is treated as a Short, so keep #Shorts in the title.
"""
import os, sys, json, argparse, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import song_dir, cfg, load_json, require_approval, item_load, item_update, item_exists
import navaan_log as L
LOG = L.get("publish_youtube")

CONF = os.path.expanduser("~/.config/navaan")
SECRET = os.environ.get("NAVAAN_YT_CLIENT_SECRETS", f"{CONF}/youtube_client_secret.json")
TOKEN = os.environ.get("NAVAAN_YT_TOKEN", f"{CONF}/youtube_token.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
LANG = {"hindi": "hi", "maithili": "mai", "english": "en", "hinglish": "hi", "bhojpuri": "bho", "urdu": "ur", "punjabi": "pa"}


def service():
    try:
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError as _e:
        L.ignored(LOG, "service: ImportError (optional or expected)", _e)
        sys.exit("navaan: pip install google-api-python-client google-auth-oauthlib")
    creds = Credentials.from_authorized_user_file(TOKEN, SCOPES) if os.path.exists(TOKEN) else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(SECRET):
                sys.exit(f"navaan: client secret not found at {SECRET}. See --help for setup.")
            creds = InstalledAppFlow.from_client_secrets_file(SECRET, SCOPES).run_local_server(port=0)
        os.makedirs(CONF, exist_ok=True)
        with open(TOKEN, "w") as f: f.write(creds.to_json())
        os.chmod(TOKEN, 0o600)
    return build("youtube", "v3", credentials=creds)


def auth(a):
    """Open the browser sign-in, save the token, and print which channel it belongs to."""
    yt = service()
    items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
    print(f"token saved: {TOKEN}")
    print("signed in to channel: " + (items[0]["snippet"]["title"] if items else "(no channel yet, create one in YouTube first)"))


def body_from(meta, privacy):
    lang = meta.get("language", "")
    lang = LANG.get(lang.lower(), lang) if lang else ""
    sn = {"title": meta["title"][:100], "description": meta.get("description", ""), "tags": meta.get("tags", []), "categoryId": "10"}
    if lang:
        sn["defaultLanguage"] = lang; sn["defaultAudioLanguage"] = lang
    st = {"privacyStatus": privacy, "selfDeclaredMadeForKids": bool(cfg("publish.made_for_kids", False)),
          "containsSyntheticMedia": bool(cfg("publish.ai_disclosure", True))}
    return {"snippet": sn, "status": st}


def find_playlist(yt, name):
    tok = None
    while True:
        r = yt.playlists().list(part="snippet", mine=True, maxResults=50, pageToken=tok).execute()
        for p in r.get("items", []):
            if p["snippet"]["title"].strip().lower() == name.strip().lower(): return p["id"]
        tok = r.get("nextPageToken")
        if not tok: return None


def set_thumb(yt, vid, path, slug=None):
    """Custom thumbnails need a phone verified channel. A refusal must not fail the run, the video is already up.
    The refusal is recorded in meta.json (published.thumbnail_pending) so the portal and the next run can show it."""
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    import storage; storage.fetch_missing(path)  # the file may only be in the bucket after a local cleanup
    def mark(add):
        if not (slug and item_exists(slug)): return
        def edit(m):
            pend = [x for x in m.setdefault("published", {}).get("thumbnail_pending", []) if x["id"] != vid]
            if add: pend.append({"id": vid, "file": os.path.basename(path)})
            m["published"]["thumbnail_pending"] = pend
            if not pend: m["published"].pop("thumbnail_pending")
        item_update(slug, edit)
    try:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(path)).execute(); mark(False); print("thumbnail set")
    except HttpError as e:
        mark(True)
        print(f"warning: thumbnail not set ({e.resp.status}). Verify the channel by phone at youtube.com/verify, then run: publish_youtube.py thumb {slug or '<slug>'} {vid}")


def thumb(a):
    D = song_dir(a.slug); f = a.file or "thumb_16x9.jpg"
    set_thumb(service(), a.video_id, f if os.path.isabs(f) else os.path.join(D, f), a.slug)


def upload(a):
    D = song_dir(a.slug); meta = load_json(os.path.join(D, a.meta) if not os.path.isabs(a.meta) else a.meta)
    f = a.file if os.path.isabs(a.file) else os.path.join(D, a.file)
    import storage; storage.fetch_missing(f)  # the file may only be in the bucket after a local cleanup
    if not os.path.exists(f): sys.exit(f"navaan: missing {f}")
    if "_cap" not in os.path.basename(f) and cfg("captions.enabled", False):
        print("warning: file name has no _cap, captions may be missing. Check before publishing.")
    body = body_from(meta, a.privacy)
    if a.publish_at:
        if a.privacy != "private": sys.exit("navaan: --publish-at needs --privacy private (YouTube schedules private videos)")
        body["status"]["publishAt"] = a.publish_at
    print(json.dumps({"file": f, "size_mb": round(os.path.getsize(f) / 1e6, 1), "body": body, "playlist": a.playlist or meta.get("playlist"),
                      "thumbnail": a.thumbnail}, ensure_ascii=False, indent=2))
    if not a.yes:
        print("\nDRY RUN. Nothing sent. Re-run with --yes after the user approves this exact upload."); return
    require_approval(a.slug, "publish_youtube")
    from googleapiclient.http import MediaFileUpload
    yt = service()
    req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(f, chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st: print(f"uploaded {int(st.progress() * 100)}%", flush=True)
    vid = resp["id"]
    pl = a.playlist or meta.get("playlist")
    if a.thumbnail:
        tp = a.thumbnail if os.path.isabs(a.thumbnail) else os.path.join(D, a.thumbnail)
        set_thumb(yt, vid, tp, a.slug)
    if pl:
        pid = find_playlist(yt, pl)
        if pid: yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        else: print(f"warning: playlist not found: {pl}")
    short = "/shorts/" if "#shorts" in meta["title"].lower() else "/watch?v="
    url = f"https://youtube.com{short}{vid}" if short == "/shorts/" else f"https://youtu.be/{vid}"
    print("uploaded", vid, a.privacy, url)
    if item_exists(a.slug):
        def rec(m):
            m.setdefault("published", {}).setdefault("youtube_items", []).append({"id": vid, "url": url, "privacy": a.privacy, "file": os.path.basename(f)})
            m.setdefault("history", []).append(f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ} youtube_upload {vid} {a.privacy}")
        item_update(a.slug, rec)


def update(a):
    """Fix the metadata of a video that is already uploaded: title, description, tags, language, thumbnail, playlist. Privacy and the file are untouched."""
    D = song_dir(a.slug); meta = load_json(os.path.join(D, a.meta) if not os.path.isabs(a.meta) else a.meta)
    sn = body_from(meta, "private")["snippet"]
    print(json.dumps({"video": a.video_id, "snippet": sn, "thumbnail": a.thumbnail, "playlist": a.playlist or meta.get("playlist")}, ensure_ascii=False, indent=2))
    if not a.yes:
        print("\nDRY RUN. Nothing sent. Re-run with --yes after the user approves this exact change."); return
    from googleapiclient.http import MediaFileUpload
    yt = service()
    yt.videos().update(part="snippet", body={"id": a.video_id, "snippet": sn}).execute()
    if a.thumbnail:
        tp = a.thumbnail if os.path.isabs(a.thumbnail) else os.path.join(D, a.thumbnail)
        set_thumb(yt, a.video_id, tp, a.slug)
    pl = a.playlist or meta.get("playlist")
    if pl:
        pid = find_playlist(yt, pl)
        if pid: yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": a.video_id}}}).execute()
        else: print(f"warning: playlist not found: {pl}")
    print("updated", a.video_id)
    if item_exists(a.slug):
        item_update(a.slug, lambda m: m.setdefault("history", []).append(f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ} youtube_update {a.video_id}"))


def privacy(a):
    print(f"set {a.video_id} to {a.status}")
    if not a.yes: print("DRY RUN. Re-run with --yes after explicit user approval."); return
    require_approval(a.slug, "publish_youtube")
    yt = service()
    yt.videos().update(part="status", body={"id": a.video_id, "status": {"privacyStatus": a.status, "selfDeclaredMadeForKids": bool(cfg("publish.made_for_kids", False)),
                                                                          "containsSyntheticMedia": bool(cfg("publish.ai_disclosure", True))}}).execute()
    print("done")


def go_public(a):
    """Last publishing step: set every YouTube video of the song (the full video and the Short) to public and record it in meta.json."""
    m = item_load(a.slug, {}); pub = m.get("published", {})
    items = [("full video", i) for i in pub.get("youtube_items", [])] + ([("Short", pub["youtube_short"])] if pub.get("youtube_short", {}).get("id") else [])
    if not items: sys.exit("navaan: nothing is uploaded to YouTube yet")
    yt = service()
    live = {v["id"]: v["status"]["privacyStatus"] for v in yt.videos().list(part="status", id=",".join(i["id"] for _, i in items)).execute().get("items", [])}
    for _, i in items:
        if i["id"] in live: i["privacy"] = live[i["id"]]  # trust YouTube over meta.json
    todo = [(n, i) for n, i in items if i.get("privacy") != "public"]
    for n, i in items: print(f"{n} {i['id']}: " + (f"{i.get('privacy', '?')} -> public" if (n, i) in todo else "already public"))
    def save(note):
        priv = {i["id"]: i.get("privacy") for _, i in items if i.get("privacy")}
        def edit(cur):   # only what this step learned, on the document as it is now (an approval may have changed while we talked to YouTube)
            p = cur.get("published", {})
            for it in list(p.get("youtube_items", [])) + ([p["youtube_short"]] if isinstance(p.get("youtube_short"), dict) else []):
                if it.get("id") in priv: it["privacy"] = priv[it["id"]]
            cur.setdefault("history", []).append(f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ} {note}")
        item_update(a.slug, edit)
    if not todo: save("youtube public check: all already public"); print("nothing to change"); return
    if not a.yes: print("\nDRY RUN. Nothing changed. Re-run with --yes after you approve the go_public gate."); return
    require_approval(a.slug, "go_public")
    for n, i in todo:
        yt.videos().update(part="status", body={"id": i["id"], "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": bool(cfg("publish.made_for_kids", False)),
                                                                          "containsSyntheticMedia": bool(cfg("publish.ai_disclosure", True))}}).execute()
        i["privacy"] = "public"; print(f"{n} {i['id']} is public")
    save("youtube public " + ",".join(i["id"] for _, i in todo))


def stats(a):
    yt = service()
    r = yt.videos().list(part="statistics,snippet,status", id=",".join(a.video_ids)).execute()
    for v in r.get("items", []):
        s = v["statistics"]; print(v["id"], v["snippet"]["title"], v["status"]["privacyStatus"], {k: s.get(k) for k in ("viewCount", "likeCount", "commentCount")})


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sp = ap.add_subparsers(dest="cmd", required=True)
    u = sp.add_parser("upload"); u.add_argument("slug"); u.add_argument("--file", required=True); u.add_argument("--meta", default="tags.json")
    u.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"]); u.add_argument("--thumbnail"); u.add_argument("--playlist"); u.add_argument("--publish-at", help="RFC 3339 time such as 2026-10-20T15:00:00Z, schedules a private upload"); u.add_argument("--yes", action="store_true"); u.set_defaults(fn=upload)
    up = sp.add_parser("update"); up.add_argument("slug"); up.add_argument("video_id"); up.add_argument("--meta", default="youtube.json"); up.add_argument("--thumbnail"); up.add_argument("--playlist"); up.add_argument("--yes", action="store_true"); up.set_defaults(fn=update)
    th = sp.add_parser("thumb"); th.add_argument("slug"); th.add_argument("video_id"); th.add_argument("--file"); th.set_defaults(fn=thumb)
    gp = sp.add_parser("go-public"); gp.add_argument("slug"); gp.add_argument("--yes", action="store_true"); gp.set_defaults(fn=go_public)
    p = sp.add_parser("privacy"); p.add_argument("slug"); p.add_argument("video_id"); p.add_argument("status", choices=["private", "unlisted", "public"]); p.add_argument("--yes", action="store_true"); p.set_defaults(fn=privacy)
    au = sp.add_parser("auth", help="sign in once and save the token (uses NAVAAN_YT_TOKEN and NAVAAN_YT_CLIENT_SECRETS)"); au.set_defaults(fn=auth)
    s = sp.add_parser("stats"); s.add_argument("video_ids", nargs="+"); s.set_defaults(fn=stats)
    a = ap.parse_args(); a.fn(a)
