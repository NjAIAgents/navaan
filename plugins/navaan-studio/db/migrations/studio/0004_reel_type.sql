-- Reels: the owner's own footage edited into an Instagram reel; its items are type 'reel' (slug reel-NNN). Adding a value works with the previous release (expand only).
ALTER TABLE items DROP CONSTRAINT items_type_check;
ALTER TABLE items ADD CONSTRAINT items_type_check CHECK (type IN ('music', 'inspiration', 'aha', 'reel', 'explainer', 'podcast'));
