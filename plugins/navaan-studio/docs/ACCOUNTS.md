# Accounts and logins, from scratch

Everything the portal needs to publish and to read analytics lives in `~/.config/navaan` (mode 600, never in the repo) and in
`navaan.config.json` (gitignored). The Settings page of the portal (http://127.0.0.1:8765/#/settings) shows the state of every
login and does the saving; this file is the walkthrough behind its buttons.

## Files

| File | What |
|---|---|
| `~/.config/navaan/instagram.env` | NAVAAN Instagram login: `NAVAAN_IG_USER_ID`, `NAVAAN_IG_TOKEN`, `NAVAAN_IG_HOST=https://graph.instagram.com`, `NAVAAN_IG_TOKEN_EXPIRES`, plus the optional market keys `NAVAAN_IG_MARKET_USER_ID`, `NAVAAN_IG_MARKET_TOKEN`, `NAVAAN_IG_MARKET_HOST=https://graph.facebook.com`, `NAVAAN_IG_MARKET_EXPIRES` |
| `~/.config/navaan/instagram_<type>.env` | the same for another content type (for example `inspiration`) |
| `~/.config/navaan/youtube_client_secret.json` | Google OAuth client (Desktop app), shared by every account |
| `~/.config/navaan/youtube_token.json`, `youtube_token_<type>.json` | one Google sign-in per channel |
| `navaan.config.json` → `accounts.<type>` | `instagram_handle`, `youtube_channel`, `instagram_env`, `youtube_token`, `youtube_client_secret` |

Music (NAVAAN) uses the default files. Every other type gets its own block and its own files, so nothing can post to the wrong channel.
Settings, "Add a content type" writes the block.

## Instagram (publishing and own analytics)

1. The Instagram account must be Professional (Creator or Business): Instagram app, Settings, Account type and tools.
2. Meta app: developers.facebook.com/apps, app `navaan-studio`, Use cases, Instagram API, Customize.
3. App Roles, Instagram Testers: add the Instagram account. In the Instagram app accept the invite (Settings, Website permissions
   or Apps and websites, Tester invites).
4. Customize, "API setup with Instagram login", section 2 "Generate access tokens": add the account, Generate token, copy.
5. Settings page, that account, Instagram: paste, Save. The portal checks it against `/me`, verifies the username matches the
   account's handle, writes the file, records a 60 day expiry.
6. Every 60 days: Settings, Refresh (any time after the token is a day old). No Meta visit needed.

Permissions on the Instagram API use case: `instagram_business_basic`, `instagram_business_manage_comments`,
`instagram_business_manage_insights`, `instagram_business_content_publish`.

## Facebook token (peer benchmarks, optional, once per workspace)

Business Discovery only exists on the Facebook Login graph, which reaches Instagram through a Facebook Page.

1. Create a Facebook Page (any name, can stay unpublished). Page settings, Linked accounts, Instagram: link the NAVAAN account.
2. App `navaan-studio`, Use cases, Customize, Permissions and features: Add `instagram_basic`, `instagram_manage_insights`,
   `pages_show_list`, `pages_read_engagement`, `business_management`.
3. developers.facebook.com/tools/explorer: Meta App `navaan-studio`, Get User Access Token, tick those five, Generate Access Token,
   allow the Page and the Instagram account in the popup.
4. developers.facebook.com/tools/debug/accesstoken: paste, Debug, Extend Access Token (60 days), copy the extended token.
5. Settings page, Peer data (Facebook): paste, Save. The portal finds the Instagram business id behind the Page, proves Business
   Discovery with one lookup, writes the `NAVAAN_IG_MARKET_*` keys. Do this on the music account; the inspiration file gets the
   same keys (copy the three lines) so both collector runs can read peers.
6. Hashtag search needs Meta's "Instagram Public Content Access" app review. Not done; hashtag volumes stay off.

CLI equivalent: `python3 plugins/navaan-studio/scripts/ig_market_setup.py` (asks for the token, hidden).
Peers: `python3 plugins/navaan-studio/scripts/ig_collect.py peers add|remove|list @name`.

## YouTube

1. console.cloud.google.com: a project, APIs and Services, Library, enable "YouTube Data API v3".
2. OAuth consent screen: External, app name and support email, Test users: every Google account that owns a channel.
3. Credentials, Create credentials, OAuth client ID, Desktop app, Download JSON. Settings page, Google OAuth client, Choose File.
   It is saved as `~/.config/navaan/youtube_client_secret.json`.
4. Settings page, that account, "Sign in with Google". A browser window opens on this computer; pick the Google account of that
   channel, allow. The token lands in that account's `youtube_token*.json`.
   CLI: `NAVAAN_YT_TOKEN=~/.config/navaan/youtube_token_<type>.json python3 plugins/navaan-studio/scripts/publish_youtube.py auth`
5. While the consent screen is in Testing, Google expires the sign-in after 7 days. Settings shows "sign in again" when that
   happens. To stop it: OAuth consent screen, Publish app. No verification is needed for your own channels; Google shows an
   "unverified app" screen once at sign-in.

## Cloud bucket

`navaan.config.json`: `storage.cloud_provider` (oci, s3 or gcs), `storage.cloud_bucket`, `storage.cloud_region`, `storage.cloud_prefix`.
The provider CLI (`oci`, `aws` or `gcloud`) must be logged in; the portal never stores those credentials.
