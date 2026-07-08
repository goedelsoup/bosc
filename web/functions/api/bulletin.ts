// /api/bulletin — the site community bulletin board.
//   GET  ?site=<slug>   → the public board (un-removed posts, newest first; no private reply-to).
//   POST { site, ... }  → create a post (public, moderated, abuse-guarded).
//
// Public on both verbs (no account needed to read or post), but writes are rate-limited per IP and
// Turnstile-verified when TURNSTILE_SECRET is set. Ships dark behind CONTACTS_ENABLED. Admin takedown
// lives at /api/admin/contacts. The author's reply-to (author_contact) is private — never returned by
// the public GET.

import { json, parseJsonBody } from "./_lib/http";
import { type ContactsEnv, guardPublicContacts, writeRateLimit } from "./_lib/contactsRoute";
import { insertBulletinPost, listPublicBulletinPosts } from "./_lib/contactsStore";
import { verifyTurnstile } from "./_lib/turnstile";

const MAX_NAME = 120;
const MAX_TITLE = 160;
const MAX_BODY = 4000;
const MAX_CONTACT = 254;

interface RequestContext {
  request: Request;
  env: ContactsEnv;
}

/** GET ?site= — the public board (un-removed posts, newest first). */
export const onRequestGet = async ({ request, env }: RequestContext): Promise<Response> => {
  const guard = guardPublicContacts(env);
  if (!guard.ok) return guard.response;
  const site = (new URL(request.url).searchParams.get("site") ?? "").trim();
  if (!site) return json(400, { error: "site is required" });
  const posts = await listPublicBulletinPosts(guard.db, site);
  return json(200, { posts });
};

/** POST — create a bulletin post. 201 on success; 4xx only on malformed input / failed verification. */
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
  const authorName = typeof v.authorName === "string" ? v.authorName.trim().slice(0, MAX_NAME) : "";
  const authorContact =
    typeof v.authorContact === "string" ? v.authorContact.trim().slice(0, MAX_CONTACT) : "";
  const title = typeof v.title === "string" ? v.title.trim().slice(0, MAX_TITLE) : "";
  const postBody = typeof v.body === "string" ? v.body.trim().slice(0, MAX_BODY) : "";
  const token = typeof v.turnstileToken === "string" ? v.turnstileToken : "";

  if (!site) return json(400, { error: "site is required" });
  if (!authorName) return json(400, { error: "a name is required" });
  if (!title) return json(400, { error: "a title is required" });
  if (!postBody) return json(400, { error: "a message is required" });

  if (env.TURNSTILE_SECRET) {
    const ip = request.headers.get("cf-connecting-ip") ?? undefined;
    const ok = token ? await verifyTurnstile(token, env.TURNSTILE_SECRET, ip) : false;
    if (!ok) return json(403, { error: "human verification failed" });
  }

  const id = crypto.randomUUID();
  await insertBulletinPost(guard.db, {
    id,
    site,
    contactId,
    authorName,
    authorContact,
    title,
    body: postBody,
    now: new Date().toISOString(),
  });
  return json(201, { ok: true, id });
};
