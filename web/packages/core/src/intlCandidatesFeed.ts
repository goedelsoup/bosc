/**
 * Build-time read of the `data-center-candidates` feed (#1394, epic #1387).
 *
 * Split from `intlCandidates.ts` for one concrete reason: that module is imported by the deck.gl
 * island, and a `client:only` island's import graph is bundled for the **browser**. `./bundle`
 * reaches for `node:fs` / `node:path`, so keeping the loader beside the types put Node built-ins
 * in the client build and broke it outright. The types and the pure helpers stay node-free and
 * shared; this one function — the only part that touches the filesystem — lives here, and only
 * the Astro page imports it.
 */

import { hasFeed, loadFeed } from "./bundle";
import { CANDIDATES_FEED, type CandidatesRegister } from "./intlCandidates";

/**
 * The register, or `null` when the feed is absent from this build's bundle.
 *
 * Absent means the sweep has not run — **not** that no data centers exist abroad. The page must
 * say the former; rendering an empty map would say the latter.
 */
export function loadCandidatesRegister(): CandidatesRegister | null {
  return hasFeed(CANDIDATES_FEED) ? loadFeed<CandidatesRegister>(CANDIDATES_FEED) : null;
}
