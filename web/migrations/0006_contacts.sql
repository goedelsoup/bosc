-- Site-level contacts: the interactive layer (petition-connect + bulletin board).
--
-- The curated contacts DIRECTORY is a bundle feed (data/site/contacts.yaml → the `contacts` feed),
-- NOT a database table — it's committed, reviewed evidence. This migration adds only the two
-- *interactive* surfaces that reference it, on the same Databricks Lakebase the Stories/auth store
-- uses (one database, one Hyperdrive config):
--
--   * petition_connects — the routed hand-off. A reader expresses interest in a petitioner (a
--     `contacts` feed row); we capture a minimal opt-in and route it to the petitioner. Signer email
--     is PRIVATE (never surfaced publicly, never in the corpus); the public surface is a count plus
--     opt-in display names. We connect signers with petitioners — we do not warehouse signatures.
--   * bulletin_posts — a public community board scoped to a site, with the same admin-takedown
--     moderation rail as `story_reports`/`stories.moderation`.
--
-- Conventions match the Stories tables (0001/0002): TEXT PKs from crypto.randomUUID(), ISO-8601 TEXT
-- timestamps, app-enforced enums (ADD COLUMN can't carry a portable CHECK), IF NOT EXISTS. contact_id
-- is the `contacts` feed row's stable id; it is NOT a FK (the directory lives in the bundle, not PG),
-- so a contact can be re-slugged in the feed without a cascade — the connect/post keeps its recorded id.

-- The petition-connect hand-off queue. A row is one reader asking to be connected to a petitioner.
CREATE TABLE IF NOT EXISTS petition_connects (
  id           TEXT PRIMARY KEY,               -- crypto.randomUUID()
  site         TEXT NOT NULL,                  -- the network-site slug the petitioner belongs to
  contact_id   TEXT NOT NULL,                  -- the `contacts` feed row id (the petitioner)
  display_name TEXT NOT NULL DEFAULT '',       -- opt-in PUBLIC name shown beside the count (may be blank)
  email        TEXT NOT NULL,                  -- PRIVATE routing address — never surfaced publicly
  message      TEXT NOT NULL DEFAULT '',       -- optional note to the petitioner (length-capped at the edge)
  created_at   TEXT NOT NULL
);

-- The public count + opt-in-name rail reads by (site, contact_id), newest first.
CREATE INDEX IF NOT EXISTS idx_petition_connects_target ON petition_connects (site, contact_id, created_at);

-- The site bulletin board — public posts, admin-moderated.
CREATE TABLE IF NOT EXISTS bulletin_posts (
  id             TEXT PRIMARY KEY,             -- crypto.randomUUID()
  site           TEXT NOT NULL,                -- the network-site slug this post belongs to
  contact_id     TEXT NOT NULL DEFAULT '',     -- optional `contacts` feed row this post is about (blank = general)
  author_name    TEXT NOT NULL,               -- public display name of the poster
  author_contact TEXT NOT NULL DEFAULT '',    -- PRIVATE reply-to (email/phone) — never surfaced publicly
  title          TEXT NOT NULL,
  body           TEXT NOT NULL,
  moderation     TEXT NOT NULL DEFAULT 'ok',  -- app-enforced ('ok','removed'); a public read requires 'ok'
  created_at     TEXT NOT NULL
);

-- The public board reads the un-removed posts for a site, newest first.
CREATE INDEX IF NOT EXISTS idx_bulletin_posts_site ON bulletin_posts (site, moderation, created_at);
