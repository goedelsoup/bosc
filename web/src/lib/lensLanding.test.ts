// The site-tier lens landing's shape (#1915, epic #1911 phase 3).
//
// A source scan, for the same reason `hubLede.test.ts` and `trailCoverage.test.ts` are: the
// assertions are about a TEMPLATE's shape, and the specific shape at issue here cannot be reached
// by rendering. Lens routes are emitted for SELECTABLE sites only, and all four selectable sites
// today have every activation domain lit — so `lensStatus` is `available` on all twenty built
// pages and the locked branch never renders in the build the other gates inspect.
//
// That branch is an acceptance criterion ("a locked lens on a thin peer renders the coherent lock
// and the ask, never an empty page"), and it becomes reachable the moment a thinner peer is
// promoted to selectable — which is exactly when nobody will be looking at it. So it is asserted
// against the source now rather than left to the first promotion to discover.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { LENS_ORDER, LENSES } from "@watermark/core/lenses";
import { SECTION_META, type ReadinessSection } from "@watermark/core/readiness";

const LANDING = "src/pages/network/[site]/lens/[lens].astro";
const source = readFileSync(LANDING, "utf8");

describe("the lens landing gates on lensStatus", () => {
  it("reads the composed gate rather than re-deriving one", () => {
    // `lensStatus` composes the same `ReadinessSection`s and domains everything else reads (#1913).
    // A page that reached for `hasFeed` or `siteTier` instead would be a second gate that drifts.
    expect(source).toMatch(/lensStatus\(slug, id\) === "locked"/);
    expect(source).not.toMatch(/isReferenceSite/);
  });

  it("renders the coherent lock, with the lens's own name on it", () => {
    // `SectionLocked` defaults its heading to the SECTION's label ("The environment"); a lens must
    // pass its own, or a locked Land lens would introduce itself as Places (#1886's rule for
    // record facets, applied here).
    expect(source).toContain("<SectionLocked");
    expect(source).toMatch(/label=\{lens\.name\}/);
    expect(source).toMatch(/section=\{lens\.lockSection\}/);
  });

  it("never lets a locked lens fall through to the door grid", () => {
    // The failure this blocks is an empty page: doors filtered to nothing plus no lock. The lock
    // and the body are the two arms of one ternary, so there is no third path.
    const lockAt = source.indexOf("<SectionLocked");
    const gridAt = source.indexOf('class="hub-grid"');
    expect(lockAt).toBeGreaterThan(0);
    expect(gridAt).toBeGreaterThan(lockAt);
    expect(source.slice(lockAt, gridAt)).toContain(") : (");
  });

  it("offers a door only where this site's own record is behind it", () => {
    // Record facets carry their declared gate; the rest name the feeds that open them. A landing
    // that linked every facet unconditionally would advertise doors onto locks — the exact defect
    // that made the merged Reference dropdown collapse to a landing link on a thin peer.
    expect(source).toMatch(/facetAvailable\(slug, f\.facet\)/);
    expect(source).toMatch(/f\.requires\.some\(/);
    expect(source).toMatch(/lens\.facets\.filter\(offered\)/);
    // …and what is withheld is named, not silently dropped.
    expect(source).toContain("Still awaiting a source here");
  });
});

describe("every lens can render a lock", () => {
  it("borrows lock copy from a real readiness section", () => {
    const sections = Object.keys(SECTION_META) as ReadinessSection[];
    for (const id of LENS_ORDER) {
      expect(sections, `${id}.lockSection`).toContain(LENSES[id].lockSection);
      // The borrowed part is the "what lands here" line only; a lens with no `holds` of its own
      // would inherit a section's copy wholesale, which is how a Land lock starts saying "places".
      expect(LENSES[id].blurb.length).toBeGreaterThan(40);
    }
  });
});
