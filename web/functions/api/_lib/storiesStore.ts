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
  created_at: string;
  updated_at: string;
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
  "id, owner_kind, owner_id, site, slug, title, dek, status, share_id, source_format, source_text, sdm_json, catalog_version, created_at, updated_at";

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
): Promise<void> {
  await db.batch([
    db
      .prepare(`INSERT INTO stories (${STORY_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .bind(
        id,
        owner.kind,
        owner.id,
        write.site,
        write.slug,
        write.title,
        write.dek,
        write.status,
        null, // share_id — populated on publish (#1098)
        write.source_format,
        write.source_text,
        write.sdm_json,
        write.catalog_version,
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
): Promise<boolean> {
  const existing = await getStory(db, owner, id);
  if (!existing) return false;
  await db.batch([
    db
      .prepare(
        `UPDATE stories SET site = ?, slug = ?, title = ?, dek = ?, status = ?, source_format = ?,
           source_text = ?, sdm_json = ?, catalog_version = ?, updated_at = ?
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
