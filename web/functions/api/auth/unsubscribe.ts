// GET /api/auth/unsubscribe?token=<token>
// One-click unsubscribe handler (#939 E2). No login required — the signed token is the
// credential. On success: removes the category from the user's stored prefs and returns 200.
// On bad/expired token: returns 400.
//
// The UNSUB_SECRET must match the secret used by the Lambda to mint the token (E1 #938).
// The prefs store (Lakebase via AUTH_HYPERDRIVE) must be bound (same store as the notifications prefs).

import { type AuthDbEnv, resolveAuthDb } from "../_lib/authDb";
import { unsubscribeCategory, VALID_CATEGORIES } from "../_lib/authStore";
import type { NotifCategory } from "../_lib/authStore";
import { json } from "../_lib/http";
import { verifyUnsubToken } from "../_lib/unsub";

interface Env extends AuthDbEnv {
  UNSUB_SECRET?: string;
}

interface RequestContext {
  request: Request;
  env: Env;
}

export const onRequestGet = async ({ request, env }: RequestContext): Promise<Response> => {
  if (!env.UNSUB_SECRET) return json(503, { error: "unsubscribe not configured" });
  const db = resolveAuthDb(env);
  if (!db) return json(503, { error: "prefs store not configured" });

  const url = new URL(request.url);
  const token = url.searchParams.get("token");
  if (!token) return json(400, { error: "token is required" });

  const payload = await verifyUnsubToken(token, env.UNSUB_SECRET);
  if (!payload) return json(400, { error: "invalid or expired token" });

  const { sub, category } = payload;

  if (!VALID_CATEGORIES.includes(category as NotifCategory)) {
    return json(400, { error: "unknown category" });
  }

  // Update-only: never materializes a prefs/users row from this unauthenticated token. A sub with no
  // prefs is a success no-op (nothing was subscribed).
  const remaining = await unsubscribeCategory(db, sub, category as NotifCategory, new Date().toISOString());

  return json(200, { ok: true, removed: category, remaining });
};
