-- Visitor analytics of the public site (NAV-33): page views, plays with the seconds listened, and clicks on the account pitch. Cookieless and anonymous:
-- `visitor` is a one-way hash of address and browser with a salt that lives only in the server's memory and changes every day, so it counts
-- unique visitors per day and cannot be linked across days or back to anyone. No address, cookie or browser string is kept. New table only (expand only).
CREATE TABLE site_events (
  id         bigserial PRIMARY KEY,
  day        date NOT NULL,
  kind       text NOT NULL CHECK (kind IN ('view', 'play', 'pitch')),
  slug       text CHECK (slug IS NULL OR length(slug) <= 80),
  source     text NOT NULL DEFAULT 'direct' CHECK (length(source) <= 20),
  device     text NOT NULL DEFAULT 'desktop' CHECK (device IN ('mobile', 'tablet', 'desktop')),
  visitor    text NOT NULL CHECK (length(visitor) = 16),
  seconds    integer NOT NULL DEFAULT 0 CHECK (seconds BETWEEN 0 AND 3600),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX site_events_day_idx ON site_events (day);
CREATE INDEX site_events_slug_day_idx ON site_events (slug, day) WHERE slug IS NOT NULL;
