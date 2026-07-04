// POST /api/admin/users/<sub>/groups — replace a user's group memberships.
// Body: { groups: string[] }  — use [] to reset to no managed group.
//
// admin: may set any of ["admin", "site-admin", "standard"].
// site-admin: forbidden — only full admins may change group assignments.
//
// Writes an audit record to the Lakebase audit_log on success (best-effort).
// Ships dark: AUTH_ENABLED kill switch must be "true".

import { requireAuth, type AuthEnv } from "../../../_lib/auth";
import { type AuthDbEnv, resolveAuthDb } from "../../../_lib/authDb";
import { writeAuditEntry, type AuditEntry } from "../../../_lib/authStore";
import { json, parseJsonBody } from "../../../_lib/http";
import { setGroupsForUser, listGroupsForUser, type CognitoAdminEnv } from "../../../_lib/cognitoAdmin";

const MANAGED_GROUPS = ["admin", "site-admin", "standard"];

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

  // Only full admins may change group memberships.
  if (auth.ctx.role !== "admin") {
    return json(403, { error: "forbidden" });
  }

  const body = await parseJsonBody(request);
  if (!body.ok) return body.response;

  const { sub } = params;
  const patch = body.value as Record<string, unknown>;

  if (!Array.isArray(patch.groups)) {
    return json(400, { error: "groups must be an array" });
  }
  const invalid = (patch.groups as unknown[]).filter(
    (g) => typeof g !== "string" || !MANAGED_GROUPS.includes(g),
  );
  if (invalid.length > 0) {
    return json(400, { error: `invalid groups; allowed: ${MANAGED_GROUPS.join(", ")}` });
  }

  const newGroups = patch.groups as string[];

  // Read current state for the audit record.
  const before = await listGroupsForUser(env, sub).catch(() => [] as string[]);

  try {
    await setGroupsForUser(env, sub, newGroups);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return json(502, { error: `Cognito error: ${msg}` });
  }

  // Audit log (best-effort — failure doesn't roll back the Cognito change).
  const db = resolveAuthDb(env);
  if (db) {
    const entry: AuditEntry = {
      actor: auth.ctx.sub,
      target: sub,
      action: "set-groups",
      before,
      after: newGroups,
      at: new Date().toISOString(),
    };
    await writeAuditEntry(db, entry, crypto.randomUUID());
  }

  return json(200, { sub, groups: newGroups });
};
