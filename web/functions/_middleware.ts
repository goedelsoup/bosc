/**
 * Global Pages Function middleware — pre-launch gate (deploy/features.yaml `preLaunch`).
 *
 * When PRE_LAUNCH_ENABLED=true:
 *   GET /                      → rewrite to /pre-launch (URL stays /; no redirect)
 *   GET /<any non-asset route> → 302 redirect to /
 *   /api/* and static assets   → pass through unchanged
 *
 * Exception: a request carrying a valid __ea cookie (HMAC-signed, non-expired) passes
 * through all routes regardless of PRE_LAUNCH_ENABLED (#1013).
 *
 * All other requests pass straight through to the static Astro output or the
 * api/* Pages Functions.
 */

interface Env {
  /** Written by `pulumi up` from deploy/features.yaml `preLaunch`. */
  PRE_LAUNCH_ENABLED?: string;
  /** Shared secret for __ea HMAC verification. Absent = bypass branch unreachable. */
  EARLY_ACCESS_SECRET?: string;
  /** Cloudflare Pages asset-serving binding — always available in Pages Functions. */
  ASSETS: { fetch(req: Request | string, init?: RequestInit): Promise<Response> };
}

type PagesFunction = (context: {
  request: Request;
  env: Env;
  next: () => Promise<Response>;
}) => Promise<Response>;

function parseCookieValue(cookieHeader: string, name: string): string | null {
  for (const part of cookieHeader.split(";")) {
    const [k, ...rest] = part.trim().split("=");
    if (k.trim() === name) return rest.join("=").trim();
  }
  return null;
}

async function isValidEaCookie(value: string, secret: string): Promise<boolean> {
  const dot = value.lastIndexOf(".");
  if (dot < 1) return false;
  const payload = value.slice(0, dot);
  const claimedSig = value.slice(dot + 1);

  // Check expiry from payload before doing any crypto.
  let exp = 0;
  try {
    const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const pipe = decoded.lastIndexOf("|");
    if (pipe < 1) return false;
    exp = parseInt(decoded.slice(pipe + 1), 10);
  } catch {
    return false;
  }
  if (!Number.isFinite(exp) || exp < Math.floor(Date.now() / 1000)) return false;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"],
  );

  // Decode the claimed signature and verify in constant time.
  let sigBytes: Uint8Array;
  try {
    const bin = atob(claimedSig.replace(/-/g, "+").replace(/_/g, "/"));
    sigBytes = new Uint8Array(Array.from(bin, (c) => c.charCodeAt(0)));
  } catch {
    return false;
  }

  return crypto.subtle.verify("HMAC", key, sigBytes.buffer as ArrayBuffer, new TextEncoder().encode(payload));
}

export const onRequest: PagesFunction = async ({ request, env, next }) => {
  if (env.PRE_LAUNCH_ENABLED !== "true") {
    return next();
  }

  const url = new URL(request.url);
  const { pathname } = url;

  // Pass through: API routes and anything with a file extension (assets, fonts, etc.)
  if (pathname.startsWith("/api/") || /\.[a-zA-Z0-9]+$/.test(pathname)) {
    return next();
  }

  // Early-access bypass: verify __ea cookie before any redirect.
  if (env.EARLY_ACCESS_SECRET) {
    const cookieHeader = request.headers.get("cookie");
    const eaValue = cookieHeader ? parseCookieValue(cookieHeader, "__ea") : null;
    if (eaValue && (await isValidEaCookie(eaValue, env.EARLY_ACCESS_SECRET))) {
      return next();
    }
  }

  // / → serve the pre-launch page content (rewrite; URL stays /)
  if (pathname === "/" || pathname === "") {
    return env.ASSETS.fetch(new URL("/pre-launch", request.url).toString());
  }

  // Every other non-asset route → redirect to / so the pre-launch page is the only exit
  return Response.redirect(new URL("/", request.url).toString(), 302);
};
