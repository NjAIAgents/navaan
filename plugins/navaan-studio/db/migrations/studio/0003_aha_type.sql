-- The Aha-lorithm (NAV-67): a second short-form channel, its items are type 'aha' (slug aha-NNN). Adding a value works with the previous release (expand only).
ALTER TABLE items DROP CONSTRAINT items_type_check;
ALTER TABLE items ADD CONSTRAINT items_type_check CHECK (type IN ('music', 'inspiration', 'aha', 'explainer', 'podcast'));
