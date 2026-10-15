#!/usr/bin/env python3
"""publish_instagram.py  publish a Reel with the official Instagram Graph API (content publishing).

  publish <slug> --video-url https://... [--caption-file publish/instagram_<slug>.txt] [--cover-url https://...] [--share-to-feed] [--yes]
  status <container_id>
  limit

Safety: a real send needs --yes AND a human approval gate (navaan.py approve <slug> publish_instagram). Without --yes nothing is sent. An agent may pass --yes only after an explicit user yes for this exact reel.

Requirements (set up by the user, not by an agent):
  1. Instagram professional account (Business or Creator).
  2. A Meta developer app with permission instagram_business_content_publish (Instagram Login) or instagram_content_publish (Facebook Login).
  3. Environment: NAVAAN_IG_USER_ID (Instagram account id) and NAVAAN_IG_TOKEN (access token). Keep them out of the project and out of chat.
  4. The video must be reachable at a public https URL while Meta fetches it. Use a temporary pre-authenticated link from your bucket (see oci_public_url.sh).
Optional env: NAVAAN_IG_HOST (default https://graph.facebook.com; use https://graph.instagram.com for Instagram Login) and NAVAAN_IG_API_VERSION (default v21.0, set to the current version).
Flow: create container (media_type REELS), poll status_code until FINISHED, then media_publish. Reels must be 9:16, up to 90 seconds.
"""
import os, sys, json, time, argparse, urllib.request, urllib.parse, urllib.error, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import song_dir, load_json, require_approval, item_load, item_update, item_exists
import navaan_log as L
LOG = L.get("publish_instagram")

def _load_env_file():
    """Read ~/.config/navaan/instagram.env (KEY=VALUE lines, mode 600) so the token never lives in the project. Real environment variables win."""
    p = os.environ.get("NAVAAN_IG_ENV", os.path.expanduser("~/.config/navaan/instagram.env"))
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k.startswith("NAVAAN_IG_") and v: os.environ.setdefault(k, v)


_load_env_file()
HOST = os.environ.get("NAVAAN_IG_HOST", "https://graph.facebook.com")
VER = os.environ.get("NAVAAN_IG_API_VERSION", "v21.0")


def env():
    uid, tok = os.environ.get("NAVAAN_IG_USER_ID"), os.environ.get("NAVAAN_IG_TOKEN")
    if not uid or not tok: sys.exit("navaan: set NAVAAN_IG_USER_ID and NAVAAN_IG_TOKEN in your shell or in ~/.config/navaan/instagram.env (not in the project, not in chat).")
    return uid, tok


def call(method, path, tok, params=None):
    url = f"{HOST}/{VER}/{path}"; data = None; params = dict(params or {}); params["access_token"] = tok
    if method == "GET": url += "?" + urllib.parse.urlencode(params)
    else: data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method), timeout=60) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        L.ignored(LOG, "call: HTTPError (optional or expected)", e)
        sys.exit(f"navaan: Instagram API error {e.code}: {e.read().decode()[:500]}")


def publish(a):
    D = song_dir(a.slug)
    cap = open(a.caption_file if os.path.isabs(a.caption_file) else os.path.join(D, a.caption_file), encoding="utf-8").read().strip() if a.caption_file else ""
    if not a.video_url.startswith("https://"): sys.exit("navaan: --video-url must be a public https URL")
    try:  # the caption should carry the full song link itself, the bio has none
        pub = ((item_load(a.slug, {}) or {}).get("published") or {})
        yt = ((pub.get("youtube_items") or [{}])[0].get("url") or "")
        if "link in bio" in cap.lower() or (yt and yt not in cap and "youtu" not in cap):
            print(f"WARNING: the caption does not carry the full YouTube link ({yt or 'none yet'}). Rewrite it with: navaan.py caption {a.slug} --feedback \"put the YouTube link in the caption, not link in bio\"", file=sys.stderr)
    except Exception as _e: L.soft(LOG, "publish_error"); pass
    plan = {"video_url": a.video_url[:80] + "...", "caption": cap, "share_to_feed": a.share_to_feed, "cover_url": a.cover_url}
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not a.yes: print("\nDRY RUN. Nothing sent. Re-run with --yes after the user approves this exact reel."); return
    require_approval(a.slug, "publish_instagram")
    uid, tok = env()
    p = {"media_type": "REELS", "video_url": a.video_url, "caption": cap, "share_to_feed": str(a.share_to_feed).lower()}
    if a.cover_url: p["cover_url"] = a.cover_url
    cid = call("POST", f"{uid}/media", tok, p)["id"]; print("container", cid)
    for _ in range(10):
        time.sleep(30); sc = call("GET", cid, tok, {"fields": "status_code"})["status_code"]; print("status", sc)
        if sc == "FINISHED": break
        if sc in ("ERROR", "EXPIRED"): sys.exit("navaan: container failed: " + sc)
    else: sys.exit("navaan: container not finished after 5 minutes. Check status later with the status command.")
    mid = call("POST", f"{uid}/media_publish", tok, {"creation_id": cid})["id"]
    link = call("GET", mid, tok, {"fields": "permalink"}).get("permalink", "")
    print("published", mid, link)
    if item_exists(a.slug):
        def rec(m):
            m.setdefault("published", {})["instagram"] = link or mid
            m.setdefault("history", []).append(f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ} instagram_publish {mid}")
        item_update(a.slug, rec)


def status(a):
    uid, tok = env(); print(call("GET", a.container_id, tok, {"fields": "status_code"}))


def limit(a):
    uid, tok = env(); print(call("GET", f"{uid}/content_publishing_limit", tok, {"fields": "quota_usage,config"}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("publish"); p.add_argument("slug"); p.add_argument("--video-url", required=True); p.add_argument("--caption-file"); p.add_argument("--cover-url")
    p.add_argument("--share-to-feed", action="store_true"); p.add_argument("--yes", action="store_true"); p.set_defaults(fn=publish)
    s = sp.add_parser("status"); s.add_argument("container_id"); s.set_defaults(fn=status)
    l = sp.add_parser("limit"); l.set_defaults(fn=limit)
    a = ap.parse_args(); a.fn(a)
