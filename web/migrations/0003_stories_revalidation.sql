-- User-authored Stories: catalog revalidation / handle stability (epic #1090 / #1099).
-- Keeps stored Story references honest as the corpus evolves. On a `catalog_version` bump, a job
-- walks `story_refs`, re-resolves each handle against the new catalog, auto-heals renamed handles,
-- and flags the rest so the author is nudged (the public render already degrades, #1096/#1097).

-- `stale`: 1 when the story cites a handle that no longer resolves (and no rename healed it). Cleared
-- to 0 on a successful owner re-save (the write path rejects dangling handles) or when a rename heals
-- the last dangling ref. App-enforced 0/1.
ALTER TABLE stories ADD COLUMN stale INTEGER NOT NULL DEFAULT 0;
-- The last time the revalidation job checked this story (NULL until first checked). Lets the job skip
-- stories already validated against the current catalog_version.
ALTER TABLE stories ADD COLUMN revalidated_at TEXT;

-- The revalidation job scans stories not yet validated against the current catalog_version.
CREATE INDEX IF NOT EXISTS idx_stories_catalog_version ON stories (catalog_version);
