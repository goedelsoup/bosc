// GET /api/stories/shared/:shareId — the public, read-only view of a shared Walk (#1098).
//
// The ONLY unauthenticated read path: resolves a *published, un-removed* Walk by its unguessable
// share_id and returns the public projection (no owner id, no editable source). A draft, an
// unpublished, or an admin-removed Walk returns 404 — a stale share URL leaks nothing. Still behind
// the STORIES_ENABLED kill switch + needs the STORIES_HYPERDRIVE binding (Lakebase/Postgres).

import { json } from "../../_lib/http";
import { type StoriesEnv, guardPublicStories, publicStory } from "../../_lib/storiesRoute";
import { getPublicStory } from "../../_lib/storiesStore";

interface RequestContext {
  request: Request;
  env: StoriesEnv;
  params: { shareId: string };
}

export const onRequestGet = async ({ env, params }: RequestContext): Promise<Response> => {
  const guard = guardPublicStories(env);
  if (!guard.ok) return guard.response;

  const found = await getPublicStory(guard.db, params.shareId);
  if (!found) return json(404, { error: "not found" });
  return json(200, { story: publicStory(found.story, found.refs) });
};
