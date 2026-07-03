-- User-authored Stories: public sharing + moderation (epic #1090 / #1098).
-- Adds the moderation rail on top of the #1095 store. `share_id` (the unguessable public id) already
-- exists on `stories`; this migration adds the takedown flag + a first-published timestamp, and a
-- report queue for admin review.

-- `moderation`: an admin takedown flag. A public read requires status='published' AND moderation='ok',
-- so an admin flip to 'removed' takes a story down instantly (the kill switch is coarser, per-feature).
-- App-enforced to ('ok','removed') — ADD COLUMN can't carry the 0001-style CHECK portably.
ALTER TABLE stories ADD COLUMN moderation TEXT NOT NULL DEFAULT 'ok';
-- When the story first went public (NULL while it has never been published). Kept sticky across an
-- unpublish→republish so the "shared since" line is stable.
ALTER TABLE stories ADD COLUMN published_at TEXT;

-- The report queue: a public visitor can flag a shared story; an admin reviews + takes down.
CREATE TABLE IF NOT EXISTS story_reports (
  id         TEXT PRIMARY KEY,                 -- crypto.randomUUID()
  story_id   TEXT NOT NULL REFERENCES stories (id) ON DELETE CASCADE,
  share_id   TEXT NOT NULL,                    -- the public id the report came in against
  reason     TEXT NOT NULL,                    -- a closed reason code (app-validated)
  detail     TEXT NOT NULL DEFAULT '',         -- optional free-text (length-capped at the edge)
  resolved   INTEGER NOT NULL DEFAULT 0,       -- 0 open, 1 reviewed
  created_at TEXT NOT NULL
);

-- The admin review queue reads open reports newest-first.
CREATE INDEX IF NOT EXISTS idx_story_reports_open ON story_reports (resolved, created_at);
CREATE INDEX IF NOT EXISTS idx_story_reports_story ON story_reports (story_id);
