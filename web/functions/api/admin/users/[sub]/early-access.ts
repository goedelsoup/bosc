// PUT /api/admin/users/<sub>/early-access  — add user to early-access group.
// DELETE /api/admin/users/<sub>/early-access — remove user from early-access group.
//
// Requires admin or site-admin role. Writes an audit record on success (best-effort).
// Ships dark: AUTH_ENABLED kill switch must be "true".

import { requireAuth, type AuthEnv } from "../../../_lib/auth";
import { json } from "../../../_lib/http";
import {
  listGroupsForUser,
  addUserToGroup,
  removeUserFromGroup,
  type CognitoAdminEnv,
} from "../../../_lib/cognitoAdmin";
import { writeAuditEntry, type AuditEntry } from "../../../_lib/audit";
import type { KVLike } from "../../../_lib/ratelimit";

const GROUP = "early-access";

interface Env extends AuthEnv, CognitoAdminEnv {
  AUTH_ENABLED?: string;
  AUTH_PREFS?: KVLike;
}

interface RequestContext {
  request: Request;
  env: Env;
  params: { sub: string };
}

async function handle(method: "PUT" | "DELETE", { request, env, params }: RequestContext): Promise<Response> {
  if (env.AUTH_ENABLED !== "true") return json(503, { error: "auth not enabled" });

  const auth = await requireAuth(request, env);
  if (!auth.ok) return auth.response;

  if (auth.ctx.role !== "admin" && auth.ctx.role !== "site-admin") {
    return json(403, { error: "forbidden" });
  }

  const { sub } = params;

  // Fetch before-state first so the audit record is accurate.
  // Propagate failures (502) rather than swallowing them — a fabricated empty
  // before[] would make the audit log useless for the revoke path.
  let before: string[];
  try {
    before = await listGroupsForUser(env, sub);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return json(502, { error: `Cognito error: ${msg}` });
  }

  try {
    if (method === "PUT") {
      await addUserToGroup(env, sub, GROUP);
    } else {
      await removeUserFromGroup(env, sub, GROUP);
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return json(502, { error: `Cognito error: ${msg}` });
  }

  const after = method === "PUT" ? [...new Set([...before, GROUP])] : before.filter((g) => g !== GROUP);

  if (env.AUTH_PREFS) {
    const entry: AuditEntry = {
      actor: auth.ctx.sub,
      target: sub,
      action: method === "PUT" ? "grant-early-access" : "revoke-early-access",
      before,
      after,
      at: new Date().toISOString(),
    };
    await writeAuditEntry(env.AUTH_PREFS, entry);
  }

  return json(200, { sub, earlyAccess: method === "PUT" });
}

export const onRequestPut = (ctx: RequestContext): Promise<Response> => handle("PUT", ctx);
export const onRequestDelete = (ctx: RequestContext): Promise<Response> => handle("DELETE", ctx);
