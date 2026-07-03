// The production `PgLike` driver (epic #1090) — postgres.js over a Cloudflare Hyperdrive binding,
// which pools connections to Databricks Lakebase (managed Postgres) and lets the Workers runtime
// reach it over `cloudflare:sockets`. This is the ONE place the store's driver-agnostic `PgLike`
// (functions/api/_lib/storiesStore.ts) is bound to a real driver; the test harness binds pglite.
//
// The client is memoized per connection string: in the Workers isolate model a module-global
// postgres.js client is reused across requests (Hyperdrive keeps the actual pool warm server-side),
// so we don't reconnect per request and there's nothing to `end()` on the hot path.

import postgres from "postgres";
import type { PgLike } from "./storiesStore";

/** The Cloudflare Hyperdrive binding surface we use — just the pooled connection string. */
export interface Hyperdrive {
  connectionString: string;
}

// postgres.js's own `Sql` type carries heavy generics; the transaction callback gets a compatible
// `Sql`-shaped handle. We only touch `.unsafe()` + `.begin()`, so a minimal structural type keeps
// this file free of the driver's Node-typed internals (functions/tsconfig has no node types).
interface Sqlish {
  unsafe(query: string, params?: unknown[]): Promise<unknown[]>;
  begin<T>(fn: (tx: Sqlish) => Promise<T>): Promise<T>;
}

/** Adapt a postgres.js `Sql`/transaction handle to the store's `PgLike` contract. */
function adapt(sql: Sqlish): PgLike {
  return {
    query: <T>(text: string, params: unknown[] = []) => sql.unsafe(text, params) as Promise<T[]>,
    begin: <T>(fn: (tx: PgLike) => Promise<T>) => sql.begin((tx) => fn(adapt(tx))),
  };
}

let cached: { key: string; db: PgLike } | undefined;

/**
 * A memoized `PgLike` over a Hyperdrive connection string. `prepare: false` is required behind
 * Hyperdrive (it pools/multiplexes, so per-connection prepared statements don't survive); we bind
 * parameters through `unsafe(text, params)` instead, which is still fully parameterized ($n), never
 * string-interpolated — no injection surface.
 */
export function hyperdrivePg(connectionString: string): PgLike {
  if (cached?.key === connectionString) return cached.db;
  const sql = postgres(connectionString, {
    max: 5,
    fetch_types: false,
    prepare: false,
  }) as unknown as Sqlish;
  cached = { key: connectionString, db: adapt(sql) };
  return cached.db;
}
