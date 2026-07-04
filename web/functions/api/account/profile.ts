// GET  /api/account/profile — Read the user's profile + display name.
// PATCH /api/account/profile — Update display_name (1–80 chars; omit to clear).
//
// Auth-gated: requires a valid Cognito Bearer token. Ships dark (AUTH_ENABLED kill switch).
// The prefs store (Lakebase via AUTH_HYPERDRIVE) must be bound; absent → 503.

import { requireAuth, type AuthEnv } from "../_lib/auth";
import { type AuthDbEnv, resolveAuthDb } from "../_lib/authDb";
import { getPrefs, putPrefs } from "../_lib/authStore";
import { json, parseJsonBody } from "../_lib/http";

interface Env extends AuthEnv, AuthDbEnv {
  AUTH_ENABLED?: string;
}

interface RequestContext {
  request: Request;
  env: Env;
}

export const onRequestGet = async ({ request, env }: RequestContext): Promise<Response> => {
  if (env.AUTH_ENABLED !== "true") return json(503, { error: "auth not enabled" });
  const auth = await requireAuth(request, env);
  if (!auth.ok) return auth.response;
  const db = resolveAuthDb(env);
  if (!db) return json(503, { error: "prefs store not configured" });

  const prefs = await getPrefs(db, auth.ctx.sub);
  return json(200, {
    sub: auth.ctx.sub,
    email: auth.ctx.email,
    email_verified: auth.ctx.emailVerified,
    display_name: prefs.display_name ?? null,
    role: auth.ctx.role,
  });
};

export const onRequestPatch = async ({ request, env }: RequestContext): Promise<Response> => {
  if (env.AUTH_ENABLED !== "true") return json(503, { error: "auth not enabled" });
  const auth = await requireAuth(request, env);
  if (!auth.ok) return auth.response;
  const db = resolveAuthDb(env);
  if (!db) return json(503, { error: "prefs store not configured" });

  const body = await parseJsonBody(request);
  if (!body.ok) return body.response;
  if (!body.value || typeof body.value !== "object" || Array.isArray(body.value)) {
    return json(400, { error: "body must be an object" });
  }

  const patch = body.value as Record<string, unknown>;
  const rawName = patch.display_name;

  if (rawName !== undefined && rawName !== null) {
    if (typeof rawName !== "string") return json(400, { error: "display_name must be a string" });
    const trimmed = rawName.trim();
    if (trimmed.length > 80) return json(400, { error: "display_name too long (max 80 chars)" });
  }

  const prefs = await getPrefs(db, auth.ctx.sub);

  if (rawName === null) {
    delete prefs.display_name;
  } else if (typeof rawName === "string") {
    const trimmed = rawName.trim();
    if (trimmed) {
      prefs.display_name = trimmed;
    } else {
      delete prefs.display_name;
    }
  }

  await putPrefs(db, auth.ctx.sub, prefs, new Date().toISOString(), auth.ctx.email);
  return json(200, {
    sub: auth.ctx.sub,
    email: auth.ctx.email,
    email_verified: auth.ctx.emailVerified,
    display_name: prefs.display_name ?? null,
    role: auth.ctx.role,
  });
};
