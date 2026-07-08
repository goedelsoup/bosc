// POST /api/petition/connect — connect a reader who wants to sign with the petitioner they chose.
//
// This does NOT warehouse a signature: it captures a minimal opt-in (a private routing email, an
// optional public display name + note) and files it to the petitioner's hand-off queue. The signer's
// email is private — the public surface is only a count + opt-in display names (GET below).
//
// Public (no auth — anyone reading the contacts directory can ask to connect), but abuse-guarded:
// rate-limited per IP, and Turnstile-verified when TURNSTILE_SECRET is configured (skipped when it
// isn't, since the whole feature ships dark behind CONTACTS_ENABLED). Returns 202 unconditionally so
// a probe can't distinguish a real petitioner from a bogus contact_id (no existence leak).

import { json, parseJsonBody } from "../_lib/http";
import { type ContactsEnv, guardPublicContacts, writeRateLimit } from "../_lib/contactsRoute";
import { insertPetitionConnect, publicConnectTally } from "../_lib/contactsStore";
import { verifyTurnstile } from "../_lib/turnstile";

const MAX_NAME = 120;
const MAX_MESSAGE = 1000;
const MAX_EMAIL = 254;
// A deliberately permissive shape check — real deliverability is the petitioner's problem, we only
// guard against obvious junk so the queue stays usable.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface RequestContext {
  request: Request;
  env: ContactsEnv;
}

/** POST — file a connect request. 202 on success (no existence leak), 4xx only on malformed input. */
export const onRequestPost = async ({ request, env }: RequestContext): Promise<Response> => {
  const guard = guardPublicContacts(env);
  if (!guard.ok) return guard.response;

  const limited = await writeRateLimit(request, env);
  if (limited) return limited;

  const body = await parseJsonBody(request);
  if (!body.ok) return body.response;
  const v = body.value as Record<string, unknown>;
  const site = typeof v.site === "string" ? v.site.trim() : "";
  const contactId = typeof v.contactId === "string" ? v.contactId.trim() : "";
  const email = typeof v.email === "string" ? v.email.trim().slice(0, MAX_EMAIL) : "";
  const displayName = typeof v.displayName === "string" ? v.displayName.trim().slice(0, MAX_NAME) : "";
  const message = typeof v.message === "string" ? v.message.slice(0, MAX_MESSAGE) : "";
  const token = typeof v.turnstileToken === "string" ? v.turnstileToken : "";

  if (!site) return json(400, { error: "site is required" });
  if (!contactId) return json(400, { error: "contactId is required" });
  if (!EMAIL_RE.test(email)) return json(400, { error: "a valid email is required to connect" });

  if (env.TURNSTILE_SECRET) {
    const ip = request.headers.get("cf-connecting-ip") ?? undefined;
    const ok = token ? await verifyTurnstile(token, env.TURNSTILE_SECRET, ip) : false;
    if (!ok) return json(403, { error: "human verification failed" });
  }

  await insertPetitionConnect(guard.db, {
    id: crypto.randomUUID(),
    site,
    contactId,
    displayName,
    email,
    message,
    now: new Date().toISOString(),
  });
  return json(202, { ok: true });
};

/** GET ?site=&contactId= — the PUBLIC tally: count + opt-in display names (never the private emails). */
export const onRequestGet = async ({ request, env }: RequestContext): Promise<Response> => {
  const guard = guardPublicContacts(env);
  if (!guard.ok) return guard.response;
  const url = new URL(request.url);
  const site = (url.searchParams.get("site") ?? "").trim();
  const contactId = (url.searchParams.get("contactId") ?? "").trim();
  if (!site || !contactId) return json(400, { error: "site and contactId are required" });
  const tally = await publicConnectTally(guard.db, site, contactId);
  return json(200, tally);
};
