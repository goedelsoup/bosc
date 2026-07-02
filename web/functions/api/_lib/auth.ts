// JWT verification, JWKS KV cache, and role helpers for Cognito ID tokens.
// Uses the Web Crypto API (native in Cloudflare Workers runtime).
//
// JWKS keys are cached in the bound JWKS_CACHE KV namespace (1-hour TTL) so
// every request isn't a cold fetch to Cognito's discovery endpoint.

/** A slice of the Workers KV API sufficient for JWKS caching. */
export interface KVLike {
  get(key: string): Promise<string | null>;
  put(key: string, value: string, options?: { expirationTtl?: number }): Promise<void>;
}

export type Role = "standard" | "site-admin" | "admin" | "early-access";

export interface CognitoIdToken {
  sub: string;
  email: string;
  email_verified: boolean;
  /** Cognito User Pool Groups flowing into the role. */
  "cognito:groups"?: string[];
  /** Comma-separated slugs of sites this user administers. */
  "custom:admin_sites"?: string;
  aud: string;
  iss: string;
  exp: number;
  iat: number;
  token_use: "id";
}

export interface AuthContext {
  sub: string;
  email: string;
  emailVerified: boolean;
  role: Role;
  /** Site slugs the user may administer (empty unless role is site-admin / admin). */
  adminSites: string[];
}

export interface AuthEnv {
  COGNITO_REGION: string;
  COGNITO_USER_POOL_ID: string;
  COGNITO_CLIENT_ID: string;
  JWKS_CACHE?: KVLike;
}

interface JwkKey {
  kid: string;
  kty: string;
  alg: string;
  use: string;
  n: string;
  e: string;
}

interface Jwks {
  keys: JwkKey[];
}

const JWKS_CACHE_KEY = "jwks";
const JWKS_TTL_SEC = 3600;

function base64urlDecode(str: string): Uint8Array<ArrayBuffer> {
  const padded = str.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(padded);
  // Array.from + Uint8Array constructor yields Uint8Array<ArrayBuffer> (required by SubtleCrypto).
  return new Uint8Array(Array.from(binary, (c) => c.charCodeAt(0)));
}

function parseBase64urlJson(str: string): unknown {
  return JSON.parse(new TextDecoder().decode(base64urlDecode(str)));
}

async function fetchJwks(jwksUrl: string, kv: KVLike | undefined): Promise<Jwks> {
  if (kv) {
    const hit = await kv.get(JWKS_CACHE_KEY);
    if (hit) return JSON.parse(hit) as Jwks;
  }
  const res = await fetch(jwksUrl);
  if (!res.ok) throw new Error(`JWKS fetch failed: ${res.status}`);
  const jwks = (await res.json()) as Jwks;
  if (kv) {
    await kv.put(JWKS_CACHE_KEY, JSON.stringify(jwks), { expirationTtl: JWKS_TTL_SEC });
  }
  return jwks;
}

/** Verify a Cognito ID token (RS256). Throws if invalid, expired, or audience-mismatched. */
export async function verifyIdToken(token: string, env: AuthEnv): Promise<CognitoIdToken> {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("malformed JWT");
  const [headerB64, payloadB64, sigB64] = parts;

  const header = parseBase64urlJson(headerB64) as { kid: string; alg: string };
  const payload = parseBase64urlJson(payloadB64) as CognitoIdToken;

  const now = Math.floor(Date.now() / 1000);
  if (payload.exp < now) throw new Error("token expired");
  if (payload.token_use !== "id") throw new Error("not an id token");
  if (payload.aud !== env.COGNITO_CLIENT_ID) throw new Error("audience mismatch");

  const expectedIss = `https://cognito-idp.${env.COGNITO_REGION}.amazonaws.com/${env.COGNITO_USER_POOL_ID}`;
  if (payload.iss !== expectedIss) throw new Error("issuer mismatch");

  const jwksUrl = `${expectedIss}/.well-known/jwks.json`;
  const jwks = await fetchJwks(jwksUrl, env.JWKS_CACHE);
  const jwk = jwks.keys.find((k) => k.kid === header.kid && k.alg === "RS256");
  if (!jwk) throw new Error(`no matching JWK for kid=${header.kid}`);

  const key = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );

  const signed = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
  const sig = base64urlDecode(sigB64);
  const valid = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, sig, signed);
  if (!valid) throw new Error("invalid signature");

  return payload;
}

export function extractRole(payload: CognitoIdToken): Role {
  const groups = payload["cognito:groups"] ?? [];
  if (groups.includes("admin")) return "admin";
  if (groups.includes("site-admin")) return "site-admin";
  if (groups.includes("early-access")) return "early-access";
  return "standard";
}

/** Groups eligible to receive an early-access bypass cookie. */
export const EARLY_ACCESS_GROUPS = ["early-access", "site-admin", "admin"] as const;

export function extractAdminSites(payload: CognitoIdToken): string[] {
  const raw = payload["custom:admin_sites"];
  if (!raw) return [];
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function toAuthContext(payload: CognitoIdToken): AuthContext {
  return {
    sub: payload.sub,
    email: payload.email,
    emailVerified: payload.email_verified,
    role: extractRole(payload),
    adminSites: extractAdminSites(payload),
  };
}

/** Parse the `cookie` header and return the value for `name`, or null. */
export function parseCookie(cookieHeader: string | null, name: string): string | null {
  if (!cookieHeader) return null;
  for (const part of cookieHeader.split(";")) {
    const [k, ...rest] = part.trim().split("=");
    if (k.trim() === name) return rest.join("=").trim();
  }
  return null;
}

/** Extract + verify the Bearer token from the Authorization header, or return a 401. */
export async function requireAuth(
  request: Request,
  env: AuthEnv,
): Promise<{ ok: true; ctx: AuthContext } | { ok: false; response: Response }> {
  const header = request.headers.get("authorization");
  if (!header?.startsWith("Bearer ")) {
    return {
      ok: false,
      response: new Response(JSON.stringify({ error: "unauthorized" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }),
    };
  }
  try {
    const payload = await verifyIdToken(header.slice(7), env);
    return { ok: true, ctx: toAuthContext(payload) };
  } catch {
    return {
      ok: false,
      response: new Response(JSON.stringify({ error: "unauthorized" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }),
    };
  }
}
