// Resolve the `PgLike` store for the auth prefs + audit endpoints (#1171). Keeps `authStore.ts`
// driver-agnostic (it only knows `PgLike`); this is the one place the production driver
// (postgres.js over Hyperdrive → Databricks Lakebase) is bound, mirroring `resolveDb` in
// `storiesRoute.ts`. Auth rides the SAME Lakebase instance as Stories (#1090) — `AUTH_HYPERDRIVE`
// and `STORIES_HYPERDRIVE` point at one provisioned Hyperdrive config (same `id`) over one database.

import { type Hyperdrive, hyperdrivePg } from "./pg";
import type { PgLike } from "./storiesStore";

export interface AuthDbEnv {
  /** Hyperdrive → Databricks Lakebase (Postgres). Absent → the store is unconfigured (503, fail-closed). */
  AUTH_HYPERDRIVE?: Hyperdrive;
  /** Test-only injection seam: a `PgLike` bound directly (pglite in the harness); wins over Hyperdrive. */
  AUTH_DB?: PgLike;
}

/** The injected `PgLike` (tests) wins; otherwise the Hyperdrive→Lakebase client; else null (503). */
export function resolveAuthDb(env: AuthDbEnv): PgLike | null {
  if (env.AUTH_DB) return env.AUTH_DB;
  if (env.AUTH_HYPERDRIVE) return hyperdrivePg(env.AUTH_HYPERDRIVE.connectionString);
  return null;
}
