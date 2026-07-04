// POST /api/admin/users/<sub>/admin-sites — update the custom:admin_sites attribute.
// Body: { sites: string[] }
//
// admin: may set any sites.
// site-admin: may only assign sites that are a subset of their own adminSites.
//
// Writes an audit record to the Lakebase audit_log on success (best-effort).
// Ships dark: AUTH_ENABLED kill switch must be "true".

import { requireAuth, type AuthEnv } from "../../../_lib/auth";
import { type AuthDbEnv, resolveAuthDb } from "../../../_lib/authDb";
import { writeAuditEntry, type AuditEntry } from "../../../_lib/authStore";
import { json, parseJsonBody } from "../../../_lib/http";
import { setAdminSites, getUser, type CognitoAdminEnv } from "../../../_lib/cognitoAdmin";

const SLUG_RE = /^[a-z0-9][a-z0-9-]*$/;

interface Env extends AuthEnv, AuthDbEnv, CognitoAdminEnv {
  AUTH_ENABLED?: string;
}

interface RequestContext {
  request: Request;
  env: Env;
  params: { sub: string };
}

export const onRequestPost = async ({ request, env, params }: RequestContext): Promise<Response> => {
  if (env.AUTH_ENABLED !== "true") return json(503, { error: "auth not enabled" });

  const auth = await requireAuth(request, env);
  if (!auth.ok) return auth.response;

  if (auth.ctx.role === "standard") {
    return json(403, { error: "forbidden" });
  }

  const body = await parseJsonBody(request);
  if (!body.ok) return body.response;

  const { sub } = params;
  const patch = body.value as Record<string, unknown>;

  if (!Array.isArray(patch.sites)) {
    return json(400, { error: "sites must be an array" });
  }
  const invalidSlugs = (patch.sites as unknown[]).filter((s) => typeof s !== "string" || !SLUG_RE.test(s));
  if (invalidSlugs.length > 0) {
    return json(400, { error: "sites must be valid slug strings" });
  }
  const newSites = patch.sites as string[];

  // Read current adminSites for the scope check and audit record.
  const targetUser = await getUser(env, sub).catch(() => null);
  const before = targetUser?.adminSites ?? [];

  // Site-admins: target user must already be in scope, and new sites must stay in scope.
  if (auth.ctx.role === "site-admin") {
    const callerSites = new Set(auth.ctx.adminSites);
    if (!targetUser || !before.some((s) => callerSites.has(s))) {
      return json(403, { error: "target user is not within your site scope" });
    }
    const outOfScope = newSites.filter((s) => !callerSites.has(s));
    if (outOfScope.length > 0) {
      return json(403, { error: `cannot assign out-of-scope sites: ${outOfScope.join(", ")}` });
    }
  }

  // Fail closed BEFORE the Cognito mutation: refuse an unauditable role change if the audit store
  // isn't bound, rather than mutate without a record.
  const db = resolveAuthDb(env);
  if (!db) return json(503, { error: "audit store not configured" });

  try {
    await setAdminSites(env, sub, newSites);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return json(502, { error: `Cognito error: ${msg}` });
  }

  // Best-effort on transient write failure — the Cognito change already committed.
  const entry: AuditEntry = {
    actor: auth.ctx.sub,
    target: sub,
    action: "set-admin-sites",
    before,
    after: newSites,
    at: new Date().toISOString(),
  };
  await writeAuditEntry(db, entry, crypto.randomUUID());

  return json(200, { sub, adminSites: newSites });
};
