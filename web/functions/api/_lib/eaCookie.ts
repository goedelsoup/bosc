// Shared helpers for the early-access bypass cookie (__ea).
// Used by both _middleware.ts (verify) and api/account/early-access.ts (mint + verify).
// Keeping them here ensures the test exercises the real signing/verification path.
//
// Cookie format: base64url(sub "|" cookieExp) "." HMAC-SHA256(payload, EARLY_ACCESS_SECRET)
// cookieExp is derived from now + MAX_AGE_SEC (7 days), NOT the id-token's own exp.

export const MAX_AGE_SEC = 60 * 60 * 24 * 7; // 7 days

function b64url(buf: ArrayBuffer | Uint8Array): string {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

/** Mint a signed cookie value for the given sub. The embedded expiry is now + MAX_AGE_SEC. */
export async function mintEaCookie(sub: string, secret: string): Promise<string> {
  const cookieExp = Math.floor(Date.now() / 1000) + MAX_AGE_SEC;
  const payload = b64url(new TextEncoder().encode(`${sub}|${cookieExp}`));
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

/** Verify a cookie value: HMAC integrity + expiry. Returns false on any malformed/expired input. */
export async function isValidEaCookie(value: string, secret: string): Promise<boolean> {
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

  let sigBytes: Uint8Array;
  try {
    const bin = atob(claimedSig.replace(/-/g, "+").replace(/_/g, "/"));
    sigBytes = new Uint8Array(Array.from(bin, (c) => c.charCodeAt(0)));
  } catch {
    return false;
  }

  return crypto.subtle.verify("HMAC", key, sigBytes.buffer as ArrayBuffer, new TextEncoder().encode(payload));
}
