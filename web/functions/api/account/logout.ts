// POST /api/account/logout — Clears the HttpOnly refresh token cookie.
//
// The client calls this on sign-out, then clears its own sessionStorage id_token
// and redirects to Cognito's /logout endpoint. Two-step because JS can't clear
// the HttpOnly cookie directly.

import { json } from "../_lib/http";

interface Env {
  AUTH_ENABLED?: string;
}

interface RequestContext {
  request: Request;
  env: Env;
}

export const onRequestPost = async ({ env }: RequestContext): Promise<Response> => {
  if (env.AUTH_ENABLED !== "true") return json(503, { error: "auth not enabled" });

  const headers = new Headers({ "content-type": "application/json" });
  headers.append("set-cookie", "__rt=; HttpOnly; Secure; SameSite=Lax; Path=/api/account; Max-Age=0");
  headers.append("set-cookie", "__ea=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0");
  return new Response(JSON.stringify({ ok: true }), { status: 200, headers });
};
