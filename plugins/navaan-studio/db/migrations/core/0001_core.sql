-- NAVAAN core, schema "core": people, roles, sessions, the audit trail and sign-in attempts (NAV-5, spec 002 FR-010 to FR-014, FR-020).
-- Stage 1 uses users, roles, permissions, sessions, audit_log and login_attempts. credentials, identities and user_profiles are created now (spec 002 data model) and used
-- by the listener sign-up and profile stories. The owner's password, authenticator secret, passkeys and recovery codes stay in auth.json (delivered by Vault, kept out of
-- database backups); the owner has a users row so sessions, roles and the audit trail work the same for everyone. Released: never edit, add 0002.
-- No citext: email is stored lower-case and unique on lower(email), so no extension (and no superuser) is needed.

CREATE TABLE users (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username          text NOT NULL,
  email             text,
  display_name      text,
  status            text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled', 'deleted')),
  email_verified_at timestamptz,
  locale            text,
  preferences       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_username_key ON users (lower(username));
CREATE UNIQUE INDEX users_email_key ON users (lower(email)) WHERE email IS NOT NULL;

CREATE TABLE user_profiles (
  user_id        uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
  display_name   text,
  avatar_asset_id uuid,
  bio            text,
  country        text,
  languages      text[] NOT NULL DEFAULT '{}',
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE credentials (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  kind       text NOT NULL CHECK (kind IN ('password', 'passkey', 'totp', 'recovery')),
  secret     text,
  label      text,
  last_used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX credentials_user_idx ON credentials (user_id);

CREATE TABLE identities (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  provider   text NOT NULL,
  subject    text NOT NULL,
  email      text,
  linked_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, subject)
);
CREATE INDEX identities_user_idx ON identities (user_id);

CREATE TABLE roles (
  id    smallint PRIMARY KEY,
  name  text NOT NULL UNIQUE
);
CREATE TABLE role_permissions (
  role_id     smallint NOT NULL REFERENCES roles (id) ON DELETE CASCADE,
  permission  text NOT NULL,
  PRIMARY KEY (role_id, permission)
);
CREATE TABLE user_roles (
  user_id  uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  role_id  smallint NOT NULL REFERENCES roles (id),
  artist   text NOT NULL DEFAULT '',        -- '' = everywhere; an artist slug later (catalog.artists, P4)
  PRIMARY KEY (user_id, role_id, artist)
);

INSERT INTO roles (id, name) VALUES (1, 'owner'), (2, 'editor'), (3, 'listener');
INSERT INTO role_permissions (role_id, permission) VALUES
  (1, 'studio.access'), (1, 'studio.approve'), (1, 'studio.settings'), (1, 'library.view'), (1, 'playlists.write'), (1, 'account.manage'),
  (2, 'studio.access'), (2, 'studio.approve'), (2, 'library.view'), (2, 'playlists.write'), (2, 'account.manage'),
  (3, 'library.view'), (3, 'playlists.write'), (3, 'account.manage');

CREATE TABLE sessions (
  token_hash    text PRIMARY KEY,           -- sha256 of the cookie value; the token itself is never stored
  user_id       uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  csrf_token    text NOT NULL,              -- per session, replaces the one token for the whole process
  ip            text,
  user_agent    text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  last_seen_at  timestamptz NOT NULL DEFAULT now(),
  expires_at    timestamptz NOT NULL,
  revoked_at    timestamptz
);
CREATE INDEX sessions_user_idx ON sessions (user_id);
CREATE INDEX sessions_expiry_idx ON sessions (expires_at);

CREATE TABLE audit_log (
  id        bigserial PRIMARY KEY,
  at        timestamptz NOT NULL DEFAULT now(),
  actor_id  uuid REFERENCES users (id) ON DELETE SET NULL,
  action    text NOT NULL,
  subject   text,
  ip        text,
  detail    jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX audit_log_at_idx ON audit_log (at DESC);
CREATE INDEX audit_log_actor_idx ON audit_log (actor_id, at DESC);

CREATE TABLE login_attempts (
  id   bigserial PRIMARY KEY,
  key  text NOT NULL,                       -- a client address now; an account later
  at   timestamptz NOT NULL DEFAULT now(),
  ok   boolean NOT NULL
);
CREATE INDEX login_attempts_key_idx ON login_attempts (key, at DESC);
