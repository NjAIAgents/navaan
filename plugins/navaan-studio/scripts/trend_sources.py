#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: what is trending for a blog's keyword, from free sources with no key: Hacker News, dev.to and Google Trends rising queries (NAV-71).

  trend_sources.py <slug>

Reads the keyword, field or area from brief.md (## Idea) and writes trend_sources.json:
{"keyword", "fetched_at", "sources": {"hacker_news"|"devto"|"google_trends": {"ok": true, "items": [...]} or {"ok": false, "error": "..."}}}.
Each source fails on its own and the step still succeeds: the blog-topics skill adds its own web search, so one rate-limited source never blocks a blog.
Google Trends has no public API; its web endpoints are used as they are and may refuse (often HTTP 429), which is recorded, not raised.
"""
import os, re, sys, json, time, http.cookiejar, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
DAYS = 14
# One cookie jar for the run: Google Trends answers 429 to a request without the NID cookie its home page sets.
_OPEN = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
_OPEN.addheaders = [("User-Agent", UA)]


def get(url, timeout=15):
    with _OPEN.open(url, timeout=timeout) as r: return r.read().decode("utf-8", "replace")


def keyword(D):
    """The text under ## Idea in brief.md, without the template's placeholder."""
    try:
        with open(os.path.join(D, "brief.md"), encoding="utf-8") as f: t = f.read()
    except OSError: return ""   # expected: no brief yet; main() then says to write the keyword
    for m in re.finditer(r"^## Idea\s*\n(.*?)(?=^## |\Z)", t, re.S | re.M):   # every Idea section: the owner may add one below the template's empty one
        k = m.group(1).strip()
        if k and not k.startswith("(write the keyword"): return " ".join(k.split())
    return ""


def hacker_news(kw, now):
    q = urllib.parse.urlencode({"query": kw, "tags": "story", "numericFilters": f"created_at_i>{int(now) - DAYS * 86400}", "hitsPerPage": 10})
    hits = json.loads(get("https://hn.algolia.com/api/v1/search?" + q)).get("hits") or []
    return [{"title": h.get("title"), "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}", "discussion": f"https://news.ycombinator.com/item?id={h.get('objectID')}",
             "points": h.get("points"), "comments": h.get("num_comments"), "created_at": h.get("created_at")} for h in hits if h.get("title")]


def devto(kw):
    tag = re.sub(r"[^a-z0-9]", "", kw.lower().split()[0]) if kw.split() else ""   # dev.to has no search API; its tags are one lowercase word
    if not tag: return []
    arts = json.loads(get("https://dev.to/api/articles?" + urllib.parse.urlencode({"tag": tag, "top": DAYS, "per_page": 10})))
    return [{"title": a.get("title"), "url": a.get("url"), "reactions": a.get("public_reactions_count"), "comments": a.get("comments_count"), "tags": a.get("tag_list"), "published_at": a.get("published_at")} for a in arts if a.get("title")]


def _gt(raw): return json.loads(raw[raw.index("{"):])   # Google prefixes its JSON with )]}' to stop it being run as a script


def daily_searches():
    """Google's daily trending searches (US), from its public RSS feed. Not tied to the keyword: the topics skill keeps only what fits."""
    import xml.etree.ElementTree as ET
    ns = {"ht": "https://trends.google.com/trending/rss"}
    root = ET.fromstring(get("https://trends.google.com/trending/rss?geo=US"))
    return [{"query": i.findtext("title"), "traffic": i.findtext("ht:approx_traffic", namespaces=ns), "daily": True} for i in root.iter("item") if i.findtext("title")][:20]


def google_trends(kw):
    """Rising related searches for the keyword over the last 7 days, worldwide (the explore call hands out a token, the related-searches call uses it).
    Google often refuses the related-searches call from a server (429); then the day's trending searches are used instead, marked "daily"."""
    try: return rising(kw)
    except (OSError, ValueError) as e:   # expected: urllib's HTTPError is an OSError; the fallback below raises on its own if it fails too
        print(f"google_trends: rising queries refused ({e}), using the daily trending searches", file=sys.stderr)
        return daily_searches()


def rising(kw):
    get("https://trends.google.com/trends/?geo=US")   # sets the cookie the API calls need
    req = {"comparisonItem": [{"keyword": kw, "geo": "", "time": "now 7-d"}], "category": 0, "property": ""}
    ex = _gt(get("https://trends.google.com/trends/api/explore?" + urllib.parse.urlencode({"hl": "en-US", "tz": 0, "req": json.dumps(req)})))
    w = next((w for w in ex.get("widgets") or [] if w.get("id") == "RELATED_QUERIES"), None)
    if not w: raise ValueError("no related-queries widget")
    rel = _gt(get("https://trends.google.com/trends/api/widgetdata/relatedsearches?" + urllib.parse.urlencode({"hl": "en-US", "tz": 0, "req": json.dumps(w["request"]), "token": w["token"]})))
    ranked = (rel.get("default") or {}).get("rankedList") or []
    rising = ranked[1].get("rankedKeyword") if len(ranked) > 1 else []
    return [{"query": r.get("query"), "rise": r.get("formattedValue")} for r in rising or [] if r.get("query")]


def collect(kw, now=None):
    now = now or time.time(); out = {}
    for name, fn in (("hacker_news", lambda: hacker_news(kw, now)), ("devto", lambda: devto(kw)), ("google_trends", lambda: google_trends(kw))):
        try: out[name] = {"ok": True, "items": fn()}
        except Exception as e:   # expected: any one free source may be down, rate-limited or changed; the others and Claude's search still give topics
            out[name] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}
    return {"keyword": kw, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "sources": out}


def main(a):
    if not a or a[0] in ("-h", "--help"): sys.exit(__doc__)
    D = C.song_dir(a[0]); kw = keyword(D)
    if not kw: sys.exit("navaan: no keyword yet. Write the keyword, field or area under ## Idea in brief.md.")
    r = collect(kw)
    with open(os.path.join(D, "trend_sources.json"), "w", encoding="utf-8") as f: json.dump(r, f, indent=2, ensure_ascii=False)
    for n, s in r["sources"].items(): print(f"{n}: {len(s['items'])} items" if s["ok"] else f"{n}: failed ({s['error']})")


if __name__ == "__main__":
    main(sys.argv[1:])
