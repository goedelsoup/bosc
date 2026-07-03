// Shared plumbing for the /api/stories Pages Functions (#1095): the env shape, the
// kill-switch + auth + store guard, the write rate-limit, and the owner-scoped serializers.
// Kept out of the route files so `stories.ts` and `stories/[id].ts` stay thin and consistent.

import { type AuthContext, type AuthEnv, requireAuth } from "./auth";
import { intEnv } from "./env";
import { json, requireEnabled } from "./http";
import { type KVLike, checkRateLimit } from "./ratelimit";
import type { D1Like, StoryOwner, StoryRef, StoryRow } from "./storiesStore";

export interface StoriesEnv extends AuthEnv {
  /** Kill switch (feature flag). Absent/≠"true" → 503, feature ships dark. */
  STORIES_ENABLED?: string;
  /** The D1 binding. Absent → 503 (not provisioned yet). */
  STORIES_DB?: D1Like;
  /** Per-IP write rate-limit KV (optional — absent means writes aren't limited). */
  RATE_LIMIT?: KVLike;
  /** Override the same-origin `/stories-catalog.json` asset URL. */
  STORIES_CATALOG_URL?: string;
  STORIES_RATE_LIMIT_MAX?: string;
  STORIES_RATE_LIMIT_WINDOW_SEC?: string;
}

const DEFAULT_WRITE_MAX = 20;
const DEFAULT_WRITE_WINDOW_SEC = 3600;

/** Kill switch → auth → store, in order. On success yields the user-owner + the bound DB. */
export async function guardStories(
  request: Request,
  env: StoriesEnv,
): Promise<
  { ok: true; owner: StoryOwner; db: D1Like; ctx: AuthContext } | { ok: false; response: Response }
> {
  const disabled = requireEnabled(env.STORIES_ENABLED, () => json(503, { error: "stories not enabled" }));
  if (disabled) return { ok: false, response: disabled };

  const auth = await requireAuth(request, env);
  if (!auth.ok) return { ok: false, response: auth.response };

  if (!env.STORIES_DB) return { ok: false, response: json(503, { error: "stories store not configured" }) };

  return { ok: true, owner: { kind: "user", id: auth.ctx.sub }, db: env.STORIES_DB, ctx: auth.ctx };
}

/** Soft per-IP rate limit on writes. Optional (no KV bound → skipped); fails open on KV error. */
export async function writeRateLimit(request: Request, env: StoriesEnv): Promise<Response | null> {
  if (!env.RATE_LIMIT) return null;
  const ip = request.headers.get("cf-connecting-ip") ?? "0.0.0.0";
  const cfg = {
    max: intEnv(env.STORIES_RATE_LIMIT_MAX, DEFAULT_WRITE_MAX),
    windowSec: intEnv(env.STORIES_RATE_LIMIT_WINDOW_SEC, DEFAULT_WRITE_WINDOW_SEC),
  };
  const res = await checkRateLimit(env.RATE_LIMIT, ip, Math.floor(Date.now() / 1000), cfg);
  if (!res.allowed) {
    return json(429, { error: "rate limited" }, { "retry-after": String(res.retryAfter) });
  }
  return null;
}

/** A list-row summary — omits the heavy `source_text`/`sdm_json` so the account list stays light. */
export function storySummary(row: StoryRow) {
  return {
    id: row.id,
    site: row.site,
    slug: row.slug,
    title: row.title,
    dek: row.dek,
    status: row.status,
    share_id: row.share_id,
    catalog_version: row.catalog_version,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

/** The full Story: the summary + the source, the parsed SDM, and the cited refs. */
export function storyDetail(row: StoryRow, refs: StoryRef[]) {
  return {
    ...storySummary(row),
    source_format: row.source_format,
    source_text: row.source_text,
    sdm: JSON.parse(row.sdm_json),
    refs,
  };
}
