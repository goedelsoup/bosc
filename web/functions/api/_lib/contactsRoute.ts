// Shared plumbing for the interactive site-contacts Pages Functions — the env shape, the
// kill-switch + guards, the write rate-limit, and the public serializers. Mirrors storiesRoute.ts
// (kept out of the route files so the endpoints stay thin) and reuses the SAME Hyperdrive→Lakebase
// binding as Stories (one database), only behind its own `CONTACTS_ENABLED` kill switch.

import { type AuthContext, type AuthEnv, requireAuth } from "./auth";
import { intEnv } from "./env";
import { json, requireEnabled } from "./http";
import { type Hyperdrive, hyperdrivePg } from "./pg";
import { type KVLike, checkRateLimit } from "./ratelimit";
import type { PgLike } from "./storiesStore";

export interface ContactsEnv extends AuthEnv {
  /** Kill switch (feature flag). Absent/≠"true" → 503, the feature ships dark. */
  CONTACTS_ENABLED?: string;
  /** The Cloudflare Hyperdrive binding to Databricks Lakebase — the SAME config Stories/auth use. */
  STORIES_HYPERDRIVE?: Hyperdrive;
  /** Test-only injection seam: a `PgLike` bound directly (pglite in the harness); wins over Hyperdrive. */
  CONTACTS_DB?: PgLike;
  /** Per-IP write rate-limit KV (optional — absent means writes aren't limited). */
  RATE_LIMIT?: KVLike;
  CONTACTS_RATE_LIMIT_MAX?: string;
  CONTACTS_RATE_LIMIT_WINDOW_SEC?: string;
  /** Cloudflare Turnstile secret — when set, the public write endpoints require a passing token. */
  TURNSTILE_SECRET?: string;
}

const DEFAULT_WRITE_MAX = 10;
const DEFAULT_WRITE_WINDOW_SEC = 3600;

/** Resolve the store: the injected `PgLike` (tests) wins; otherwise the Hyperdrive→Lakebase client. */
function resolveDb(env: ContactsEnv): PgLike | null {
  if (env.CONTACTS_DB) return env.CONTACTS_DB;
  if (env.STORIES_HYPERDRIVE) return hyperdrivePg(env.STORIES_HYPERDRIVE.connectionString);
  return null;
}

/** Kill switch + store, no auth — the guard for the public petition-connect + bulletin read/write. */
export function guardPublicContacts(
  env: ContactsEnv,
): { ok: true; db: PgLike } | { ok: false; response: Response } {
  const disabled = requireEnabled(env.CONTACTS_ENABLED, () => json(503, { error: "contacts not enabled" }));
  if (disabled) return { ok: false, response: disabled };
  const db = resolveDb(env);
  if (!db) return { ok: false, response: json(503, { error: "contacts store not configured" }) };
  return { ok: true, db };
}

/**
 * Kill switch → auth → **admin authority for this site** → store. The moderation + hand-off view is
 * open to a global `admin` OR a `site-admin` whose `adminSites` includes the requested slug — so a
 * petitioner who administers their own site sees their connects without seeing another site's.
 */
export async function guardContactsAdmin(
  request: Request,
  env: ContactsEnv,
  site: string,
): Promise<{ ok: true; db: PgLike; ctx: AuthContext } | { ok: false; response: Response }> {
  const disabled = requireEnabled(env.CONTACTS_ENABLED, () => json(503, { error: "contacts not enabled" }));
  if (disabled) return { ok: false, response: disabled };
  const auth = await requireAuth(request, env);
  if (!auth.ok) return { ok: false, response: auth.response };
  const authorized = auth.ctx.role === "admin" || auth.ctx.adminSites.includes(site);
  if (!authorized) return { ok: false, response: json(403, { error: "forbidden" }) };
  const db = resolveDb(env);
  if (!db) return { ok: false, response: json(503, { error: "contacts store not configured" }) };
  return { ok: true, db, ctx: auth.ctx };
}

/** Soft per-IP rate limit on writes. Optional (no KV bound → skipped); fails open on KV error. */
export async function writeRateLimit(request: Request, env: ContactsEnv): Promise<Response | null> {
  if (!env.RATE_LIMIT) return null;
  const ip = request.headers.get("cf-connecting-ip") ?? "0.0.0.0";
  const cfg = {
    max: intEnv(env.CONTACTS_RATE_LIMIT_MAX, DEFAULT_WRITE_MAX),
    windowSec: intEnv(env.CONTACTS_RATE_LIMIT_WINDOW_SEC, DEFAULT_WRITE_WINDOW_SEC),
  };
  const res = await checkRateLimit(env.RATE_LIMIT, ip, Math.floor(Date.now() / 1000), cfg);
  if (!res.allowed) {
    return json(429, { error: "rate limited" }, { "retry-after": String(res.retryAfter) });
  }
  return null;
}
