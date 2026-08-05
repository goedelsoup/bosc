// The Databricks Lakebase (Postgres) store for user-authored Stories (epic #1090 / #1095) —
// owner-scoped CRUD with transactional writes. Every write that touches `stories` + `story_refs`
// runs inside `db.begin(...)`, one atomic Postgres transaction, so a Walk and its refs can never
// drift (a half-written Walk with stale refs is impossible).
//
// Kept driver-agnostic: a minimal `PgLike` slice (query + begin) over parameterized `$n` SQL, so the
// same store runs against postgres.js/Hyperdrive in production (functions/api/_lib/pg.ts) and an
// in-memory Postgres (pglite) in the test harness — the store never imports a driver directly.

/**
 * The slice of a Postgres driver the store uses. `query` runs one parameterized statement and
 * returns its rows (an empty array for a write with no `RETURNING`); `begin` runs `fn` inside a
 * single transaction — a throw rolls the whole thing back — passing a transaction-scoped `PgLike`.
 */
export interface PgLike {
  query<T = unknown>(text: string, params?: unknown[]): Promise<T[]>;
  begin<T>(fn: (tx: PgLike) => Promise<T>): Promise<T>;
}

export type StoryStatus = "draft" | "published";
export type StorySourceFormat = "dsl" | "mdx-data";
/** The admin moderation flag (#1098). A public read requires `ok`; `removed` is an admin takedown. */
export type StoryModeration = "ok" | "removed";

/** The Walk owner (#1092) — user-owned for this feature; the `site` case is the editorial path. */
export interface ContentOwner {
  kind: "site" | "user";
  id: string;
}

/** One cited catalog atom (a `story_refs` row) — the thin snapshot for graceful degradation. */
export interface WalkRef {
  ord: number;
  handle: string;
  kind: string;
  title: string;
}

/** A persisted `stories` row. */
export interface StoryRow {
  id: string;
  owner_kind: "site" | "user";
  owner_id: string;
  site: string;
  slug: string;
  title: string;
  dek: string;
  status: StoryStatus;
  share_id: string | null;
  source_format: StorySourceFormat;
  source_text: string;
  sdm_json: string;
  catalog_version: string;
  moderation: StoryModeration;
  published_at: string | null;
  /** 1 when the story cites a handle that no longer resolves (#1099); cleared on a clean re-save/heal. */
  stale: number;
  /** ISO-8601 of the last revalidation check, or null (#1099). */
  revalidated_at: string | null;
  created_at: string;
  updated_at: string;
}

/** One row of the report queue (#1098) — a public flag against a shared story, for admin review. */
export interface StoryReport {
  id: string;
  story_id: string;
  share_id: string;
  reason: string;
  detail: string;
  resolved: number;
  created_at: string;
}

/** The write payload — the compiled, validated Walk a Function persists (no id/timestamps). */
export interface StoryWrite {
  site: string;
  slug: string;
  title: string;
  dek: string;
  status: StoryStatus;
  source_format: StorySourceFormat;
  source_text: string;
  sdm_json: string;
  catalog_version: string;
  refs: WalkRef[];
}

const STORY_COLUMNS =
  "id, owner_kind, owner_id, site, slug, title, dek, status, share_id, source_format, source_text, sdm_json, catalog_version, moderation, published_at, stale, revalidated_at, created_at, updated_at";

/** Sticky publish state: once a story has a `share_id`/`published_at`, keep it across an
 *  unpublish→republish; otherwise mint (only when going public) from the injected candidate. */
function publishState(
  existing: { share_id: string | null; published_at: string | null } | null,
  status: StoryStatus,
  shareIdCandidate: string,
  now: string,
): { shareId: string | null; publishedAt: string | null } {
  const publishing = status === "published";
  return {
    shareId: existing?.share_id ?? (publishing ? shareIdCandidate : null),
    publishedAt: existing?.published_at ?? (publishing ? now : null),
  };
}

/** Insert every ref for a story inside a transaction — refs are replaced wholesale, not diffed. */
async function insertRefs(tx: PgLike, storyId: string, refs: WalkRef[]): Promise<void> {
  for (const r of refs) {
    await tx.query(
      "INSERT INTO story_refs (story_id, ord, handle, kind, title) VALUES ($1, $2, $3, $4, $5)",
      [storyId, r.ord, r.handle, r.kind, r.title],
    );
  }
}

/** A user's own Stories, newest first. Owner-scoped by construction. */
export async function listStories(db: PgLike, owner: ContentOwner): Promise<StoryRow[]> {
  return db.query<StoryRow>(
    `SELECT ${STORY_COLUMNS} FROM stories WHERE owner_kind = $1 AND owner_id = $2 ORDER BY updated_at DESC`,
    [owner.kind, owner.id],
  );
}

/** One owner-scoped Walk + its refs, or `null` if it isn't the owner's / doesn't exist. */
export async function getStory(
  db: PgLike,
  owner: ContentOwner,
  id: string,
): Promise<{ story: StoryRow; refs: WalkRef[] } | null> {
  const rows = await db.query<StoryRow>(
    `SELECT ${STORY_COLUMNS} FROM stories WHERE id = $1 AND owner_kind = $2 AND owner_id = $3`,
    [id, owner.kind, owner.id],
  );
  const story = rows[0];
  if (!story) return null;
  const refs = await db.query<WalkRef>(
    "SELECT ord, handle, kind, title FROM story_refs WHERE story_id = $1 ORDER BY ord",
    [id],
  );
  return { story, refs };
}

/**
 * Create a Walk + its refs atomically. `id`/`now` are injected (the Function mints the UUID and
 * timestamp) so the store stays pure/testable. The whole write is one transaction, so a ref-insert
 * failure (e.g. the unique-slug constraint) rolls the Walk insert back too.
 */
export async function createStory(
  db: PgLike,
  owner: ContentOwner,
  id: string,
  write: StoryWrite,
  now: string,
  shareIdCandidate: string,
): Promise<void> {
  const pub = publishState(null, write.status, shareIdCandidate, now);
  await db.begin(async (tx) => {
    await tx.query(
      `INSERT INTO stories (${STORY_COLUMNS})
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)`,
      [
        id,
        owner.kind,
        owner.id,
        write.site,
        write.slug,
        write.title,
        write.dek,
        write.status,
        pub.shareId, // minted here iff created as published (#1098)
        write.source_format,
        write.source_text,
        write.sdm_json,
        write.catalog_version,
        "ok", // moderation — admin-only from here
        pub.publishedAt,
        0, // stale — validated clean at write time (#1099)
        null, // revalidated_at — set by the revalidation job
        now,
        now,
      ],
    );
    await insertRefs(tx, id, write.refs);
  });
}

/**
 * Update an owner's Walk and **replace** its refs atomically. Returns `false` when the Walk
 * isn't the owner's (ownership is checked first, and the UPDATE is owner-scoped as defense in
 * depth). The UPDATE + refs DELETE/INSERT run in one transaction, so the refs can never outlive a
 * failed Walk update.
 */
export async function updateStory(
  db: PgLike,
  owner: ContentOwner,
  id: string,
  write: StoryWrite,
  now: string,
  shareIdCandidate: string,
): Promise<boolean> {
  const existing = await getStory(db, owner, id);
  if (!existing) return false;
  // Publish state is sticky (mint on first publish, keep the same share URL on republish). Moderation
  // is deliberately NOT in the SET clause — an owner edit can't clear an admin takedown (#1098).
  const pub = publishState(existing.story, write.status, shareIdCandidate, now);
  await db.begin(async (tx) => {
    await tx.query(
      `UPDATE stories SET site = $1, slug = $2, title = $3, dek = $4, status = $5, source_format = $6,
         source_text = $7, sdm_json = $8, catalog_version = $9, share_id = $10, published_at = $11, stale = 0, updated_at = $12
       WHERE id = $13 AND owner_kind = $14 AND owner_id = $15`,
      [
        write.site,
        write.slug,
        write.title,
        write.dek,
        write.status,
        write.source_format,
        write.source_text,
        write.sdm_json,
        write.catalog_version,
        pub.shareId,
        pub.publishedAt,
        now,
        id,
        owner.kind,
        owner.id,
      ],
    );
    await tx.query("DELETE FROM story_refs WHERE story_id = $1", [id]);
    await insertRefs(tx, id, write.refs);
  });
  return true;
}

/** Delete an owner's Walk (refs cascade). Returns whether a row was removed. */
export async function deleteStory(db: PgLike, owner: ContentOwner, id: string): Promise<boolean> {
  const rows = await db.query<{ id: string }>(
    "DELETE FROM stories WHERE id = $1 AND owner_kind = $2 AND owner_id = $3 RETURNING id",
    [id, owner.kind, owner.id],
  );
  return rows.length > 0;
}

// --- public read + moderation (#1098) -------------------------------------------------------

/**
 * Resolve a **published, un-removed** Walk by its public `share_id` — the only path a Walk is
 * reachable without auth. An unpublished (draft) or admin-removed Walk returns `null` (not reachable),
 * so a stale share URL leaks nothing. Owner-agnostic by design (anyone with the link may read).
 */
export async function getPublicStory(
  db: PgLike,
  shareId: string,
): Promise<{ story: StoryRow; refs: WalkRef[] } | null> {
  const rows = await db.query<StoryRow>(
    `SELECT ${STORY_COLUMNS} FROM stories WHERE share_id = $1 AND status = 'published' AND moderation = 'ok'`,
    [shareId],
  );
  const story = rows[0];
  if (!story) return null;
  const refs = await db.query<WalkRef>(
    "SELECT ord, handle, kind, title FROM story_refs WHERE story_id = $1 ORDER BY ord",
    [story.id],
  );
  return { story, refs };
}

/** Admin takedown / restore: flip a Walk's moderation flag by id. Returns whether a row changed. */
export async function setModeration(db: PgLike, id: string, moderation: StoryModeration): Promise<boolean> {
  const rows = await db.query<{ id: string }>(
    "UPDATE stories SET moderation = $1 WHERE id = $2 RETURNING id",
    [moderation, id],
  );
  return rows.length > 0;
}

/** Look up a Walk id by its share_id (any status) — the report endpoint resolves the target this way
 *  without leaking whether it's currently published. */
export async function storyIdForShareId(db: PgLike, shareId: string): Promise<string | null> {
  const rows = await db.query<{ id: string }>("SELECT id FROM stories WHERE share_id = $1", [shareId]);
  return rows[0]?.id ?? null;
}

/** File a report against a Walk (the public flag → admin review queue). */
export async function insertReport(
  db: PgLike,
  report: { id: string; storyId: string; shareId: string; reason: string; detail: string; now: string },
): Promise<void> {
  await db.query(
    "INSERT INTO story_reports (id, story_id, share_id, reason, detail, resolved, created_at) VALUES ($1, $2, $3, $4, $5, 0, $6)",
    [report.id, report.storyId, report.shareId, report.reason, report.detail, report.now],
  );
}

/** The admin review queue: open reports (or all), newest first. */
export async function listReports(
  db: PgLike,
  opts: { openOnly?: boolean; limit?: number } = {},
): Promise<StoryReport[]> {
  const limit = opts.limit ?? 100;
  const sql = opts.openOnly
    ? "SELECT id, story_id, share_id, reason, detail, resolved, created_at FROM story_reports WHERE resolved = 0 ORDER BY created_at DESC LIMIT $1"
    : "SELECT id, story_id, share_id, reason, detail, resolved, created_at FROM story_reports ORDER BY created_at DESC LIMIT $1";
  return db.query<StoryReport>(sql, [limit]);
}

/** Mark a report reviewed (resolved). Returns whether a row changed. */
export async function resolveReport(db: PgLike, reportId: string): Promise<boolean> {
  const rows = await db.query<{ id: string }>(
    "UPDATE story_reports SET resolved = 1 WHERE id = $1 RETURNING id",
    [reportId],
  );
  return rows.length > 0;
}

// --- revalidation (#1099) -------------------------------------------------------------------

/** One Walk the revalidation job needs to re-check: its stored SDM + its cited refs. */
export interface RevalidationTarget {
  id: string;
  catalog_version: string;
  sdm_json: string;
  refs: WalkRef[];
}

/** Every Walk not yet validated against the current catalog_version (the job's work-list). Skips
 *  stories already at the current version, so a no-op pass after a non-bump touches nothing. */
export async function storiesToRevalidate(db: PgLike, currentVersion: string): Promise<RevalidationTarget[]> {
  const rows = await db.query<{ id: string; catalog_version: string; sdm_json: string }>(
    "SELECT id, catalog_version, sdm_json FROM stories WHERE catalog_version != $1",
    [currentVersion],
  );
  const out: RevalidationTarget[] = [];
  for (const r of rows) {
    const refs = await db.query<WalkRef>(
      "SELECT ord, handle, kind, title FROM story_refs WHERE story_id = $1 ORDER BY ord",
      [r.id],
    );
    out.push({
      id: r.id,
      catalog_version: r.catalog_version,
      sdm_json: r.sdm_json,
      refs,
    });
  }
  return out;
}

/**
 * Apply a revalidation result to one Walk atomically: rewrite the (possibly-healed) SDM + refs, mark
 * it checked against `catalogVersion` at `now`, and set/clear the `stale` flag. One `batch`, so the
 * refs never drift from the SDM.
 */
export async function applyStoryRevalidation(
  db: PgLike,
  id: string,
  args: { sdmJson: string; refs: WalkRef[]; catalogVersion: string; stale: boolean; now: string },
): Promise<void> {
  await db.begin(async (tx) => {
    await tx.query(
      "UPDATE stories SET sdm_json = $1, catalog_version = $2, stale = $3, revalidated_at = $4 WHERE id = $5",
      [args.sdmJson, args.catalogVersion, args.stale ? 1 : 0, args.now, id],
    );
    await tx.query("DELETE FROM story_refs WHERE story_id = $1", [id]);
    await insertRefs(tx, id, args.refs);
  });
}
