-- NAVAAN billing, schema "billing": what a plan includes and which plan a person is on (NAV-7). Entitlements only: no payment provider, no card data (FR-021).
-- Everything a screen or an endpoint asks goes through entitlements.can(); changing a limit here changes it everywhere with no code or screen change (SC-008).
-- Users live in schema core and are referenced by id without a foreign key (the schemas are migrated and tested separately). Released: never edit, add 0002.

CREATE TABLE plans (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  key          text NOT NULL UNIQUE CHECK (key ~ '^[a-z][a-z0-9_]*$'),
  name         text NOT NULL,
  price_minor  integer CHECK (price_minor >= 0),          -- NULL: no price yet (Premium cannot be bought)
  currency     text,
  interval     text CHECK (interval IN ('month', 'year')),
  active       boolean NOT NULL DEFAULT true,
  sort         smallint NOT NULL DEFAULT 0,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE plan_entitlements (
  plan_id    uuid NOT NULL REFERENCES plans (id) ON DELETE CASCADE,
  feature    text NOT NULL,                               -- playlists.max, audio.play, audio.quality_hi, offline, ads.off
  enabled    boolean NOT NULL DEFAULT true,
  limit_int  integer CHECK (limit_int >= 0),              -- NULL with enabled: no limit
  PRIMARY KEY (plan_id, feature)
);

CREATE TABLE subscriptions (
  id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                   uuid NOT NULL,
  plan_id                   uuid NOT NULL REFERENCES plans (id),
  status                    text NOT NULL CHECK (status IN ('trialing', 'active', 'past_due', 'canceled')),
  period_start              timestamptz,
  period_end                timestamptz,
  cancel_at                 timestamptz,
  provider                  text,                          -- empty until a provider is chosen
  provider_customer_id      text,
  provider_subscription_id  text,
  created_at                timestamptz NOT NULL DEFAULT now(),
  updated_at                timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX subscriptions_one_live_idx ON subscriptions (user_id) WHERE status IN ('trialing', 'active', 'past_due');
CREATE INDEX subscriptions_plan_idx ON subscriptions (plan_id);

-- An exception granted by the owner for one person and one feature (a bigger limit, a switched-on feature), with the reason, optionally until a date.
CREATE TABLE entitlement_overrides (
  user_id     uuid NOT NULL,
  feature     text NOT NULL,
  enabled     boolean,
  limit_int   integer CHECK (limit_int >= 0),
  reason      text NOT NULL,
  expires_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, feature)
);

-- What each person with a live subscription may do: their plan's entitlements with their overrides on top.
CREATE VIEW v_user_entitlements AS
  SELECT s.user_id, p.key AS plan, e.feature, COALESCE(o.enabled, e.enabled) AS enabled, COALESCE(o.limit_int, e.limit_int) AS limit_int
  FROM subscriptions s
  JOIN plans p ON p.id = s.plan_id
  JOIN plan_entitlements e ON e.plan_id = s.plan_id
  LEFT JOIN entitlement_overrides o ON o.user_id = s.user_id AND o.feature = e.feature AND (o.expires_at IS NULL OR o.expires_at > now())
  WHERE s.status IN ('trialing', 'active', 'past_due');

INSERT INTO plans (key, name, sort) VALUES ('free', 'Free', 1), ('premium', 'Premium', 2);
INSERT INTO plan_entitlements (plan_id, feature, enabled, limit_int)
  SELECT p.id, f.feature, f.enabled, f.limit_int FROM plans p JOIN (VALUES
    ('free', 'playlists.max', true, 3), ('free', 'audio.play', true, NULL), ('free', 'library.save', true, NULL),
    ('free', 'audio.quality_hi', false, NULL), ('free', 'offline', false, NULL), ('free', 'ads.off', false, NULL),
    ('premium', 'playlists.max', true, NULL), ('premium', 'audio.play', true, NULL), ('premium', 'library.save', true, NULL),
    ('premium', 'audio.quality_hi', true, NULL), ('premium', 'offline', true, NULL), ('premium', 'ads.off', true, NULL)
  ) AS f(plan, feature, enabled, limit_int) ON f.plan = p.key;
