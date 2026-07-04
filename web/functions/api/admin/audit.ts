// GET /api/admin/audit?sub=<sub> — list recent role-change audit entries for a user.
// Returns up to 20 entries in reverse-chronological order.
//
// Requires `admin` or `site-admin` role.
// site-admin: may only query audit entries for users whose adminSites overlap the caller's.
//
// Ships dark: AUTH_ENABLED kill switch must be "true".

import { requireAuth, type AuthEnv } from "../_lib/auth";
import { type AuthDbEnv, resolveAuthDb } from "../_lib/authDb";
import { listAuditEntries } from "../_lib/authStore";
import { json } from "../_lib/http";
import { getUser, type CognitoAdminEnv } from "../_lib/cognitoAdmin";

interface Env extends AuthEnv, AuthDbEnv, CognitoAdminEnv {
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

  if (auth.ctx.role === "standard") {
    return json(403, { error: "forbidden" });
  }

  const db = resolveAuthDb(env);
  if (!db) return json(503, { error: "prefs store not configured" });

  const url = new URL(request.url);
  const sub = url.searchParams.get("sub");
  if (!sub) return json(400, { error: "sub is required" });

  // Site-admins may only read audit entries for users within their site scope.
  if (auth.ctx.role === "site-admin") {
    const targetUser = await getUser(env, sub).catch(() => null);
    if (!targetUser) return json(404, { error: "user not found" });
    const callerSites = new Set(auth.ctx.adminSites);
    if (!targetUser.adminSites.some((s) => callerSites.has(s))) {
      return json(403, { error: "forbidden" });
    }
  }

  const entries = await listAuditEntries(db, sub);
  return json(200, entries);
};
