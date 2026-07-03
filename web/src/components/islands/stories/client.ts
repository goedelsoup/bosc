/**
 * Browser-side plumbing shared by the Story islands (#1096/#1097): authed fetch against the
 * `/api/stories` Functions, the render-catalog asset load, and the wire types the endpoints return.
 * Keep this the only place that knows the endpoint shapes, so the reader/editor/my-stories islands
 * stay declarative.
 */
import { getIdToken } from "~/lib/auth";
import type { StoryDocument } from "~/lib/sdm";
import type { HydratedAtom, HydratedCatalog } from "~/lib/storyAtoms";

/** The Pages Functions live at the origin root (never under the deploy base). */
export const STORIES_API = "/api/stories";

export interface StorySummary {
  id: string;
  site: string;
  slug: string;
  title: string;
  dek: string;
  status: "draft" | "published";
  share_id: string | null;
  catalog_version: string;
  created_at: string;
  updated_at: string;
}

export interface StoryRefWire {
  ord: number;
  handle: string;
  kind: string;
  title: string;
}

export interface StoryDetail extends StorySummary {
  source_format: "dsl" | "mdx-data";
  source_text: string;
  sdm: StoryDocument;
  refs: StoryRefWire[];
}

/** The public projection of a shared Story (#1098) — no owner id / editable source. */
export interface PublicStory {
  share_id: string;
  site: string;
  title: string;
  dek: string;
  published_at: string | null;
  sdm: StoryDocument;
  refs: StoryRefWire[];
}

export type ReportReason = "spam" | "abuse" | "misinformation" | "copyright" | "other";

export interface AuthorError {
  kind: string;
  message: string;
  line?: number;
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getIdToken();
  return token ? { authorization: `Bearer ${token}`, ...extra } : extra;
}

export type ApiResult<T> =
  | { ok: true; value: T }
  | { ok: false; status: number; error?: string; errors?: AuthorError[] };

async function parse<T>(res: Response): Promise<ApiResult<T>> {
  if (res.ok) return { ok: true, value: (await res.json()) as T };
  let body: { error?: string; errors?: AuthorError[] } = {};
  try {
    body = (await res.json()) as typeof body;
  } catch {
    /* non-JSON error body */
  }
  return { ok: false, status: res.status, error: body.error, errors: body.errors };
}

export async function listStories(): Promise<ApiResult<{ stories: StorySummary[] }>> {
  return parse(await fetch(STORIES_API, { headers: authHeaders() }));
}

export async function getStory(id: string): Promise<ApiResult<{ story: StoryDetail }>> {
  return parse(await fetch(`${STORIES_API}/${encodeURIComponent(id)}`, { headers: authHeaders() }));
}

export interface StoryInput {
  site: string;
  slug: string;
  title: string;
  dek: string;
  status: "draft" | "published";
  source_format: "dsl" | "mdx-data";
  source_text: string;
}

/** Create/update responses carry the minted `share_id` (present once the Story is published). */
export interface SaveResult {
  id: string;
  share_id: string | null;
}

export async function createStory(input: StoryInput): Promise<ApiResult<SaveResult>> {
  return parse(
    await fetch(STORIES_API, {
      method: "POST",
      headers: authHeaders({ "content-type": "application/json" }),
      body: JSON.stringify(input),
    }),
  );
}

export async function updateStory(id: string, input: StoryInput): Promise<ApiResult<SaveResult>> {
  return parse(
    await fetch(`${STORIES_API}/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: authHeaders({ "content-type": "application/json" }),
      body: JSON.stringify(input),
    }),
  );
}

export async function deleteStory(id: string): Promise<ApiResult<{ ok: true }>> {
  return parse(
    await fetch(`${STORIES_API}/${encodeURIComponent(id)}`, { method: "DELETE", headers: authHeaders() }),
  );
}

/** The public share read (#1098) — no auth. `shareId` comes from the `?share=` URL param. */
export async function getPublicStory(shareId: string): Promise<ApiResult<{ story: PublicStory }>> {
  return parse(await fetch(`${STORIES_API}/shared/${encodeURIComponent(shareId)}`));
}

/** Flag a shared Story for admin review (#1098). Public; Turnstile token optional. */
export async function reportStory(
  shareId: string,
  reason: ReportReason,
  detail = "",
  turnstileToken?: string,
): Promise<ApiResult<{ ok: true }>> {
  return parse(
    await fetch(`${STORIES_API}/report`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ shareId, reason, detail, turnstileToken }),
    }),
  );
}

/**
 * Fetch the per-site render-catalog asset (`…/stories-atoms.json`) — the hydrated atoms the renderer
 * resolves each handle against. Returns `null` on a failed / non-OK fetch (a *load error*, distinct
 * from a genuinely empty `{}` catalog) so callers can show "couldn't load, try again" rather than
 * marking every citation as dangling. `url` is site-specific (built via `withSite` on the page), so
 * a non-Lima page never resolves against Lima's atoms.
 */
export async function loadRenderCatalog(url: string): Promise<HydratedCatalog | null> {
  let res: Response;
  try {
    res = await fetch(url);
  } catch {
    return null;
  }
  if (!res.ok) return null;
  try {
    const body = (await res.json()) as { atoms?: HydratedAtom[] };
    const out: HydratedCatalog = {};
    for (const a of body.atoms ?? []) out[a.handle] = a;
    return out;
  } catch {
    return null;
  }
}
