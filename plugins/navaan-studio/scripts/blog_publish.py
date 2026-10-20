#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-20
Last updated: 2026-10-20
Description: post a finished blog post from the Posts tab through the APIs (NAV-78): the article to dev.to, and a short post with a link card to LinkedIn.

  devto_post(slug, publish=False)   create the article on dev.to (a draft unless publish), or update the one already made; an article that is live stays live
  linkedin_post(slug)               post linkedin_post.md to the owner's LinkedIn profile with the dev.to article as a link card (cover as its picture); once only
  status(D, meta)                   what the Posts tab needs: is a key saved, what has been posted and where

dev.to:    POST https://dev.to/api/articles (PUT .../{id} to update), header api-key, body {"article": {title, body_markdown, published, tags, main_image, description}}
LinkedIn:  POST https://api.linkedin.com/rest/posts, headers Authorization, X-Restli-Protocol-Version 2.0.0, Linkedin-Version YYYYMM; a picture goes up first through /rest/images (initializeUpload, then a PUT of the bytes).
LinkedIn has no API for long-form articles (checked in the Posts API reference): the LinkedIn article stays copy and paste.
The keys are the owner's own, saved in Settings (devto.env, linkedin.env), kept in Vault, never logged or returned. Every network call goes through HTTP(), so tests never reach out.
"""
import os, sys, re, json, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
import media_cfg
LOG = L.get("blog_publish")

DEVTO = "https://dev.to/api/articles"
LINKEDIN = "https://api.linkedin.com/rest"
LINKEDIN_VERSION = "202610"   # YYYYMM; LinkedIn supports each version for about a year (override with blog.linkedin_version in navaan.config.json)
PLACEHOLDER = "[ARTICLE_URL]"
MARKER = re.compile(r"[ \t]?\[c\d+\]")
FRONT = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.S)


def HTTP(method, url, headers=None, body=None, timeout=30):
    """(status, response headers as a lower-case dict, bytes). A refusal is returned, not raised, so the caller can say what the site said."""
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
    except urllib.error.HTTPError as e: return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()   # expected: a refusal is an answer; the caller turns it into a sentence


def _p(D, n): return os.path.join(D, n)


def _read(D, n):
    with open(_p(D, n), encoding="utf-8") as f: return MARKER.sub("", f.read())


def _said(status, raw, secret=""):
    """What the site answered, in a sentence, with the key taken out."""
    try:
        d = json.loads(raw.decode("utf-8", "replace")); msg = d.get("error") or d.get("message") or d.get("detail") or json.dumps(d)[:200]
        if isinstance(msg, dict): msg = json.dumps(msg)[:200]
    except ValueError: msg = raw.decode("utf-8", "replace")[:200]   # expected: not every refusal is JSON
    return str(msg).replace(secret, "<key>") if secret else str(msg)


def front(text):
    """(front matter as a dict, the body) of a dev.to draft."""
    m = FRONT.match(text); fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line: k, v = line.split(":", 1); fm[k.strip()] = v.strip().strip("\"'")
    return fm, (text[m.end():] if m else text).strip()


def devto_article(D, publish):
    """The article as dev.to takes it: title, body without the front matter, tags as one comma list (at most 4), the cover (set by the images step), the description."""
    fm, body = front(_read(D, "devto.md"))
    if not fm.get("title"): raise ValueError("The dev.to post has no title. Add it on the Posts tab.")
    tags = ",".join(t.strip() for t in fm.get("tags", "").split(",") if t.strip())
    a = {"title": fm["title"], "body_markdown": body, "published": bool(publish), "tags": tags, "description": fm.get("description", "")}
    if fm.get("cover_image"): a["main_image"] = fm["cover_image"]
    return {"article": a}


# ---------- dev.to ----------
def devto_post(slug, publish=False):
    D = C.song_dir(slug); key = media_cfg.get_key("devto")
    if not key: raise ValueError("Add your dev.to key in Settings first (dev.to, Settings, Extensions, API keys).")
    meta = C.item_load(slug, {}) or {}; prev = (meta.get("published") or {}).get("devto") or {}
    live = bool(publish or prev.get("published"))   # an article that is already live stays live: saving must not unpublish it
    payload = devto_article(D, live); hdr = {"api-key": key, "Content-Type": "application/json", "Accept": "application/vnd.forem.api-v1+json", "User-Agent": "navaan-studio"}
    status, _, raw = HTTP("PUT" if prev.get("id") else "POST", f"{DEVTO}/{prev['id']}" if prev.get("id") else DEVTO, hdr, payload)
    if status == 401: raise RuntimeError("dev.to refused the key (401). Paste it again in Settings.")
    if status == 404 and prev.get("id"): raise RuntimeError("dev.to no longer has the article it made earlier (404). Delete it from the record or make a new one.")
    if status not in (200, 201): raise RuntimeError(f"dev.to said no (HTTP {status}): {_said(status, raw, key)}")
    try: a = json.loads(raw.decode("utf-8", "replace"))
    except ValueError: a = {}   # expected: an answer that is not JSON has no article in it, which is reported just below
    if not a.get("id") or not a.get("url"): raise RuntimeError("dev.to answered without the article's address. Check dev.to before posting again.")
    info = {"id": a["id"], "url": a["url"], "published": live, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "updated": bool(prev.get("id"))}
    meta.setdefault("published", {})["devto"] = info; C.item_save(slug, meta)
    L.event(LOG, "info", "devto_posted", item=slug, article=a["id"], published=live, updated=info["updated"])
    return info


# ---------- LinkedIn ----------
def _li_headers(token, json_body=True):
    h = {"Authorization": "Bearer " + token, "X-Restli-Protocol-Version": "2.0.0", "Linkedin-Version": str(C.cfg("blog.linkedin_version", LINKEDIN_VERSION)), "User-Agent": "navaan-studio"}
    if json_body: h["Content-Type"] = "application/json"
    return h


def _linkedin_image(token, author, path):
    """Upload a picture and return its URN (urn:li:image:...): ask for an upload address, then PUT the bytes. RuntimeError when LinkedIn says no."""
    st, _, raw = HTTP("POST", LINKEDIN + "/images?action=initializeUpload", _li_headers(token), {"initializeUploadRequest": {"owner": author}})
    if st not in (200, 201): raise RuntimeError(f"LinkedIn would not take the picture (HTTP {st}): {_said(st, raw, token)}")
    v = json.loads(raw.decode("utf-8", "replace")).get("value") or {}
    if not v.get("uploadUrl") or not v.get("image"): raise RuntimeError("LinkedIn gave no upload address for the picture")
    with open(path, "rb") as f: data = f.read()
    st, _, raw = HTTP("PUT", v["uploadUrl"], {"Authorization": "Bearer " + token, "Content-Type": "application/octet-stream"}, data, timeout=120)
    if st not in (200, 201): raise RuntimeError(f"LinkedIn would not take the picture bytes (HTTP {st})")
    return v["image"]


def linkedin_text(D, url):
    """The post text with the dev.to address in it (where [ARTICLE_URL] stands, else at the end)."""
    t = _read(D, "linkedin_post.md").strip()
    if not t: raise ValueError("The LinkedIn post is empty.")
    t = t.replace(PLACEHOLDER, url) if PLACEHOLDER in t else t + "\n\n" + url
    if len(t) > 3000: raise ValueError(f"A LinkedIn post can have 3,000 characters; this one has {len(t):,}.")
    return t


def linkedin_post(slug):
    D = C.song_dir(slug); token = media_cfg.get_key("linkedin"); author = media_cfg.linkedin_author()
    if not token or not author: raise ValueError("Add your LinkedIn token and member id in Settings first.")
    meta = C.item_load(slug, {}) or {}; pub = meta.get("published") or {}
    if (pub.get("linkedin_post") or {}).get("url"): raise ValueError("This post is already on LinkedIn: " + pub["linkedin_post"]["url"])
    dv = pub.get("devto") or {}
    if not (dv.get("url") and dv.get("published")): raise ValueError("Publish the dev.to article first: the LinkedIn post links to it.")
    text = linkedin_text(D, dv["url"]); fm, _ = front(_read(D, "devto.md")) if os.path.exists(_p(D, "devto.md")) else ({}, "")
    body = {"author": author, "commentary": text, "visibility": "PUBLIC", "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []}, "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
    cover = _p(D, "post_cover_linkedin.png"); card = False
    if os.path.exists(cover):   # the article as a link card with the cover (LinkedIn does not read the page itself, so the card is built here)
        try:
            thumb = _linkedin_image(token, author, cover)
            body["content"] = {"article": {"source": dv["url"], "thumbnail": thumb, "title": fm.get("title") or "Read the article", "description": (fm.get("description") or "")[:240]}}; card = True
        except (RuntimeError, OSError, ValueError) as e:
            L.event(LOG, "warning", "linkedin_card_skipped", item=slug, reason=str(e)[:200])   # the post still goes out, as text with the link in it
    st, h, raw = HTTP("POST", LINKEDIN + "/posts", _li_headers(token), body)
    if st == 401: raise RuntimeError("LinkedIn refused the token (401): it has expired or is wrong. Make a new one in Settings.")
    if st == 403: raise RuntimeError("LinkedIn refused the post (403): the token needs the w_member_social permission (Share on LinkedIn).")
    if st != 201: raise RuntimeError(f"LinkedIn said no (HTTP {st}): {_said(st, raw, token)}")
    pid = h.get("x-restli-id", "")
    if not pid: raise RuntimeError("LinkedIn accepted the post but gave no post id. Check your LinkedIn feed before posting again.")
    info = {"id": pid, "url": f"https://www.linkedin.com/feed/update/{pid}/", "card": card, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    meta = C.item_load(slug, {}) or {}; meta.setdefault("published", {})["linkedin_post"] = info; C.item_save(slug, meta)
    L.event(LOG, "info", "linkedin_posted", item=slug, post=pid, card=card)
    return info


def status(D, meta):
    """For the Posts tab: what is possible and what is done, without any key in it."""
    pub = (meta or {}).get("published") or {}; dv = pub.get("devto") or {}; li = pub.get("linkedin_post") or {}
    return {"devto": {"key": bool(media_cfg.get_key("devto")), "posted": bool(dv.get("id")), "published": bool(dv.get("published")), "url": dv.get("url", "")},
            "linkedin": {"key": bool(media_cfg.get_key("linkedin") and media_cfg.linkedin_author()), "posted": bool(li.get("url")), "url": li.get("url", ""), "ready": bool(dv.get("published")),
                         "text": os.path.exists(_p(D, "linkedin_post.md"))}}
