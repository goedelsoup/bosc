/**
 * Browser-side plumbing shared by the interactive contacts islands (petition-connect + bulletin).
 * The endpoints are PUBLIC (no auth — the peer of `report.ts`), so this is a thin typed fetch with
 * no bearer token. Keep this the only place that knows the endpoint shapes. Writes stay
 * server-authoritative; the UI never assumes a write succeeded without the response.
 */

/** The Pages Functions live at the origin root (never under the deploy base). */
export const PETITION_API = "/api/petition/connect";
export const BULLETIN_API = "/api/bulletin";

export type ApiResult<T> = { ok: true; value: T } | { ok: false; status: number; error?: string };

async function parse<T>(res: Response): Promise<ApiResult<T>> {
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    // no body / non-JSON
  }
  if (res.ok) return { ok: true, value: data as T };
  const error = data && typeof data === "object" ? (data as { error?: string }).error : undefined;
  return { ok: false, status: res.status, error };
}

// --- petition-connect ----------------------------------------------------------------------

export interface ConnectTally {
  contact_id: string;
  count: number;
  names: string[];
}

export interface ConnectInput {
  site: string;
  contactId: string;
  email: string;
  displayName?: string;
  message?: string;
  turnstileToken?: string;
}

/** The public tally for one petitioner (count + opt-in display names). */
export async function getConnectTally(site: string, contactId: string): Promise<ApiResult<ConnectTally>> {
  const q = new URLSearchParams({ site, contactId });
  return parse<ConnectTally>(await fetch(`${PETITION_API}?${q}`));
}

/** File a petition-connect (202 on success). */
export async function submitConnect(input: ConnectInput): Promise<ApiResult<{ ok: true }>> {
  return parse<{ ok: true }>(
    await fetch(PETITION_API, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

// --- bulletin board ------------------------------------------------------------------------

export interface BulletinPost {
  id: string;
  site: string;
  contact_id: string;
  author_name: string;
  title: string;
  body: string;
  created_at: string;
}

export interface BulletinInput {
  site: string;
  authorName: string;
  title: string;
  body: string;
  authorContact?: string;
  contactId?: string;
  turnstileToken?: string;
}

/** The public board for a site (un-removed posts, newest first). */
export async function listBulletin(site: string): Promise<ApiResult<{ posts: BulletinPost[] }>> {
  const q = new URLSearchParams({ site });
  return parse<{ posts: BulletinPost[] }>(await fetch(`${BULLETIN_API}?${q}`));
}

/** Create a bulletin post (201 on success). */
export async function submitBulletin(input: BulletinInput): Promise<ApiResult<{ ok: true; id: string }>> {
  return parse<{ ok: true; id: string }>(
    await fetch(BULLETIN_API, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}
