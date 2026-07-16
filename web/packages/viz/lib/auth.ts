// Client-side auth helpers: PKCE generation, sessionStorage, and token parsing.
// Browser-only — do not import in server-side Astro frontmatter.

export type Role = "standard" | "site-admin" | "admin";

export interface AuthUser {
  sub: string;
  email: string;
  role: Role;
  /** Site slugs this user may administer. */
  adminSites: string[];
  /** Unix expiry of the ID token (seconds). */
  exp: number;
}

const ID_TOKEN_KEY = "watermark_id_token";
const PKCE_VERIFIER_KEY = "watermark_pkce_cv";

// --- PKCE (RFC 7636) ---

function base64urlEncode(buf: Uint8Array): string {
  return btoa(String.fromCharCode(...buf))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
}

export async function generatePkce(): Promise<{ verifier: string; challenge: string }> {
  const verifier = base64urlEncode(crypto.getRandomValues(new Uint8Array(32)));
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  const challenge = base64urlEncode(new Uint8Array(digest));
  return { verifier, challenge };
}

export function storePkceVerifier(verifier: string): void {
  sessionStorage.setItem(PKCE_VERIFIER_KEY, verifier);
}

export function getPkceVerifier(): string | null {
  return sessionStorage.getItem(PKCE_VERIFIER_KEY);
}

export function clearPkceVerifier(): void {
  sessionStorage.removeItem(PKCE_VERIFIER_KEY);
}

// --- ID token sessionStorage ---

export function storeIdToken(token: string): void {
  sessionStorage.setItem(ID_TOKEN_KEY, token);
}

export function getIdToken(): string | null {
  return sessionStorage.getItem(ID_TOKEN_KEY);
}

export function clearIdToken(): void {
  sessionStorage.removeItem(ID_TOKEN_KEY);
}

// --- Token parsing (client trusts server-verified token for display purposes) ---

function base64urlDecodeText(str: string): string {
  return atob(str.replace(/-/g, "+").replace(/_/g, "/"));
}

export function parseIdToken(token: string): AuthUser | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(base64urlDecodeText(parts[1])) as Record<string, unknown>;
    const now = Math.floor(Date.now() / 1000);
    if (typeof payload.exp !== "number" || payload.exp < now) return null;
    const groups = Array.isArray(payload["cognito:groups"]) ? (payload["cognito:groups"] as string[]) : [];
    const role: Role = groups.includes("admin")
      ? "admin"
      : groups.includes("site-admin")
        ? "site-admin"
        : "standard";
    const adminSites =
      typeof payload["custom:admin_sites"] === "string"
        ? (payload["custom:admin_sites"] as string)
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [];
    return {
      sub: String(payload.sub),
      email: String(payload.email),
      role,
      adminSites,
      exp: payload.exp,
    };
  } catch {
    return null;
  }
}

/** Read the current auth user from sessionStorage, or null when logged out / token expired. */
export function currentUser(): AuthUser | null {
  const token = getIdToken();
  return token ? parseIdToken(token) : null;
}

/** Build the Cognito Hosted UI authorization URL for a PKCE flow. */
export function buildAuthUrl(params: {
  cognitoDomain: string;
  clientId: string;
  redirectUri: string;
  codeChallenge: string;
  state: string;
}): string {
  const url = new URL(`https://${params.cognitoDomain}/oauth2/authorize`);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", params.clientId);
  url.searchParams.set("redirect_uri", params.redirectUri);
  url.searchParams.set("scope", "openid email profile");
  url.searchParams.set("code_challenge_method", "S256");
  url.searchParams.set("code_challenge", params.codeChallenge);
  url.searchParams.set("state", params.state);
  return url.toString();
}

/** Build the Cognito /logout URL that ends the Hosted UI session. */
export function buildLogoutUrl(params: {
  cognitoDomain: string;
  clientId: string;
  logoutUri: string;
}): string {
  const url = new URL(`https://${params.cognitoDomain}/logout`);
  url.searchParams.set("client_id", params.clientId);
  url.searchParams.set("logout_uri", params.logoutUri);
  return url.toString();
}
