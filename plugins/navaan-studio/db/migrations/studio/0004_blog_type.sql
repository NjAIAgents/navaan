-- Blog items (NAV-69): one topic becomes a dev.to post, a LinkedIn article and a LinkedIn post. Type 'blog', slug blog-NNN. Adding a value works with the previous release (expand only).
ALTER TABLE items DROP CONSTRAINT items_type_check;
ALTER TABLE items ADD CONSTRAINT items_type_check CHECK (type IN ('music', 'inspiration', 'aha', 'explainer', 'podcast', 'blog'));
