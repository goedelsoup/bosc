/**
 * The international candidates reader (#1394, epic #1387).
 *
 * These tests are about the *presentation* rules, not the evidentiary ones — the latter are
 * enforced in Python (`tests/test_international_candidates.py`) and arrive on the feed as
 * computed fields. What can still go wrong on this side is a renderer quietly flattening a
 * contested attribution into a clean name, so that is what is pinned hardest here.
 */
import { describe, expect, it } from "vitest";
import {
  type Candidate,
  type CandidatesRegister,
  type OperatorAttribution,
  type PriorObservation,
  aoiSummaries,
  attributionView,
  contested,
  corroborated,
  singleSource,
} from "./intlCandidates";

function obs(source: PriorObservation["source"], id: string): PriorObservation {
  return {
    source,
    source_id: id,
    url: `https://example.invalid/${id}`,
    latitude: 53.4,
    longitude: -6.35,
    license: "test",
    retrieved_at: "2026-08-01",
  };
}

const OPEN: OperatorAttribution = { contested: [], is_contested: false, tag: "open" };

function candidate(over: Partial<Candidate> = {}): Candidate {
  return {
    key: "k",
    aoi: "dublin",
    country: "IE",
    latitude: 53.4,
    longitude: -6.35,
    attribution: OPEN,
    basis: "priors_only",
    cooling: "unknown",
    observations: [obs("osm", "way/1")],
    scene_ids: [],
    sources: ["osm"],
    corroboration: "single_source",
    tag: "reference",
    ...over,
  };
}

function register(over: Partial<CandidatesRegister> = {}): CandidatesRegister {
  return {
    scope: "seeded",
    generated_at: "2026-08-01",
    corroboration_radius_m: 250,
    aois: [],
    sources: [],
    candidates: [],
    ...over,
  };
}

describe("splits", () => {
  it("separates corroborated candidates from single-source leads", () => {
    const both = candidate({
      key: "both",
      corroboration: "corroborated",
      sources: ["osm", "peeringdb"],
    });
    const lead = candidate({ key: "lead" });
    const reg = register({ candidates: [both, lead] });
    expect(corroborated(reg).map((c) => c.key)).toEqual(["both"]);
    expect(singleSource(reg).map((c) => c.key)).toEqual(["lead"]);
  });

  it("keeps single-source leads rather than dropping them", () => {
    // The coverage gap between the two registers is itself a finding — a reader must be able
    // to see that Johor has many mapped buildings and few interconnection rows.
    const reg = register({ candidates: [candidate({ key: "lead" })] });
    expect(reg.candidates).toHaveLength(1);
    expect(corroborated(reg)).toHaveLength(0);
  });
});

describe("attributionView", () => {
  it("reports an unattributed candidate as open", () => {
    expect(attributionView(candidate())).toEqual({ kind: "open" });
  });

  it("reports a cited operator", () => {
    const view = attributionView(
      candidate({
        attribution: {
          operator: "Equinix, Inc.",
          citation: "https://www.peeringdb.com/fac/164",
          source: "peeringdb",
          contested: [],
          is_contested: false,
          tag: "reference",
        },
      }),
    );
    expect(view).toMatchObject({ kind: "cited", operator: "Equinix, Inc." });
  });

  it("never flattens a contested attribution to a bare name", () => {
    // The Querétaro case: PeeringDB says Equinix, OSM says Axtel. A renderer must be handed a
    // shape it cannot accidentally print as "the operator is Equinix".
    const view = attributionView(
      candidate({
        attribution: {
          operator: "Equinix, Inc.",
          citation: "https://www.peeringdb.com/fac/8434",
          source: "peeringdb",
          contested: [
            {
              operator: "Axtel",
              citation: "https://www.openstreetmap.org/way/741133950",
              source: "osm",
            },
          ],
          is_contested: true,
          tag: "reference",
        },
      }),
    );
    expect(view.kind).toBe("contested");
    if (view.kind !== "contested") throw new Error("unreachable");
    expect(view.others.map((o) => o.operator)).toEqual(["Axtel"]);
  });

  it("treats a name without a citation as open, not as a claim", () => {
    // Defensive: Python refuses to emit this, but a hand-edited or truncated feed must degrade
    // to [open] rather than surfacing an uncited operator name.
    const view = attributionView(
      candidate({
        attribution: { operator: "Definitely Google", contested: [], is_contested: false, tag: "reference" },
      }),
    );
    expect(view).toEqual({ kind: "open" });
  });
});

describe("contested", () => {
  it("selects only the entries whose sources disagree", () => {
    const disputed = candidate({
      key: "disputed",
      attribution: {
        operator: "A",
        citation: "https://example.invalid/a",
        source: "peeringdb",
        contested: [{ operator: "B", citation: "https://example.invalid/b", source: "osm" }],
        is_contested: true,
        tag: "reference",
      },
    });
    const reg = register({ candidates: [disputed, candidate({ key: "clean" })] });
    expect(contested(reg).map((c) => c.key)).toEqual(["disputed"]);
  });
});

describe("aoiSummaries", () => {
  const reg = register({
    aois: [
      {
        slug: "johor",
        label: "Johor",
        country: "MY",
        bbox: [1.25, 103.3, 1.95, 104.35],
        selection_basis: "operator-dense, active buildout",
        observations_by_source: { peeringdb: 6, osm: 75 },
        candidate_count: 80,
        corroborated_count: 1,
        is_negative: false,
      },
      {
        slug: "empty",
        label: "Nowhere",
        country: "XX",
        bbox: [0, 0, 1, 1],
        selection_basis: "control",
        observations_by_source: { peeringdb: 0, osm: 0 },
        candidate_count: 0,
        corroborated_count: 0,
        is_negative: true,
      },
    ],
  });

  it("derives a bbox centre for flying the map", () => {
    const [johor] = aoiSummaries(reg);
    expect(johor.center.latitude).toBeCloseTo(1.6, 5);
    expect(johor.center.longitude).toBeCloseTo(103.825, 5);
  });

  it("does not divide by zero on an AOI that produced nothing", () => {
    const [, empty] = aoiSummaries(reg);
    expect(empty.corroboratedShare).toBe(0);
    expect(empty.is_negative).toBe(true);
  });

  it("keeps every swept AOI, including the negative one", () => {
    // Negative results are results — omitting the row would read as "never looked".
    expect(aoiSummaries(reg)).toHaveLength(2);
  });
});
