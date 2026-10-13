#!/usr/bin/env python3
"""ig_market_setup.py  save the Facebook Login token that unlocks peer and hashtag data (Business Discovery).

Run it once, interactively. It asks for the token (not echoed), finds the Instagram business id behind your Facebook Page,
checks Business Discovery with a test lookup, and writes NAVAAN_IG_MARKET_USER_ID, NAVAAN_IG_MARKET_TOKEN and
NAVAAN_IG_MARKET_HOST into the login file (default ~/.config/navaan/instagram.env, or --env PATH). The token is never printed.

How to get the token: developers.facebook.com/tools/explorer, pick the app, User Token, permissions instagram_basic,
pages_show_list, pages_read_engagement, business_management. Generate, then in the Access Token Debugger press
Extend Access Token so it lasts 60 days.
"""
import os, sys, json, getpass, urllib.request, urllib.parse, urllib.error

HOST = "https://graph.facebook.com"
VER = "v21.0"


def get(path, tok, **params):
    params["access_token"] = tok
    url = f"{HOST}/{VER}/{path}?" + urllib.parse.urlencode(params)
    try:
        return json.loads(urllib.request.urlopen(url, timeout=30).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try: msg = json.loads(body)["error"]["message"]
        except Exception: msg = body[:300]
        sys.exit(f"navaan: Facebook API error {e.code}: {msg}")


def main(argv):
    env = os.path.expanduser(argv[argv.index("--env") + 1] if "--env" in argv else "~/.config/navaan/instagram.env")
    tok = getpass.getpass("Facebook user token (hidden): ").strip()
    if not tok: sys.exit("navaan: no token given")
    me = get("me", tok, fields="id,name")
    pages = get("me/accounts", tok, fields="id,name,instagram_business_account{id,username}").get("data", [])
    linked = [p for p in pages if p.get("instagram_business_account")]
    if not pages: sys.exit("navaan: this token sees no Facebook Pages. Add pages_show_list and pick the Page when Facebook asks which Pages to allow.")
    if not linked: sys.exit("navaan: the Page is not linked to an Instagram account yet. Link it (Page settings, Linked accounts, Instagram), then run again. Pages seen: " + ", ".join(p["name"] for p in pages))
    page = linked[0]; ig = page["instagram_business_account"]
    print(f"signed in as {me.get('name')}; Page '{page['name']}' is linked to @{ig.get('username')} (business id ends with ...{str(ig['id'])[-4:]})")
    scopes = get("debug_token", tok, input_token=tok).get("data", {}).get("scopes", [])
    need = ["instagram_basic", "pages_show_list", "pages_read_engagement", "business_management"]
    print("token scopes:", ", ".join(scopes) or "(none)")
    miss = [x for x in need if x not in scopes]
    if miss: sys.exit("navaan: the token lacks " + ", ".join(miss) + ". In the Graph API Explorer add them under Add a Permission, press Generate Access Token again, allow the Page, extend, rerun.")
    # the check that matters: Business Discovery on a public account
    test = get(ig["id"], tok, fields="business_discovery.username(instagram){username,followers_count}").get("business_discovery", {})
    print(f"Business Discovery works: @{test.get('username')} has {test.get('followers_count'):,} followers")
    dbg = get("debug_token", tok, input_token=tok).get("data", {})
    exp = dbg.get("expires_at") or 0
    if exp:
        import datetime; print("token expires", datetime.datetime.fromtimestamp(exp).strftime("%Y-%m-%d"), "(press Extend Access Token in the debugger if that is sooner than 60 days)")
    else: print("token has no expiry")
    lines = [l for l in (open(env, encoding="utf-8").read().splitlines() if os.path.exists(env) else []) if not l.startswith("NAVAAN_IG_MARKET_")]
    lines += [f"NAVAAN_IG_MARKET_USER_ID={ig['id']}", f"NAVAAN_IG_MARKET_TOKEN={tok}", f"NAVAAN_IG_MARKET_HOST={HOST}"]
    os.makedirs(os.path.dirname(env), exist_ok=True)
    with open(env, "w", encoding="utf-8") as f: f.write("\n".join(lines) + "\n")
    os.chmod(env, 0o600)
    print(f"saved to {env}. Next: ig_collect.py peers add @handle ..., then Collect now in the portal.")


if __name__ == "__main__":
    main(sys.argv[1:])
