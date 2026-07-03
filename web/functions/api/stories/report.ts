// POST /api/stories/report — flag a shared Story for admin review (#1098).
//
// Public (no auth — anyone reading a shared story can report it), but abuse-guarded: rate-limited
// per IP, and Turnstile-verified when TURNSTILE_SECRET is configured (skipped when it isn't, since
// the whole feature ships dark behind STORIES_ENABLED). A report files a row on the admin review
// queue; it never changes the story (only an admin takedown does that).

import { json, parseJsonBody } from "../_lib/http";
import { type StoriesEnv, guardPublicStories, writeRateLimit } from "../_lib/storiesRoute";
import { insertReport, storyIdForShareId } from "../_lib/storiesStore";
import { verifyTurnstile } from "../_lib/turnstile";

const REASONS = new Set(["spam", "abuse", "misinformation", "copyright", "other"]);
const MAX_DETAIL = 1000;

interface RequestContext {
  request: Request;
  env: StoriesEnv;
}

export const onRequestPost = async ({ request, env }: RequestContext): Promise<Response> => {
  const guard = guardPublicStories(env);
  if (!guard.ok) return guard.response;

  const limited = await writeRateLimit(request, env);
  if (limited) return limited;

  const body = await parseJsonBody(request);
  if (!body.ok) return body.response;
  const v = body.value as Record<string, unknown>;
  const shareId = typeof v.shareId === "string" ? v.shareId : "";
  const reason = typeof v.reason === "string" ? v.reason : "";
  const detail = typeof v.detail === "string" ? v.detail.slice(0, MAX_DETAIL) : "";
  const token = typeof v.turnstileToken === "string" ? v.turnstileToken : "";

  if (!shareId) return json(400, { error: "shareId is required" });
  if (!REASONS.has(reason)) return json(400, { error: "invalid reason" });

  if (env.TURNSTILE_SECRET) {
    const ip = request.headers.get("cf-connecting-ip") ?? undefined;
    const ok = token ? await verifyTurnstile(token, env.TURNSTILE_SECRET, ip) : false;
    if (!ok) return json(403, { error: "human verification failed" });
  }

  const storyId = await storyIdForShareId(guard.db, shareId);
  // Don't leak whether the share id exists — a bad id reports success just like a good one.
  if (storyId) {
    await insertReport(guard.db, {
      id: crypto.randomUUID(),
      storyId,
      shareId,
      reason,
      detail,
      now: new Date().toISOString(),
    });
  }
  return json(202, { ok: true });
};
