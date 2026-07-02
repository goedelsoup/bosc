// POST /api/account/early-access — mint an __ea bypass cookie for early-access users.
// DELETE /api/account/early-access — clear the cookie (no auth required; idempotent).
//
// Cookie: Path=/ so the middleware can read it on every route.
// HttpOnly, Secure, SameSite=Lax, Max-Age=604800 (7 days).
// The embedded expiry is derived from now + MAX_AGE_SEC, not the id-token's own exp.

import { verifyIdToken, EARLY_ACCESS_GROUPS, type AuthEnv } from "../_lib/auth";
import { json } from "../_lib/http";
import { mintEaCookie, MAX_AGE_SEC } from "../_lib/eaCookie";
import { enforceRateLimit, type KVLike, type RateLimitConfig } from "../_lib/ratelimit";

interface Env extends AuthEnv {
  AUTH_ENABLED?: string;
  EARLY_ACCESS_SECRET?: string;
  RATE_LIMIT?: KVLike;
}

interface RequestContext {
  request: Request;
  env: Env;
}

const RATE_CFG: RateLimitConfig = { max: 10, windowSec: 3600 };

export const onRequestPost = async ({ request, env }: RequestContext): Promise<Response> => {
  if (env.AUTH_ENABLED !== "true") return json(503, { error: "auth not enabled" });
  if (!env.EARLY_ACCESS_SECRET) return json(503, { error: "early access not configured" });

  const ip = request.headers.get("CF-Connecting-IP") ?? "unknown";
  if (env.RATE_LIMIT) {
    const blocked = await enforceRateLimit(
      env.RATE_LIMIT,
      ip,
      Math.floor(Date.now() / 1000),
      RATE_CFG,
      "Too many early-access requests. Try again later.",
    );
    if (blocked) return blocked;
  }

  const header = request.headers.get("authorization");
  if (!header?.startsWith("Bearer ")) return json(401, { error: "unauthorized" });

  let payload: Awaited<ReturnType<typeof verifyIdToken>>;
  try {
    payload = await verifyIdToken(header.slice(7), env);
  } catch {
    return json(401, { error: "unauthorized" });
  }

  const groups = payload["cognito:groups"] ?? [];
  const eligible = (EARLY_ACCESS_GROUPS as readonly string[]).some((g) => groups.includes(g));
  if (!eligible) return json(403, { error: "forbidden" });

  const value = await mintEaCookie(payload.sub, env.EARLY_ACCESS_SECRET);
  const cookie = `__ea=${value}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${MAX_AGE_SEC}`;

  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "content-type": "application/json", "set-cookie": cookie },
  });
};

export const onRequestDelete = async ({ request, env }: RequestContext): Promise<Response> => {
  if (env.AUTH_ENABLED !== "true") return json(503, { error: "auth not enabled" });

  const ip = request.headers.get("CF-Connecting-IP") ?? "unknown";
  if (env.RATE_LIMIT) {
    const blocked = await enforceRateLimit(
      env.RATE_LIMIT,
      ip,
      Math.floor(Date.now() / 1000),
      RATE_CFG,
      "Too many early-access requests. Try again later.",
    );
    if (blocked) return blocked;
  }

  const clearCookie = "__ea=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0";
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "content-type": "application/json", "set-cookie": clearCookie },
  });
};
