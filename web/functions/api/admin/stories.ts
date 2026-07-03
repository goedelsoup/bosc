// GET  /api/admin/stories        — the moderation review queue (open reports, newest first).
// POST /api/admin/stories         — a moderation action: { action, id }
//     action: "takedown"  id=<story id>  → moderation='removed' (public read 404s instantly)
//             "restore"   id=<story id>  → moderation='ok'
//             "resolve"   id=<report id> → mark a report reviewed
//
// Admin-only (#1098): guarded by STORIES_ENABLED + a valid Cognito Bearer token with the `admin`
// role. The public report endpoint feeds this queue; an admin reviews and takes a story down.

import { json, parseJsonBody } from "../_lib/http";
import { type StoriesEnv, guardStoriesAdmin } from "../_lib/storiesRoute";
import { listReports, resolveReport, setModeration } from "../_lib/storiesStore";

interface RequestContext {
  request: Request;
  env: StoriesEnv;
}

export const onRequestGet = async ({ request, env }: RequestContext): Promise<Response> => {
  const guard = await guardStoriesAdmin(request, env);
  if (!guard.ok) return guard.response;

  const url = new URL(request.url);
  const openOnly = url.searchParams.get("all") !== "true";
  const reports = await listReports(guard.db, { openOnly });
  return json(200, { reports });
};

export const onRequestPost = async ({ request, env }: RequestContext): Promise<Response> => {
  const guard = await guardStoriesAdmin(request, env);
  if (!guard.ok) return guard.response;

  const body = await parseJsonBody(request);
  if (!body.ok) return body.response;
  const v = body.value as Record<string, unknown>;
  const action = typeof v.action === "string" ? v.action : "";
  const id = typeof v.id === "string" ? v.id : "";
  if (!id) return json(400, { error: "id is required" });

  switch (action) {
    case "takedown":
      return json(200, { ok: await setModeration(guard.db, id, "removed") });
    case "restore":
      return json(200, { ok: await setModeration(guard.db, id, "ok") });
    case "resolve":
      return json(200, { ok: await resolveReport(guard.db, id) });
    default:
      return json(400, { error: "invalid action" });
  }
};
