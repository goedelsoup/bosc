// The Databricks Lakebase (Postgres) store for auth prefs + the role-change audit trail (#1171) —
// the durable identity data that used to live in the AUTH_PREFS KV namespace (per-user profile +
// notification prefs under `prefs:<sub>`, role-change records under `audit:role:<sub>:<at>`). It's
// not edge-ephemeral state (no TTL, no need for edge locality), and the audit trail is append-only
// history meant to be queried across records — so it belongs relationally, next to Stories (#1090).
//
// Kept driver-agnostic on the same `PgLike` slice as `storiesStore.ts`, so the same SQL runs against
// postgres.js/Hyperdrive in production (`pg.ts`) and pglite in the test harness — the store never
// imports a driver directly.

import type { PgLike } from "./storiesStore";

export const VALID_CATEGORIES = ["tip", "correction", "new_source", "hypothesis"] as const;
export type NotifCategory = (typeof VALID_CATEGORIES)[number];

export const VALID_FREQUENCIES = ["immediate", "daily"] as const;
export type NotifFrequency = (typeof VALID_FREQUENCIES)[number];

export interface UserPrefs {
  display_name?: string;
  notifications: {
    sites: string[];
    categories: NotifCategory[];
    frequency: NotifFrequency;
    /** Reflects the Cognito email_verified claim; synced on read, never persisted / patchable. */
    email_verified: boolean;
  };
}

const DEFAULT_NOTIFICATIONS: UserPrefs["notifications"] = {
  sites: [],
  categories: [],
  frequency: "immediate",
  email_verified: false,
};

/** Parse a JSON-array TEXT column back to a string[]; tolerates malformed/non-array values. */
function parseStringArray(raw: string): string[] {
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

/** The stored `user_prefs` row (email_verified is NOT a column — it's JWT-derived). */
interface PrefsRow {
  display_name: string | null;
  notif_sites: string;
  notif_categories: string;
  notif_frequency: string;
}

/**
 * A user's profile + notification prefs, or defaults when no row exists (a first-time reader). The
 * returned `email_verified` is always the `false` default here — the route overwrites it from the
 * live JWT before responding, exactly as the KV path did.
 */
export async function getPrefs(db: PgLike, sub: string): Promise<UserPrefs> {
  const rows = await db.query<PrefsRow>(
    "SELECT display_name, notif_sites, notif_categories, notif_frequency FROM user_prefs WHERE sub = $1",
    [sub],
  );
  const row = rows[0];
  if (!row) return { notifications: { ...DEFAULT_NOTIFICATIONS } };
  const freq = VALID_FREQUENCIES.includes(row.notif_frequency as NotifFrequency)
    ? (row.notif_frequency as NotifFrequency)
    : "immediate";
  return {
    display_name: row.display_name ?? undefined,
    notifications: {
      sites: parseStringArray(row.notif_sites),
      categories: parseStringArray(row.notif_categories).filter((c): c is NotifCategory =>
        VALID_CATEGORIES.includes(c as NotifCategory),
      ),
      frequency: freq,
      email_verified: false,
    },
  };
}

/**
 * Upsert a user's prefs (and the backing `users` row) atomically. `now`/`email` are injected by the
 * route — `email` is the caller's own JWT email when available (opportunistic denormalization; a
 * null never clobbers a previously-known email). `email_verified` is intentionally not persisted.
 */
export async function putPrefs(
  db: PgLike,
  sub: string,
  prefs: UserPrefs,
  now: string,
  email?: string,
): Promise<void> {
  const displayName = prefs.display_name ?? null;
  const sites = JSON.stringify(prefs.notifications.sites);
  const categories = JSON.stringify(prefs.notifications.categories);
  const frequency = prefs.notifications.frequency;
  await db.begin(async (tx) => {
    await tx.query(
      `INSERT INTO users (sub, email, created_at, updated_at) VALUES ($1, $2, $3, $3)
       ON CONFLICT (sub) DO UPDATE SET email = COALESCE(EXCLUDED.email, users.email), updated_at = $3`,
      [sub, email ?? null, now],
    );
    await tx.query(
      `INSERT INTO user_prefs (sub, display_name, notif_sites, notif_categories, notif_frequency, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6)
       ON CONFLICT (sub) DO UPDATE SET
         display_name = EXCLUDED.display_name,
         notif_sites = EXCLUDED.notif_sites,
         notif_categories = EXCLUDED.notif_categories,
         notif_frequency = EXCLUDED.notif_frequency,
         updated_at = EXCLUDED.updated_at`,
      [sub, displayName, sites, categories, frequency, now],
    );
  });
}

// --- role-change audit trail ----------------------------------------------------------------

export type AuditAction = "set-groups" | "set-admin-sites" | "grant-early-access" | "revoke-early-access";

export interface AuditEntry {
  actor: string;
  target: string;
  action: AuditAction;
  before: string[];
  after: string[];
  at: string;
}

/** The stored `audit_log` row — before/after are JSON-array TEXT. */
interface AuditRow {
  actor: string;
  target: string;
  action: AuditAction;
  before: string;
  after: string;
  at: string;
}

/**
 * Append one audit entry. Best-effort (mirrors the KV path): a failure is logged and swallowed, never
 * thrown — the Cognito role change that triggered it has already committed and must not roll back.
 * `id` is injected (the route mints the UUID) so the store stays pure/testable.
 */
export async function writeAuditEntry(db: PgLike, entry: AuditEntry, id: string): Promise<void> {
  try {
    await db.query(
      "INSERT INTO audit_log (id, actor, target, action, before, after, at) VALUES ($1, $2, $3, $4, $5, $6, $7)",
      [
        id,
        entry.actor,
        entry.target,
        entry.action,
        JSON.stringify(entry.before),
        JSON.stringify(entry.after),
        entry.at,
      ],
    );
  } catch (e) {
    console.error("audit write failed", id, e);
  }
}

/**
 * The most recent audit entries for a user (up to `limit`, default 20), newest first — the
 * `SELECT ... WHERE target = $1 ORDER BY at DESC` that KV couldn't answer without a keyspace scan.
 */
export async function listAuditEntries(db: PgLike, targetSub: string, limit = 20): Promise<AuditEntry[]> {
  const rows = await db.query<AuditRow>(
    "SELECT actor, target, action, before, after, at FROM audit_log WHERE target = $1 ORDER BY at DESC LIMIT $2",
    [targetSub, limit],
  );
  return rows.map((r) => ({
    actor: r.actor,
    target: r.target,
    action: r.action,
    before: parseStringArray(r.before),
    after: parseStringArray(r.after),
    at: r.at,
  }));
}
