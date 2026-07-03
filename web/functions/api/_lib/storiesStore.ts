// The D1 store for user-authored Stories (epic #1090 / #1095) — owner-scoped CRUD with
// transactional writes. Every write that touches `stories` + `story_refs` goes through
// `db.batch([...])`, which D1 runs as one atomic transaction, so a Story and its refs can never
// drift (a half-written Story with stale refs is impossible).
//
// Kept dependency-light: a minimal `D1Like` slice (no @cloudflare/workers-types), so the store is
// unit-testable against an in-memory SQLite adapter (node:sqlite) in the test harness.

/** The slice of the D1 API we use. `batch` is D1's atomic-transaction primitive. */
export interface D1Result<T = unknown> {
  results?: T[];
  success: boolean;
  meta?: { changes?: number };
}
export interface D1PreparedStatement {
  bind(...values: unknown[]): D1PreparedStatement;
  first<T = unknown>(): Promise<T | null>;
  all<T = unknown>(): Promise<D1Result<T>>;
  run(): Promise<D1Result>;
}
export interface D1Like {
  prepare(sql: string): D1PreparedStatement;
  batch(statements: D1PreparedStatement[]): Promise<D1Result[]>;
}

export type StoryStatus = "draft" | "published";
export type StorySourceFormat = "dsl" | "mdx-data";
/** The admin moderation flag (#1098). A public read requires `ok`; `removed` is an admin takedown. */
export type StoryModeration = "ok" | "removed";

/** The Story owner (#1092) — user-owned for this feature; the `site` case is the editorial path. */
export interface StoryOwner {
  kind: "site" | "user";
  id: string;
}

/** One cited catalog atom (a `story_refs` row) — the thin snapshot for graceful degradation. */
export interface StoryRef {
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

/** The write payload — the compiled, validated Story a Function persists (no id/timestamps). */
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
  refs: StoryRef[];
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

/** One INSERT statement per ref — replaced wholesale on every write (not diffed). */
function refInserts(db: D1Like, storyId: string, refs: StoryRef[]): D1PreparedStatement[] {
  return refs.map((r) =>
    db
      .prepare("INSERT INTO story_refs (story_id, ord, handle, kind, title) VALUES (?, ?, ?, ?, ?)")
      .bind(storyId, r.ord, r.handle, r.kind, r.title),
  );
}

/** A user's own Stories, newest first. Owner-scoped by construction. */
export async function listStories(db: D1Like, owner: StoryOwner): Promise<StoryRow[]> {
  const res = await db
    .prepare(
      `SELECT ${STORY_COLUMNS} FROM stories WHERE owner_kind = ? AND owner_id = ? ORDER BY updated_at DESC`,
    )
    .bind(owner.kind, owner.id)
    .all<StoryRow>();
  return res.results ?? [];
}

/** One owner-scoped Story + its refs, or `null` if it isn't the owner's / doesn't exist. */
export async function getStory(
  db: D1Like,
  owner: StoryOwner,
  id: string,
): Promise<{ story: StoryRow; refs: StoryRef[] } | null> {
  const story = await db
    .prepare(`SELECT ${STORY_COLUMNS} FROM stories WHERE id = ? AND owner_kind = ? AND owner_id = ?`)
    .bind(id, owner.kind, owner.id)
    .first<StoryRow>();
  if (!story) return null;
  const refs = await db
    .prepare("SELECT ord, handle, kind, title FROM story_refs WHERE story_id = ? ORDER BY ord")
    .bind(id)
    .all<StoryRef>();
  return { story, refs: refs.results ?? [] };
}

/**
 * Create a Story + its refs atomically. `id`/`now` are injected (the Function mints the UUID and
 * timestamp) so the store stays pure/testable. The whole write is one `batch`, so a ref-insert
 * failure (e.g. the unique-slug constraint) rolls the Story insert back too.
 */
export async function createStory(
  db: D1Like,
  owner: StoryOwner,
  id: string,
  write: StoryWrite,
  now: string,
  shareIdCandidate: string,
): Promise<void> {
  const pub = publishState(null, write.status, shareIdCandidate, now);
  await db.batch([
    db
      .prepare(
        `INSERT INTO stories (${STORY_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .bind(
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
      ),
    ...refInserts(db, id, write.refs),
  ]);
}

/**
 * Update an owner's Story and **replace** its refs atomically. Returns `false` when the Story
 * isn't the owner's (ownership is checked first, and the UPDATE is owner-scoped as defense in
 * depth). The UPDATE + refs DELETE/INSERT run in one `batch`, so the refs can never outlive a
 * failed Story update.
 */
export async function updateStory(
  db: D1Like,
  owner: StoryOwner,
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
  await db.batch([
    db
      .prepare(
        `UPDATE stories SET site = ?, slug = ?, title = ?, dek = ?, status = ?, source_format = ?,
           source_text = ?, sdm_json = ?, catalog_version = ?, share_id = ?, published_at = ?, stale = 0, updated_at = ?
         WHERE id = ? AND owner_kind = ? AND owner_id = ?`,
      )
      .bind(
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
      ),
    db.prepare("DELETE FROM story_refs WHERE story_id = ?").bind(id),
    ...refInserts(db, id, write.refs),
  ]);
  return true;
}

/** Delete an owner's Story (refs cascade). Returns whether a row was removed. */
export async function deleteStory(db: D1Like, owner: StoryOwner, id: string): Promise<boolean> {
  const res = await db
    .prepare("DELETE FROM stories WHERE id = ? AND owner_kind = ? AND owner_id = ?")
    .bind(id, owner.kind, owner.id)
    .run();
  return (res.meta?.changes ?? 0) > 0;
}

// --- public read + moderation (#1098) -------------------------------------------------------

/**
 * Resolve a **published, un-removed** Story by its public `share_id` — the only path a Story is
 * reachable without auth. An unpublished (draft) or admin-removed Story returns `null` (not reachable),
 * so a stale share URL leaks nothing. Owner-agnostic by design (anyone with the link may read).
 */
export async function getPublicStory(
  db: D1Like,
  shareId: string,
): Promise<{ story: StoryRow; refs: StoryRef[] } | null> {
  const story = await db
    .prepare(
      `SELECT ${STORY_COLUMNS} FROM stories WHERE share_id = ? AND status = 'published' AND moderation = 'ok'`,
    )
    .bind(shareId)
    .first<StoryRow>();
  if (!story) return null;
  const refs = await db
    .prepare("SELECT ord, handle, kind, title FROM story_refs WHERE story_id = ? ORDER BY ord")
    .bind(story.id)
    .all<StoryRef>();
  return { story, refs: refs.results ?? [] };
}

/** Admin takedown / restore: flip a Story's moderation flag by id. Returns whether a row changed. */
export async function setModeration(db: D1Like, id: string, moderation: StoryModeration): Promise<boolean> {
  const res = await db.prepare("UPDATE stories SET moderation = ? WHERE id = ?").bind(moderation, id).run();
  return (res.meta?.changes ?? 0) > 0;
}

/** Look up a Story id by its share_id (any status) — the report endpoint resolves the target this way
 *  without leaking whether it's currently published. */
export async function storyIdForShareId(db: D1Like, shareId: string): Promise<string | null> {
  const row = await db
    .prepare("SELECT id FROM stories WHERE share_id = ?")
    .bind(shareId)
    .first<{ id: string }>();
  return row?.id ?? null;
}

/** File a report against a Story (the public flag → admin review queue). */
export async function insertReport(
  db: D1Like,
  report: { id: string; storyId: string; shareId: string; reason: string; detail: string; now: string },
): Promise<void> {
  await db
    .prepare(
      "INSERT INTO story_reports (id, story_id, share_id, reason, detail, resolved, created_at) VALUES (?, ?, ?, ?, ?, 0, ?)",
    )
    .bind(report.id, report.storyId, report.shareId, report.reason, report.detail, report.now)
    .run();
}

/** The admin review queue: open reports (or all), newest first. */
export async function listReports(
  db: D1Like,
  opts: { openOnly?: boolean; limit?: number } = {},
): Promise<StoryReport[]> {
  const limit = opts.limit ?? 100;
  const sql = opts.openOnly
    ? "SELECT id, story_id, share_id, reason, detail, resolved, created_at FROM story_reports WHERE resolved = 0 ORDER BY created_at DESC LIMIT ?"
    : "SELECT id, story_id, share_id, reason, detail, resolved, created_at FROM story_reports ORDER BY created_at DESC LIMIT ?";
  const res = await db.prepare(sql).bind(limit).all<StoryReport>();
  return res.results ?? [];
}

/** Mark a report reviewed (resolved). Returns whether a row changed. */
export async function resolveReport(db: D1Like, reportId: string): Promise<boolean> {
  const res = await db.prepare("UPDATE story_reports SET resolved = 1 WHERE id = ?").bind(reportId).run();
  return (res.meta?.changes ?? 0) > 0;
}

// --- revalidation (#1099) -------------------------------------------------------------------

/** One Story the revalidation job needs to re-check: its stored SDM + its cited refs. */
export interface RevalidationTarget {
  id: string;
  catalog_version: string;
  sdm_json: string;
  refs: StoryRef[];
}

/** Every Story not yet validated against the current catalog_version (the job's work-list). Skips
 *  stories already at the current version, so a no-op pass after a non-bump touches nothing. */
export async function storiesToRevalidate(db: D1Like, currentVersion: string): Promise<RevalidationTarget[]> {
  const rows = await db
    .prepare("SELECT id, catalog_version, sdm_json FROM stories WHERE catalog_version != ?")
    .bind(currentVersion)
    .all<{ id: string; catalog_version: string; sdm_json: string }>();
  const out: RevalidationTarget[] = [];
  for (const r of rows.results ?? []) {
    const refs = await db
      .prepare("SELECT ord, handle, kind, title FROM story_refs WHERE story_id = ? ORDER BY ord")
      .bind(r.id)
      .all<StoryRef>();
    out.push({
      id: r.id,
      catalog_version: r.catalog_version,
      sdm_json: r.sdm_json,
      refs: refs.results ?? [],
    });
  }
  return out;
}

/**
 * Apply a revalidation result to one Story atomically: rewrite the (possibly-healed) SDM + refs, mark
 * it checked against `catalogVersion` at `now`, and set/clear the `stale` flag. One `batch`, so the
 * refs never drift from the SDM.
 */
export async function applyStoryRevalidation(
  db: D1Like,
  id: string,
  args: { sdmJson: string; refs: StoryRef[]; catalogVersion: string; stale: boolean; now: string },
): Promise<void> {
  await db.batch([
    db
      .prepare(
        "UPDATE stories SET sdm_json = ?, catalog_version = ?, stale = ?, revalidated_at = ? WHERE id = ?",
      )
      .bind(args.sdmJson, args.catalogVersion, args.stale ? 1 : 0, args.now, id),
    db.prepare("DELETE FROM story_refs WHERE story_id = ?").bind(id),
    ...refInserts(db, id, args.refs),
  ]);
}
