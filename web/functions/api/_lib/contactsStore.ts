// The Databricks Lakebase (Postgres) store for the interactive site-contacts surfaces — the
// petition-connect hand-off queue and the site bulletin board. Reuses the same driver-agnostic
// `PgLike` slice as the Stories store (functions/api/_lib/storiesStore.ts), so the same SQL runs
// against postgres.js/Hyperdrive in production and pglite (in-memory Postgres) in tests.
//
// DISCIPLINE: petition-connect is about *connecting a signer with a petitioner*, not warehousing
// signatures. A signer's `email` is private routing — it never leaves this store toward the public
// surface. The public projection (publicConnectTally / publicBulletinPost) drops it.

import type { PgLike } from "./storiesStore";

export type { PgLike } from "./storiesStore";

/** The admin moderation flag for a bulletin post. A public read requires `ok`; `removed` is a takedown. */
export type BulletinModeration = "ok" | "removed";

/** A persisted `petition_connects` row (private — carries the signer email). */
export interface PetitionConnectRow {
  id: string;
  site: string;
  contact_id: string;
  display_name: string;
  email: string;
  message: string;
  created_at: string;
}

/** A persisted `bulletin_posts` row (private — carries the author reply-to). */
export interface BulletinPostRow {
  id: string;
  site: string;
  contact_id: string;
  author_name: string;
  author_contact: string;
  title: string;
  body: string;
  moderation: BulletinModeration;
  created_at: string;
}

const CONNECT_COLUMNS = "id, site, contact_id, display_name, email, message, created_at";
const BULLETIN_COLUMNS =
  "id, site, contact_id, author_name, author_contact, title, body, moderation, created_at";

// --- petition-connect ----------------------------------------------------------------------

/** The public tally for one petitioner: a total count + the opt-in display names (blanks dropped). */
export interface ConnectTally {
  contact_id: string;
  count: number;
  names: string[];
}

/**
 * Record one petition-connect. `id`/`now` are injected (the Function mints the UUID + timestamp) so
 * the store stays pure/testable. A single INSERT — no transaction needed (one table, one row).
 */
export async function insertPetitionConnect(
  db: PgLike,
  connect: {
    id: string;
    site: string;
    contactId: string;
    displayName: string;
    email: string;
    message: string;
    now: string;
  },
): Promise<void> {
  await db.query(`INSERT INTO petition_connects (${CONNECT_COLUMNS}) VALUES ($1, $2, $3, $4, $5, $6, $7)`, [
    connect.id,
    connect.site,
    connect.contactId,
    connect.displayName,
    connect.email,
    connect.message,
    connect.now,
  ]);
}

/** How many opt-in display names the public tally surfaces (the count is exact; the roster is capped). */
const TALLY_NAMES_LIMIT = 100;

/**
 * The PUBLIC tally for a petitioner — the exact count of connects plus a bounded roster of the opt-in
 * display names, newest first. The count is a `COUNT(*)` (so the public read never scans every row),
 * and the names are a separate `LIMIT`ed query filtered to non-blank in SQL. Never selects `email`
 * (private routing).
 */
export async function publicConnectTally(db: PgLike, site: string, contactId: string): Promise<ConnectTally> {
  const countRows = await db.query<{ n: number }>(
    `SELECT COUNT(*)::int AS n FROM petition_connects WHERE site = $1 AND contact_id = $2`,
    [site, contactId],
  );
  const nameRows = await db.query<{ display_name: string }>(
    `SELECT display_name FROM petition_connects
     WHERE site = $1 AND contact_id = $2 AND TRIM(display_name) <> ''
     ORDER BY created_at DESC LIMIT $3`,
    [site, contactId, TALLY_NAMES_LIMIT],
  );
  return {
    contact_id: contactId,
    count: Number(countRows[0]?.n ?? 0),
    names: nameRows.map((r) => r.display_name),
  };
}

/**
 * The ADMIN view of connects for a site (or one petitioner) — the FULL rows, including the private
 * email, so a site-admin/petitioner can act on the hand-off. Newest first. Admin-guarded by the caller.
 */
export async function listConnectsForAdmin(
  db: PgLike,
  site: string,
  opts: { contactId?: string; limit?: number } = {},
): Promise<PetitionConnectRow[]> {
  const limit = opts.limit ?? 200;
  if (opts.contactId) {
    return db.query<PetitionConnectRow>(
      `SELECT ${CONNECT_COLUMNS} FROM petition_connects WHERE site = $1 AND contact_id = $2 ORDER BY created_at DESC LIMIT $3`,
      [site, opts.contactId, limit],
    );
  }
  return db.query<PetitionConnectRow>(
    `SELECT ${CONNECT_COLUMNS} FROM petition_connects WHERE site = $1 ORDER BY created_at DESC LIMIT $2`,
    [site, limit],
  );
}

// --- bulletin board ------------------------------------------------------------------------

/** Create a bulletin post. `id`/`now` injected; a single INSERT (moderation starts `ok`). */
export async function insertBulletinPost(
  db: PgLike,
  post: {
    id: string;
    site: string;
    contactId: string;
    authorName: string;
    authorContact: string;
    title: string;
    body: string;
    now: string;
  },
): Promise<void> {
  await db.query(
    `INSERT INTO bulletin_posts (${BULLETIN_COLUMNS})
     VALUES ($1, $2, $3, $4, $5, $6, $7, 'ok', $8)`,
    [
      post.id,
      post.site,
      post.contactId,
      post.authorName,
      post.authorContact,
      post.title,
      post.body,
      post.now,
    ],
  );
}

/**
 * The PUBLIC board for a site — un-removed posts, newest first. Never selects `author_contact`
 * (private reply-to). Capped so a hot board can't return an unbounded page.
 */
export async function listPublicBulletinPosts(
  db: PgLike,
  site: string,
  limit = 100,
): Promise<Omit<BulletinPostRow, "author_contact" | "moderation">[]> {
  return db.query<Omit<BulletinPostRow, "author_contact" | "moderation">>(
    `SELECT id, site, contact_id, author_name, title, body, created_at
     FROM bulletin_posts WHERE site = $1 AND moderation = 'ok' ORDER BY created_at DESC LIMIT $2`,
    [site, limit],
  );
}

/** The ADMIN view of a site's board — the FULL rows (incl. private reply-to + removed posts). */
export async function listBulletinPostsForAdmin(
  db: PgLike,
  site: string,
  limit = 200,
): Promise<BulletinPostRow[]> {
  return db.query<BulletinPostRow>(
    `SELECT ${BULLETIN_COLUMNS} FROM bulletin_posts WHERE site = $1 ORDER BY created_at DESC LIMIT $2`,
    [site, limit],
  );
}

/** Admin takedown / restore: flip a post's moderation flag by id. Returns whether a row changed. */
export async function setBulletinModeration(
  db: PgLike,
  id: string,
  moderation: BulletinModeration,
): Promise<boolean> {
  const rows = await db.query<{ id: string }>(
    "UPDATE bulletin_posts SET moderation = $1 WHERE id = $2 RETURNING id",
    [moderation, id],
  );
  return rows.length > 0;
}
