import type { APIRoute } from "astro";
import { hasFeed, loadFeed } from "@watermark/core/bundle";
import type { ReachNetwork, RoutedHydrographNetwork, ScenarioResult } from "@watermark/core/feeds";
import { buildFlowReaches } from "@watermark/viz/flowModel";

// Static feed endpoint: the joined `FlowReach[]` the deck.gl FlowLayer island advects over
// (epic #1237 / #1235) — the `reach-network` river centerlines keyed to `routed-hydrograph`
// magnitude + `hydrology-scenarios` deficit. Empty array when the reference site ships no
// reach network (a non-reference/peer bundle) — the island then renders the locked state.
export const GET: APIRoute = () => {
  const network = hasFeed("reach-network") ? loadFeed<ReachNetwork>("reach-network") : null;
  const routed = hasFeed("routed-hydrograph") ? loadFeed<RoutedHydrographNetwork>("routed-hydrograph") : null;
  const scenarios = hasFeed("hydrology-scenarios") ? loadFeed<ScenarioResult[]>("hydrology-scenarios") : [];
  return new Response(JSON.stringify(buildFlowReaches(network, routed, scenarios)), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
