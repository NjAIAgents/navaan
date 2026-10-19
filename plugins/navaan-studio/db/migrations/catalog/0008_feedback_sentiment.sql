-- NAV-68: messages sent from the public site are scored for sentiment like the platform comments. New nullable columns only (expand only).
ALTER TABLE site_feedback ADD COLUMN sentiment text CHECK (sentiment IS NULL OR sentiment IN ('positive', 'neutral', 'negative'));
ALTER TABLE site_feedback ADD COLUMN sentiment_conf double precision;
ALTER TABLE site_feedback ADD COLUMN themes text;
ALTER TABLE site_feedback ADD COLUMN tagged_at timestamptz;
