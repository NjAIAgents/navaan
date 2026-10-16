-- Visitors of the free site who asked for an account: what they like (moods, genres, languages) and an optional email for when accounts open. No address or cookie is kept. New table only: works with the previous release (expand only).
CREATE TABLE account_interest (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  moods      text[] NOT NULL DEFAULT '{}',
  genres     text[] NOT NULL DEFAULT '{}',
  languages  text[] NOT NULL DEFAULT '{}',
  email      text CHECK (email IS NULL OR length(email) <= 254),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX account_interest_created_idx ON account_interest (created_at DESC);
