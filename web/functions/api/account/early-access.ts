// POST /api/account/early-access — mint an __ea bypass cookie for early-access users.
// DELETE /api/account/early-access — clear the cookie (no auth required; idempotent).
//
// Cookie format: base64url(sub|exp) + "." + HMAC-SHA256(sub|exp, EARLY_ACCESS_SECRET)
// HttpOnly, Secure, SameSite=Lax, Max-Age=604800 (7 days), no Path restriction so
// the middleware can read it on every route.

import { verifyIdToken, EARLY_ACCESS_GROUPS, type AuthEnv } from "../_lib/auth";
import { json } from "../_lib/http";

interface Env extends AuthEnv {
  AUTH_ENABLED?: string;
  EARLY_ACCESS_SECRET?: string;
}

interface RequestContext {
  request: Request;
  env: Env;
}

const MAX_AGE = 60 * 60 * 24 * 7; // 7 days in seconds

function b64url(buf: ArrayBuffer | Uint8Array): string {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

async function mintCookie(sub: string, exp: number, secret: string): Promise<string> {
  const payload = b64url(new TextEncoder().encode(`${sub}|${exp}`));
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = b64url(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload)));
  return `${payload}.${sig}`;
}

export const onRequestPost = async ({ request, env }: RequestContext): Promise<Response> => {
  if (env.AUTH_ENABLED !== "true") return json(503, { error: "auth not enabled" });
  if (!env.EARLY_ACCESS_SECRET) return json(503, { error: "early access not configured" });

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

  const value = await mintCookie(payload.sub, payload.exp, env.EARLY_ACCESS_SECRET);
  const cookie = `__ea=${value}; HttpOnly; Secure; SameSite=Lax; Max-Age=${MAX_AGE}`;

  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "content-type": "application/json", "set-cookie": cookie },
  });
};

export const onRequestDelete = async ({ env }: RequestContext): Promise<Response> => {
  if (env.AUTH_ENABLED !== "true") return json(503, { error: "auth not enabled" });

  const clearCookie = "__ea=; HttpOnly; Secure; SameSite=Lax; Max-Age=0";
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "content-type": "application/json", "set-cookie": clearCookie },
  });
};
