// /api/admin/contacts — the petitioner / site-admin view of the interactive contacts surfaces.
//   GET  ?site=<slug>                          → the hand-off queue (petition connects, WITH the
//                                                 private signer emails) + the full bulletin board.
//   POST { site, action: "moderate", postId, moderation } → take a bulletin post down / restore it.
//
// Guarded by `guardContactsAdmin`: a global `admin` OR a `site-admin` whose `adminSites` includes the
// requested slug — so a petitioner administering their own site sees their own connects (the whole
// point: connecting signers with petitioners) without seeing another site's. Ships dark behind
// CONTACTS_ENABLED.

import { json, parseJsonBody } from "../_lib/http";
import { type ContactsEnv, guardContactsAdmin } from "../_lib/contactsRoute";
import {
  type BulletinModeration,
  listBulletinPostsForAdmin,
  listConnectsForAdmin,
  setBulletinModeration,
} from "../_lib/contactsStore";

interface RequestContext {
  request: Request;
  env: ContactsEnv;
}

/** GET ?site=&contactId? — the hand-off queue + the full board for a site the caller administers. */
export const onRequestGet = async ({ request, env }: RequestContext): Promise<Response> => {
  const url = new URL(request.url);
  const site = (url.searchParams.get("site") ?? "").trim();
  const contactId = (url.searchParams.get("contactId") ?? "").trim() || undefined;
  if (!site) return json(400, { error: "site is required" });

  const guard = await guardContactsAdmin(request, env, site);
  if (!guard.ok) return guard.response;

  const [connects, posts] = await Promise.all([
    listConnectsForAdmin(guard.db, site, { contactId }),
    listBulletinPostsForAdmin(guard.db, site),
  ]);
  return json(200, { connects, posts });
};

const MODERATIONS = new Set<BulletinModeration>(["ok", "removed"]);

/** POST { site, action:"moderate", postId, moderation } — take a post down / restore it. */
export const onRequestPost = async ({ request, env }: RequestContext): Promise<Response> => {
  const body = await parseJsonBody(request);
  if (!body.ok) return body.response;
  const v = body.value as Record<string, unknown>;
  const site = typeof v.site === "string" ? v.site.trim() : "";
  if (!site) return json(400, { error: "site is required" });

  const guard = await guardContactsAdmin(request, env, site);
  if (!guard.ok) return guard.response;

  const action = typeof v.action === "string" ? v.action : "";
  if (action !== "moderate") return json(400, { error: "unknown action" });
  const postId = typeof v.postId === "string" ? v.postId : "";
  const moderation = (typeof v.moderation === "string" ? v.moderation : "") as BulletinModeration;
  if (!postId) return json(400, { error: "postId is required" });
  if (!MODERATIONS.has(moderation)) return json(400, { error: "invalid moderation" });

  const changed = await setBulletinModeration(guard.db, postId, moderation);
  return json(changed ? 200 : 404, { ok: changed });
};
