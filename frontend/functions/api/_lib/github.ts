// GitHub App auth + issue creation, using only Web Crypto + fetch (no dependencies),
// so it runs on the Cloudflare Workers runtime. The flow: sign a short-lived App JWT
// (RS256) → exchange it for a repo-scoped installation token (further narrowed to
// issues:write) → create the issue. See docs/submissions-api.md.
//
// The App private key must be **PKCS#8** (`-----BEGIN PRIVATE KEY-----`). GitHub
// downloads a PKCS#1 key (`-----BEGIN RSA PRIVATE KEY-----`); convert it once with
// `openssl pkcs8 -topk8 -nocrypt -in app.pem -out app.pkcs8.pem` (bootstrap step).

import { submissionMarker, type IssueDraft } from "./issue";

const API = "https://api.github.com";
const UA = "bosc-tips-bot";

function b64url(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function pemToDer(pem: string): Uint8Array<ArrayBuffer> {
  const b64 = pem
    .replace(/-----BEGIN [^-]+-----/g, "")
    .replace(/-----END [^-]+-----/g, "")
    .replace(/\s+/g, "");
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function appJwt(appId: string, privateKeyPem: string): Promise<string> {
  const enc = new TextEncoder();
  const now = Math.floor(Date.now() / 1000);
  // iat backdated 60s for clock drift; exp well under GitHub's 10-minute ceiling.
  const header = b64url(enc.encode(JSON.stringify({ alg: "RS256", typ: "JWT" })));
  const payload = b64url(enc.encode(JSON.stringify({ iat: now - 60, exp: now + 540, iss: appId })));
  const signingInput = `${header}.${payload}`;

  const key = await crypto.subtle.importKey(
    "pkcs8",
    pemToDer(privateKeyPem),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, enc.encode(signingInput));
  return `${signingInput}.${b64url(new Uint8Array(sig))}`;
}

function ghHeaders(token: string, scheme: "Bearer" | "token"): Record<string, string> {
  return {
    Authorization: `${scheme} ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": UA,
  };
}

async function installationToken(jwt: string, owner: string, repo: string): Promise<string> {
  const inst = await fetch(`${API}/repos/${owner}/${repo}/installation`, {
    headers: ghHeaders(jwt, "Bearer"),
  });
  if (!inst.ok) throw new Error(`installation lookup failed (${inst.status})`);
  const { id } = (await inst.json()) as { id: number };

  // Narrow the token to issues:write even though the App itself is issues-only.
  const tok = await fetch(`${API}/app/installations/${id}/access_tokens`, {
    method: "POST",
    headers: { ...ghHeaders(jwt, "Bearer"), "Content-Type": "application/json" },
    body: JSON.stringify({ permissions: { issues: "write" } }),
  });
  if (!tok.ok) throw new Error(`token mint failed (${tok.status})`);
  const { token } = (await tok.json()) as { token: string };
  return token;
}

/**
 * Dedupe (Phase 5): scan the open `submission` issues for one already carrying this
 * run's marker and return its URL, else null. Best-effort — only the first page (100)
 * of open submissions is checked, and any error returns null (proceed to create) so a
 * dedupe hiccup never drops a legitimate submission. The triage queue is kept bounded
 * by closing handled issues (they leave `state=open`).
 */
async function findOpenSubmission(
  token: string,
  owner: string,
  repo: string,
  marker: string,
): Promise<string | null> {
  try {
    const res = await fetch(
      `${API}/repos/${owner}/${repo}/issues?labels=submission&state=open&per_page=100`,
      { headers: ghHeaders(token, "token") },
    );
    if (!res.ok) return null;
    const issues = (await res.json()) as Array<{ html_url: string; body: string | null }>;
    return issues.find((i) => (i.body ?? "").includes(marker))?.html_url ?? null;
  } catch {
    return null;
  }
}

export interface FileResult {
  url: string;
  /** True when an existing open issue carried the same marker (no new issue opened). */
  deduped: boolean;
}

export async function fileIssueAsApp(opts: {
  appId: string;
  privateKey: string;
  owner: string;
  repo: string;
  issue: IssueDraft;
  dedupeHash: string;
}): Promise<FileResult> {
  const jwt = await appJwt(opts.appId, opts.privateKey);
  const token = await installationToken(jwt, opts.owner, opts.repo);

  const existing = await findOpenSubmission(token, opts.owner, opts.repo, submissionMarker(opts.dedupeHash));
  if (existing) return { url: existing, deduped: true };

  const res = await fetch(`${API}/repos/${opts.owner}/${opts.repo}/issues`, {
    method: "POST",
    headers: { ...ghHeaders(token, "token"), "Content-Type": "application/json" },
    body: JSON.stringify(opts.issue),
  });
  if (!res.ok) throw new Error(`issue create failed (${res.status})`);
  const { html_url } = (await res.json()) as { html_url: string };
  return { url: html_url, deduped: false };
}
