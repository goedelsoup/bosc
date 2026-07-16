/**
 * Flow-view join (epic #1237 / #1235) — turns the three shipping feeds into the
 * `FlowReach[]` the `FlowLayer` advects over, keyed by reach `node_id`. Pure + typed, so it
 * unit-tests offline and the runtime `/feeds/flow.json` endpoint and the island share one
 * join. No deck.gl import.
 *
 * The join:
 *   - **geometry** comes from the `reach-network` feed (`ReachNetwork`, real NHDPlus lines);
 *   - **magnitude** (particle density + speed) from the `routed-hydrograph` feed — each
 *     reach's routed `outflow_peak_cfs`, normalized against the network max, so attenuation
 *     down the reaches reads as thinning/slowing flow;
 *   - **deficit** (oxblood + thinned) from the `hydrology-scenarios` worst case: a reach is
 *     stressed when its receiving water fails its low-flow assimilative screen (a `violation`
 *     flag), or the mainstem's consumptive loss exceeds the cited 7Q10 (draw > supply).
 */
import type { ReachNetwork, RoutedHydrographNetwork, ScenarioResult } from "@watermark/core/feeds";
import { type FlowReach, normalizeMagnitude } from "./flow";

/** A reach ready to draw, plus the labels the island's legend/probe show. */
export interface FlowReachView extends FlowReach {
  /** Human name (e.g. "Ottawa River at Lima"). */
  name: string;
  /** The receiving water this reach is on. */
  receivingWater: string | null;
  /** The routed storm-peak magnitude behind the encoding, for the probe (cfs). */
  magnitudeCfs: number | null;
}

/** The worst-case scenario = the one with the largest modeled consumptive loss. */
export function worstScenario(scenarios: ScenarioResult[]): ScenarioResult | null {
  if (scenarios.length === 0) return null;
  return scenarios.reduce((a, b) =>
    (b.consumptive_loss?.value ?? 0) > (a.consumptive_loss?.value ?? 0) ? b : a,
  );
}

/** The set of receiving waters that fail their low-flow screen in the worst scenario. */
export function deficitReceivingWaters(scenarios: ScenarioResult[]): Set<string> {
  const worst = worstScenario(scenarios);
  const out = new Set<string>();
  if (!worst) return out;
  // Per-discharger assimilative violations — the receiving water can't dilute the effluent.
  for (const check of worst.assimilative ?? []) {
    if (check.flag === "violation" && check.receiving_water) out.add(check.receiving_water);
  }
  // Mainstem consumptive draw > cited design low flow (the reach can't spare the water).
  const draw = worst.consumptive_loss?.value;
  const low = worst.receiving_7q10?.value;
  if (draw != null && low != null && draw > low && worst.receiving_water_name) {
    out.add(worst.receiving_water_name);
  }
  return out;
}

/**
 * Build the `FlowReach[]` for the FlowLayer from the three feeds. Reaches with fewer than two
 * geometry vertices are dropped (nothing to advect). A reach absent from the routed hydrograph
 * keeps a faint baseline magnitude rather than vanishing — the geometry is still real.
 */
export function buildFlowReaches(
  network: ReachNetwork | null,
  routed: RoutedHydrographNetwork | null,
  scenarios: ScenarioResult[],
): FlowReachView[] {
  if (!network || network.reaches.length === 0) return [];

  const peakByNode = new Map<string, number>();
  for (const r of routed?.reaches ?? []) peakByNode.set(r.node_id, r.outflow_peak_cfs);
  const maxPeak = Math.max(1, ...peakByNode.values());
  const deficitWaters = deficitReceivingWaters(scenarios);

  return network.reaches
    .filter((r) => r.coordinates.length >= 2)
    .map((r): FlowReachView => {
      const peak = peakByNode.get(r.node_id) ?? null;
      const magnitude = normalizeMagnitude(peak ?? 0.2 * maxPeak, maxPeak);
      const deficit = r.receiving_water != null && deficitWaters.has(r.receiving_water);
      return {
        id: r.node_id,
        name: r.name,
        receivingWater: r.receiving_water ?? null,
        path: r.coordinates,
        speed: magnitude,
        density: magnitude,
        deficit,
        magnitudeCfs: peak,
      };
    });
}
