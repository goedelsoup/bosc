-- Auth prefs + role audit store (#1171). Moves AUTH_PREFS off Cloudflare KV onto the same
-- Databricks Lakebase (managed Postgres) instance Stories uses (#1090) — durable identity data,
-- not edge-ephemeral state. Applied out-of-band against Lakebase in filename order (psql / the
-- Databricks SQL editor); the test harness applies the same files to an in-memory Postgres (pglite).
--
-- Why relational (the KV pain this fixes):
--   * `audit_log` is append-only history meant to be QUERIED across records — "everything that
--     happened to user Y" is a `WHERE target = $1 ORDER BY at`, not a full KV keyspace scan.
--   * `users` is a real join target: Stories keys ownership on (owner_kind='user', owner_id) with
--     nothing behind it. This is that table. (A hard stories.owner_id → users.sub FK is deferred:
--     it needs a users row guaranteed at first login, which we don't create yet — see #1171.)
--   * Nothing here wants a TTL or edge locality, so nothing about it benefited from KV.

-- One row per user we've seen authenticate (the caller's own JWT sub/email). `email` is a
-- denormalized last-seen convenience, NOT authoritative — the live Cognito claim always wins.
CREATE TABLE IF NOT EXISTS users (
  sub        TEXT PRIMARY KEY,                 -- Cognito sub (the stable user id)
  email      TEXT,                             -- last-seen email; nullable (unsubscribe has no email)
  created_at TEXT NOT NULL,                    -- ISO-8601 UTC
  updated_at TEXT NOT NULL
);

-- Per-user profile + notification preferences (was KV `prefs:<sub>`). One row per user, FK to
-- `users` so a prefs row always has a user behind it (putPrefs upserts the user in the same txn).
-- `email_verified` is deliberately NOT stored: it reflects the live Cognito JWT claim and is synced
-- on every read by the route, never persisted. Site/category lists are JSON-encoded TEXT, mirroring
-- the `sdm_json` convention in `stories` — parsed by the store, no driver array-encoding surface.
CREATE TABLE IF NOT EXISTS user_prefs (
  sub              TEXT PRIMARY KEY REFERENCES users (sub) ON DELETE CASCADE,
  display_name     TEXT,                                       -- NULL = unset
  notif_sites      TEXT NOT NULL DEFAULT '[]',                 -- JSON array of site slugs
  notif_categories TEXT NOT NULL DEFAULT '[]',                 -- JSON array of notification categories
  notif_frequency  TEXT NOT NULL DEFAULT 'immediate' CHECK (notif_frequency IN ('immediate', 'daily')),
  updated_at       TEXT NOT NULL
);

-- Immutable role-change audit trail (was KV `audit:role:<target>:<at>`). Append-only; the whole
-- point of moving off KV is that this is queryable — by target ("what happened to user Y") and by
-- actor ("every role change admin X made"). Writes are best-effort: a failure here must NOT roll
-- back the Cognito change that triggered it (the store swallows + logs, never throws to the route).
CREATE TABLE IF NOT EXISTS audit_log (
  id     TEXT PRIMARY KEY,                     -- crypto.randomUUID()
  actor  TEXT NOT NULL,                        -- Cognito sub of the admin who made the change
  target TEXT NOT NULL,                        -- Cognito sub the change was applied to
  action TEXT NOT NULL CHECK (
    action IN ('set-groups', 'set-admin-sites', 'grant-early-access', 'revoke-early-access')
  ),
  before TEXT NOT NULL,                        -- JSON array of group/site strings (prior state)
  after  TEXT NOT NULL,                        -- JSON array (resulting state)
  at     TEXT NOT NULL                         -- ISO-8601 UTC
);

-- "Everything that happened to user Y", newest first (the admin audit endpoint).
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log (target, at);
-- "Every role change actor X made" — the cross-record query KV couldn't answer (future admin views).
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log (actor, at);
