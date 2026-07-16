/**
 * The build-time **render catalog** (#1097) — the hydrated peer of the thin resolver catalog. The
 * runtime renderer is a client island and can't read the content bundle off disk, so the reader
 * page emits this as a static `/stories-atoms.json` asset (the same static-asset-at-runtime pattern
 * as `/stories-catalog.json` and `/ask-index.json`); the island fetches it and resolves each SDM
 * `atom` handle against it.
 *
 * For every real, addressable handle in the merged catalog (`catalogBuild.loadCatalog`) it emits at
 * least the thin card (`hydrateFromThin`); where the fixture recognizes a handle it overlays the
 * rich embedded payload. Richer live hydration — reading each kind's full feed row in the Python
 * tier — is the follow-up; this keeps the renderer honest today (it renders what's addressable and
 * never fabricates fields) while staying end-to-end wireable against the sample bundle.
 */
import { loadCatalog } from "./catalogBuild";
import { type HydratedCatalog, hydrateFromThin } from "./storyAtoms";
import { FIXTURE_CATALOG } from "./storyAtoms.fixture";

/** Assemble the hydrated render catalog for a site: every thin atom, enriched where recognized. */
export function buildRenderCatalog(site?: string): HydratedCatalog {
  const catalog = site ? loadCatalog(site) : loadCatalog();
  const out: HydratedCatalog = {};
  for (const atom of catalog.byHandle.values()) {
    const rich = FIXTURE_CATALOG[atom.handle];
    out[atom.handle] = rich ?? hydrateFromThin(atom);
  }
  return out;
}
