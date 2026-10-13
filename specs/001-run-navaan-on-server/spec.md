# Feature Specification: Run NAVAAN on the Oracle VM at navaan.njlabs.dev

**Feature Branch**: `001-run-navaan-on-server` (no git branch created; the spec directory carries the number)

**Created**: 2026-10-13

**Status**: Clarified (3 questions answered 2026-10-13)

**Input**: User description: "Run NAVAAN on the Oracle VM at navaan.njlabs.dev, behind login, with credentials in Vault. NAVAAN only for now."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open NAVAAN from anywhere and sign in safely (Priority: P1)

The owner opens https://navaan.njlabs.dev from any device and sees only a sign-in page. On the first visit, a one-time setup creates the login (password, authenticator app, recovery codes) and needs proof of control over the server. After signing in with a password and a second factor, the owner sees the same studio they use on the Mac.

**Why this priority**: Nothing else is useful or safe until the studio is reachable and protected. The studio can publish to YouTube and Instagram, so exposure without protection is the main risk.

**Independent Test**: Visit the address in a fresh browser: only the sign-in page loads, over a valid secure connection. Complete first-time setup, sign out, sign in again with a password plus authenticator code, and with a recovery code.

**Acceptance Scenarios**:

1. **Given** no login exists, **When** the owner visits the address, **Then** a setup page asks for a one-time setup code that only someone with access to the server can read.
2. **Given** a login exists and no session, **When** anyone requests any page, media file or data call, **Then** they receive the sign-in page or a "sign in" refusal and no studio content.
3. **Given** five wrong attempts from one network address, **When** that address tries again, **Then** it is temporarily locked out while the owner from another address can still sign in.
4. **Given** the owner is idle for two hours or 12 hours have passed, **When** they use the studio, **Then** they must sign in again.

---

### User Story 2 - Scheduled posts go out with the Mac off (Priority: P1)

The owner schedules a song for a chosen time and approves the required gates. At that time the server publishes to YouTube and Instagram without the Mac being awake or online.

**Why this priority**: This is the main reason to move to a server.

**Independent Test**: Schedule a low-stakes test post a few minutes ahead with the Mac asleep; confirm it is published at the time and the history shows it.

**Acceptance Scenarios**:

1. **Given** a scheduled item with all gates approved, **When** the time arrives, **Then** it is published once and recorded.
2. **Given** a missing approval at the time, **When** the time passes, **Then** nothing is published, the item shows "waiting for approval", and it fires after approval or is marked missed after the grace period.
3. **Given** the Mac studio and the server studio both exist, **When** a time arrives, **Then** only one of them publishes.

---

### User Story 3 - Platform credentials kept in the secret manager (Priority: P2)

YouTube, Instagram, cloud storage and login-secret material live in the existing secret manager, not in loose files on the server's disk. When a token refreshes, the new value is kept and survives restarts.

**Why this priority**: A public server holding long-lived publishing tokens in plain files is the largest damage if the server is compromised.

**Independent Test**: Restart the studio and confirm it still publishes; confirm no credential files exist in the studio's persistent storage; confirm a refreshed token is still valid after restart.

**Acceptance Scenarios**:

1. **Given** the secret manager is available, **When** the studio starts, **Then** it obtains only the secrets it needs and nothing else.
2. **Given** the secret manager is sealed or unreachable, **When** the studio starts, **Then** it waits and retries instead of failing, and says so on the sign-in or status page.
3. **Given** a token refreshes during use, **When** the studio restarts, **Then** the refreshed token is used.

---

### User Story 4 - Build and publish everything that does not need the Mac (Priority: P2)

The owner runs the pipeline on the server: lyrics and captions steps with Claude, local video rendering, analytics collection, and publishing. Steps that need the owner's own browser (Suno import, Flow visuals, first-time platform sign-in) are clearly marked as Mac-only with instructions on how to hand over the result.

**Why this priority**: The server is only as useful as the share of the pipeline it can run.

**Independent Test**: Run a short song with own pictures from lyrics through render on the server; confirm the output matches what the Mac produces within normal tolerance and that Mac-only steps show clear guidance.

**Acceptance Scenarios**:

1. **Given** a song with a lyrics file and pictures, **When** the owner starts the pipeline, **Then** the video is rendered on the server.
2. **Given** a Mac-only step is next, **When** the owner views the song, **Then** the page explains what to do on the Mac and how to upload the result.

---

### User Story 5 - Move existing work over without loss (Priority: P3)

Existing songs, analytics history, configuration and platform sign-ins move from the Mac to the server. Nothing is lost, and the Mac keeps working as a fallback.

**Why this priority**: Needed to cut over, but it is a one-time activity.

**Independent Test**: Compare song lists, analytics totals and gate states before and after; open a migrated song and play it.

**Acceptance Scenarios**:

1. **Given** the Mac data set, **When** the move completes, **Then** every song, approval, schedule and analytics history is present on the server.
2. **Given** the move is done, **When** the owner decides to roll back, **Then** the Mac studio works unchanged.

---

### User Story 6 - Share the VM safely with the existing apps (Priority: P3)

The existing apps on the VM keep running with no change in behaviour. Adding or removing NAVAAN can be done without redoing their setup.

**Why this priority**: Other apps on the same machine matter to the owner's work.

**Independent Test**: Before and after the change, confirm the other apps respond and their certificates are unchanged; remove NAVAAN and confirm they still do.

**Acceptance Scenarios**:

1. **Given** NAVAAN is added, **When** the other apps are checked, **Then** their addresses, certificates and configuration are unchanged except for the single addition needed to route NAVAAN.
2. **Given** NAVAAN is removed, **When** the other apps are checked, **Then** they work as before.

---

### Edge Cases

- The secret manager is sealed after a server restart: the studio waits, shows status, and resumes when unsealed.
- The server certificate nears expiry: renewal works without taking other apps down, and expiry is noticed before it happens.
- The owner loses the phone with the authenticator app: a recovery code or a documented reset restores access.
- The server restarts during a render or a publish: the item resumes or fails visibly; it is never published twice.
- A platform token expires (Google test-mode tokens expire weekly): the studio says which sign-in is needed and where to do it.
- Large uploads (pictures, audio) over the public address fail visibly, not silently.
- Both the Mac and the server schedulers are running.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The studio MUST be reachable at https://navaan.njlabs.dev over a valid, automatically renewed secure connection, and over no other hostname.
- **FR-002**: Every page, media file and data request MUST require a signed-in session, except the sign-in and first-time setup pages.
- **FR-003**: Sign-in MUST require a password and a second factor (authenticator code, passkey, or one-time recovery code).
- **FR-004**: First-time setup MUST require a one-time code readable only by someone with access to the server.
- **FR-005**: Failed sign-in attempts MUST be limited per network address, so a stranger cannot lock the owner out.
- **FR-006**: Sessions MUST end after 12 hours or two hours of inactivity, and session cookies MUST be marked secure.
- **FR-007**: Gates MUST remain human-only on the server exactly as on the Mac.
- **FR-008**: Scheduled publishing MUST run on the server without the Mac, and MUST publish each item at most once even when another studio instance exists.
- **FR-009**: Platform credentials MUST be kept in the secret manager, and the studio MUST only be able to read its own secrets.
- **FR-010**: Refreshed tokens MUST be written back to the secret manager so they survive restarts.
- **FR-011**: If the secret manager is sealed or unreachable, the studio MUST wait and retry, and show a clear status.
- **FR-012**: Claude-driven steps MUST run on the server using a credential the owner provides; the studio MUST show which credential type is in use.
- **FR-013**: Steps that need the owner's browser MUST be clearly marked and offer a way to supply the result.
- **FR-014**: Existing songs, approvals, schedules, configuration and analytics history MUST be transferable without loss, and the Mac studio MUST keep working as a fallback.
- **FR-015**: Adding NAVAAN MUST NOT change the behaviour, addresses or certificates of the other apps on the VM; removal MUST restore the earlier state.
- **FR-016**: Studio data MUST be backed up so it can be restored after a server loss.
- **FR-017**: A shared password prompt MUST be shown before the sign-in page is served, so that visitors without it see nothing of the studio. The prompt has its own failed-attempt limit and its password is kept in the secret manager.
- **FR-018**: Claude-driven steps on the server MUST use the owner's Claude subscription through a long-lived token kept in the secret manager. The studio MUST show when that token is missing, expired or rate limited, and the owner MUST be able to switch to a pay-per-use key without other changes. Always-on server use of a subscription is subject to Anthropic's terms, which the owner accepts responsibility for checking.
- **FR-019**: Analytics and studio data MUST stay in the current file-based database for this feature, stored on persistent storage and covered by the backup in FR-016. Moving to a separate database service is out of scope here and is a later feature.

### Key Entities

- **Owner account**: the single login with password, authenticator, passkeys and recovery codes.
- **Session**: a signed-in period bound to a device, with an expiry and an idle limit.
- **Platform credential**: a token or key for YouTube, Instagram, cloud storage or Claude, with an expiry date.
- **Schedule**: a chosen publish time for an item with its status (waiting, done, missed, blocked).
- **Studio data set**: songs, approvals, analytics history and configuration that must move and be backed up.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A fresh browser reaches the sign-in page at the public address over a valid secure connection in under 3 seconds.
- **SC-002**: 100% of requests without a session are refused, including media and data requests, in an automated check.
- **SC-003**: A test post scheduled with the Mac switched off is published within 2 minutes of the chosen time.
- **SC-004**: After a full server restart with the secret manager unsealed, the studio is usable again within 5 minutes without manual file copying.
- **SC-005**: Zero platform credentials exist as files in the studio's persistent storage in an audit.
- **SC-006**: Before and after adding NAVAAN, all existing apps respond and keep their certificates, with zero downtime beyond a few seconds at the moment of the one routing change.
- **SC-007**: After the move, 100% of songs and analytics rows match the Mac counts.
- **SC-008**: A 30-second song renders on the server in under 10 minutes.
- **SC-009**: The owner can restore the studio data set to a new server from backup in under 1 hour.

## Assumptions

- The owner is the only user; there is one login.
- Scope is NAVAAN only; the other apps stay on their current hostnames and are not changed beyond the single routing addition.
- The domain's DNS is managed at the registrar the owner already uses, and the name points at the server.
- The existing secret manager is available, unsealed by the owner after restarts, and NAVAAN gets its own area in it.
- The server is an ARM Linux machine with enough CPU and memory to render videos.
- Platform sign-ins that need a browser (YouTube) are done on the Mac and moved over.
- Steps driven by the owner's Chrome (Suno import, Flow visuals) stay Mac-only.
- A single-host certificate is used; no wildcard.
- The shared password in front is a convenience gate, not a replacement for the studio login.
- Google platform tokens stay subject to the weekly expiry until the OAuth app is published.

## Clarifications

### Session 2026-10-13

- Q: Extra gate in front of the sign-in page? -> A: Shared password in front (FR-017).
- Q: Claude credential on the server? -> A: Subscription token, with a documented switch to an API key (FR-018).
- Q: Database in this feature? -> A: Keep the current file database; container database is a later feature (FR-019).
