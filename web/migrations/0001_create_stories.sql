-- User-authored Stories store (epic #1090 / #1095). Databricks Lakebase (managed Postgres) — the
-- first relational store, reached from the Workers runtime through a Cloudflare Hyperdrive binding.
-- Applied out-of-band against Lakebase (psql / the Databricks SQL editor) in filename order; the
-- test harness applies the same files to an in-memory Postgres (pglite). See web/functions/README.md.
--
-- `stories` holds one row per Story on the owner axis (#1092); `story_refs` is one row per cited
-- catalog atom (#1093) — the inverse index ("which Stories cite handle X"), the DB analog of the
-- editorial `anchorRecordRels`. The stored `sdm_json` is the pre-validated render artifact (#1094);
-- `source_text` + `source_format` are the editable source the write path recompiles from.

CREATE TABLE IF NOT EXISTS stories (
  id              TEXT PRIMARY KEY,                 -- crypto.randomUUID()
  owner_kind      TEXT NOT NULL CHECK (owner_kind IN ('site', 'user')),
  owner_id        TEXT NOT NULL,                    -- user: Cognito sub; site: network-site slug
  site            TEXT NOT NULL,                    -- the network site the Story reads over
  slug            TEXT NOT NULL,                    -- URL segment, unique per (owner, site)
  title           TEXT NOT NULL,
  dek             TEXT NOT NULL DEFAULT '',
  status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
  share_id        TEXT UNIQUE,                      -- unguessable public id; NULL until shared (#1098)
  source_format   TEXT NOT NULL CHECK (source_format IN ('dsl', 'mdx-data')),
  source_text     TEXT NOT NULL,                    -- the editable Story source
  sdm_json        TEXT NOT NULL,                    -- the compiled, validated SDM (render artifact)
  catalog_version TEXT NOT NULL DEFAULT '',         -- the catalog the handles were validated against (#1099)
  created_at      TEXT NOT NULL,                    -- ISO-8601 UTC
  updated_at      TEXT NOT NULL
);

-- List a user's own Stories, newest first (the account page + owner-scoped reads).
CREATE INDEX IF NOT EXISTS idx_stories_owner ON stories (owner_kind, owner_id, updated_at);
-- A Story slug is unique within an owner + site (no two of my Stories share a slug on one site).
CREATE UNIQUE INDEX IF NOT EXISTS idx_stories_owner_slug ON stories (owner_kind, owner_id, site, slug);

CREATE TABLE IF NOT EXISTS story_refs (
  story_id TEXT NOT NULL REFERENCES stories (id) ON DELETE CASCADE,
  ord      INTEGER NOT NULL,                        -- position in the Story, for stable ordering
  handle   TEXT NOT NULL,                           -- <kind>:<site>:<localId> (the live pointer)
  kind     TEXT NOT NULL,                           -- thin snapshot (graceful degradation)
  title    TEXT NOT NULL,
  PRIMARY KEY (story_id, ord)
);

-- The inverse index: "which Stories cite this atom?" (revalidation #1099, backlinks).
CREATE INDEX IF NOT EXISTS idx_story_refs_handle ON story_refs (handle);
