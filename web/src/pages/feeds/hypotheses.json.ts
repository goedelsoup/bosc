import type { APIRoute } from "astro";
import { getHypotheses, hasFeed, loadFeed } from "@watermark/core/bundle";
import type { HypothesisAssessmentItem } from "@watermark/core/feeds";

// Emits a joined payload: { hypotheses, assessments } so the get_hypotheses MCP
// tool can join on hypothesis.id client-side without a second round-trip.
export const GET: APIRoute = () => {
  const hypotheses = getHypotheses();
  const assessments = hasFeed("hypothesis-assessments")
    ? loadFeed<HypothesisAssessmentItem[]>("hypothesis-assessments")
    : [];
  return new Response(JSON.stringify({ hypotheses, assessments }), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
