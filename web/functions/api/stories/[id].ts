// GET    /api/stories/:id — the authenticated user's Story (source + parsed SDM + refs).
// PUT    /api/stories/:id — recompile + validate + transactionally replace the Story and its refs.
// DELETE /api/stories/:id — delete the Story (refs cascade).
//
// All owner-scoped (#1092): a Story that isn't the caller's reads as 404, never leaks. Ships dark
// behind STORIES_ENABLED; requires the STORIES_HYPERDRIVE binding (Lakebase/Postgres) + a valid Cognito Bearer token.

import { loadCatalogAsset } from "../_lib/catalogAsset";
import { json, parseJsonBody } from "../_lib/http";
import {
  type StoriesEnv,
  guardStories,
  publishGate,
  storyDetail,
  writeRateLimit,
} from "../_lib/storiesRoute";
import { deleteStory, getStory, updateStory } from "../_lib/storiesStore";
import { buildStoryWrite, parseStoryInput } from "../_lib/storyWrite";

interface RequestContext {
  request: Request;
  env: StoriesEnv;
  params: { id: string };
}

export const onRequestGet = async ({ request, env, params }: RequestContext): Promise<Response> => {
  const guard = await guardStories(request, env);
  if (!guard.ok) return guard.response;

  const found = await getStory(guard.db, guard.owner, params.id);
  if (!found) return json(404, { error: "not found" });
  return json(200, { story: storyDetail(found.story, found.refs) });
};

export const onRequestPut = async ({ request, env, params }: RequestContext): Promise<Response> => {
  const guard = await guardStories(request, env);
  if (!guard.ok) return guard.response;

  const limited = await writeRateLimit(request, env);
  if (limited) return limited;

  const body = await parseJsonBody(request);
  if (!body.ok) return body.response;
  const parsed = parseStoryInput(body.value);
  if (!parsed.ok) return json(400, { error: parsed.error });

  let catalog: Awaited<ReturnType<typeof loadCatalogAsset>>;
  try {
    catalog = await loadCatalogAsset(request.url, env.STORIES_CATALOG_URL);
  } catch {
    return json(500, { error: "catalog unavailable" });
  }

  const built = buildStoryWrite(parsed.input, catalog);
  if (!built.ok) return json(400, { error: "story failed validation", errors: built.errors });

  // Publishing (incl. republishing) is early-access-gated (#1098); unpublish/draft is always allowed.
  const blocked = publishGate(guard.ctx, built.write.status);
  if (blocked) return blocked;

  const now = new Date().toISOString();
  const shareId = crypto.randomUUID(); // candidate — used iff this publish is the first one
  let ok: boolean;
  try {
    ok = await updateStory(guard.db, guard.owner, params.id, built.write, now, shareId);
  } catch {
    return json(409, { error: "a story with that slug already exists" });
  }
  if (!ok) return json(404, { error: "not found" });
  const saved = await getStory(guard.db, guard.owner, params.id);
  return json(200, { id: params.id, share_id: saved?.story.share_id ?? null });
};

export const onRequestDelete = async ({ request, env, params }: RequestContext): Promise<Response> => {
  const guard = await guardStories(request, env);
  if (!guard.ok) return guard.response;

  const removed = await deleteStory(guard.db, guard.owner, params.id);
  if (!removed) return json(404, { error: "not found" });
  return json(200, { id: params.id });
};
