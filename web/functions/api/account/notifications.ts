// GET  /api/account/notifications — Read the user's notification preferences.
// PATCH /api/account/notifications — Update sites, categories, and/or frequency.
//
// `email_verified` is read-only (sourced from the live Cognito JWT); it cannot be PATCH'd.
// Auth-gated: requires a valid Cognito Bearer token. Ships dark (AUTH_ENABLED kill switch).
// The prefs store (Lakebase via AUTH_HYPERDRIVE) must be bound; absent → 503.

import { requireAuth, type AuthEnv } from "../_lib/auth";
import { type AuthDbEnv, resolveAuthDb } from "../_lib/authDb";
import { getPrefs, setNotifications, VALID_CATEGORIES, VALID_FREQUENCIES } from "../_lib/authStore";
import type { NotifCategory, NotifFrequency } from "../_lib/authStore";
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
  // Sync email_verified from the live JWT on every read.
  prefs.notifications.email_verified = auth.ctx.emailVerified;
  return json(200, prefs.notifications);
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

  // Validate sites: array of slug-formatted strings (^[a-z0-9][a-z0-9-]*$).
  // Full registry validation would require coupling to Astro-land; format validation
  // rejects garbage while allowing any valid slug regardless of registry state.
  if (patch.sites !== undefined) {
    if (!Array.isArray(patch.sites)) {
      return json(400, { error: "sites must be an array of strings" });
    }
    const slugRe = /^[a-z0-9][a-z0-9-]*$/;
    const invalid = (patch.sites as unknown[]).filter((s) => typeof s !== "string" || !slugRe.test(s));
    if (invalid.length > 0) {
      return json(400, { error: `invalid site slugs: ${invalid.join(", ")}` });
    }
  }

  // Validate categories
  if (patch.categories !== undefined) {
    if (!Array.isArray(patch.categories)) {
      return json(400, { error: "categories must be an array" });
    }
    const invalid = (patch.categories as unknown[]).filter(
      (c) => !VALID_CATEGORIES.includes(c as NotifCategory),
    );
    if (invalid.length > 0) {
      return json(400, {
        error: `invalid categories: ${invalid.join(", ")}; valid: ${VALID_CATEGORIES.join(", ")}`,
      });
    }
  }

  // Validate frequency
  if (patch.frequency !== undefined && !VALID_FREQUENCIES.includes(patch.frequency as NotifFrequency)) {
    return json(400, { error: `frequency must be one of: ${VALID_FREQUENCIES.join(", ")}` });
  }

  const prefs = await getPrefs(db, auth.ctx.sub);

  if (patch.sites !== undefined) prefs.notifications.sites = patch.sites as string[];
  if (patch.categories !== undefined) prefs.notifications.categories = patch.categories as NotifCategory[];
  if (patch.frequency !== undefined) prefs.notifications.frequency = patch.frequency as NotifFrequency;

  // Sync email_verified from the live JWT — not user-settable.
  prefs.notifications.email_verified = auth.ctx.emailVerified;

  // Column-scoped write — only the notification columns, so a concurrent profile PATCH isn't clobbered.
  await setNotifications(db, auth.ctx.sub, prefs.notifications, new Date().toISOString(), auth.ctx.email);
  return json(200, prefs.notifications);
};
