// Bearer service-token bypass for POST /api/ask (#1578).
//
// A ChatGPT plugin / GPT Action can't solve a Cloudflare Turnstile challenge, so the public
// browser gate (`turnstile_token`) is unreachable from an agent ecosystem. This lets a
// request carrying `Authorization: Bearer <ASK_PLUGIN_TOKEN>` stand in for the human
// challenge — mirroring the MCP endpoint's Bearer "cognito" tier (mcpAuth.ts).
//
// The bypass is OFF unless ASK_PLUGIN_TOKEN is provisioned (a Cloudflare secret): with no
// token bound no header value can authorize, so the endpoint keeps its Turnstile-only
// posture. It replaces ONLY the human-verification step — the per-IP rate limit and the
// account-wide daily token budget in ask.ts still apply to plugin traffic.

export interface AskPluginAuthEnv {
  /** Shared plugin service token (Cloudflare secret). Absent ⇒ no Bearer bypass. */
  ASK_PLUGIN_TOKEN?: string;
}

/** Constant-time string compare — avoids leaking the token through response timing. */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/**
 * True when the request bears a valid `Authorization: Bearer <ASK_PLUGIN_TOKEN>`.
 * Returns false when no plugin token is configured (bypass disabled) or the header is
 * absent / malformed / mismatched — the caller then falls back to Turnstile verification.
 */
export function isPluginAuthorized(request: Request, env: AskPluginAuthEnv): boolean {
  const expected = env.ASK_PLUGIN_TOKEN;
  if (!expected) return false;
  const match = /^Bearer\s+(.+)$/i.exec(request.headers.get("authorization") ?? "");
  if (!match) return false;
  return timingSafeEqual(match[1], expected);
}
