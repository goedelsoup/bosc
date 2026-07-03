// GET  /api/stories — list the authenticated user's own Stories (summaries, newest first).
// POST /api/stories — create a Story: compile the source against the live catalog, validate every
//                     handle, and transactionally persist the Story + its refs.
//
// User-owned by construction (#1092). Ships dark behind STORIES_ENABLED; requires the STORIES_DB
// D1 binding + a valid Cognito Bearer token. Mirrors the submit/ask Function shape.

import { loadCatalogAsset } from "./_lib/catalogAsset";
import { json, parseJsonBody } from "./_lib/http";
import { type StoriesEnv, guardStories, storySummary, writeRateLimit } from "./_lib/storiesRoute";
import { createStory, listStories } from "./_lib/storiesStore";
import { buildStoryWrite, parseStoryInput } from "./_lib/storyWrite";

interface RequestContext {
  request: Request;
  env: StoriesEnv;
}

export const onRequestGet = async ({ request, env }: RequestContext): Promise<Response> => {
  const guard = await guardStories(request, env);
  if (!guard.ok) return guard.response;

  const rows = await listStories(guard.db, guard.owner);
  return json(200, { stories: rows.map(storySummary) });
};

export const onRequestPost = async ({ request, env }: RequestContext): Promise<Response> => {
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

  // Server-side write path (#1094): compile + validate every handle before persist.
  const built = buildStoryWrite(parsed.input, catalog);
  if (!built.ok) return json(400, { error: "story failed validation", errors: built.errors });

  const id = crypto.randomUUID();
  const now = new Date().toISOString();
  try {
    await createStory(guard.db, guard.owner, id, built.write, now);
  } catch {
    // The most likely failure is the unique (owner, site, slug) constraint.
    return json(409, { error: "a story with that slug already exists" });
  }

  return json(201, { id });
};
