// The network-tier lens scorecard (#1914, epic #1911 phase 2).
//
// `lensView.ts` is pure, so this runs offline against a stub registry and stub resolvers — the same
// discipline `directory.test.ts` holds. What it pins is the half that would be easy to get quietly
// wrong: that the three site states stay three (a lens must never claim an export ran that didn't),
// that a real 0 survives as a measurement, and that nothing in the view can express a verdict.
import { describe, expect, it } from "vitest";
import { LENSES, LENS_ORDER } from "./lenses";
import {
  buildLensView,
  LENS_METRICS,
  lensCount,
  lensFootNote,
  lensNetworkCounts,
  type LensResolvers,
  lensSiteState,
} from "./lensView";
import { TAIL_META } from "./scorecard";
import type { NetworkSite } from "./sites";
import { SITES } from "./sites";

// Four sites, one per state the renderer must distinguish, in registry order.
const site = (slug: string, status: NetworkSite["status"] = "tracking"): NetworkSite =>
  ({
    ...SITES[0],
    slug,
    place: `${slug} place`,
    basin: "Basin",
    href: `/network/${slug}`,
    status,
  }) as NetworkSite;

const FIXTURE: NetworkSite[] = [
  site("ref", "live"), // reference tier, everything on the record
  site("worked"), //     case tier, on the record, real zeros on some feeds
  site("thin"), //       has a bundle, but this lens is locked → "not on the record here"
  site("unbuilt"), //    registered, never exported → "no bundle committed yet"
];

const TIERS: Record<string, "reference" | "case" | "backdrop" | "stub" | null> = {
  ref: "reference",
  worked: "case",
  thin: "backdrop",
  unbuilt: null,
};

/** Every feed at 3 rows on `ref`, 0 on `worked` — the measured-zero case — absent elsewhere. */
const COUNTS: Record<string, Record<string, number>> = {
  ref: Object.fromEntries(
    LENS_ORDER.flatMap((id) => LENS_METRICS[id].flatMap((m) => m.feeds.map((f) => [f, 3]))),
  ),
  worked: {},
  thin: {},
};

const resolvers = (open: readonly string[] = ["ref", "worked"]): LensResolvers => ({
  tierOf: (slug) => TIERS[slug] ?? null,
  statusOf: (slug) => (open.includes(slug) ? "available" : "locked"),
  countOf: (slug, feed) => (TIERS[slug] === null ? null : (COUNTS[slug]?.[feed] ?? 0)),
});

describe("a lens column may only measure the record", () => {
  it("draws every column from a feed the lens itself declares", () => {
    // The rule that keeps the network table honest: a column may not reach for data the lens does
    // not say it reads. Without this, a metric could quietly widen a lens past its own model.
    for (const id of LENS_ORDER) {
      const declared = new Set(LENSES[id].feeds);
      for (const m of LENS_METRICS[id]) {
        expect(m.feeds.length, `${id} · ${m.label}`).toBeGreaterThan(0);
        for (const f of m.feeds) {
          expect(declared.has(f), `${id} · ${m.label} reads undeclared feed "${f}"`).toBe(true);
        }
        expect(m.gloss.length, `${id} · ${m.label}`).toBeGreaterThan(0);
      }
    }
  });

  it("gives every lens at least one column and a footer that says what each counts", () => {
    for (const id of LENS_ORDER) {
      expect(LENS_METRICS[id].length, id).toBeGreaterThan(0);
      const note = lensFootNote(id);
      for (const m of LENS_METRICS[id]) expect(note).toContain(m.gloss);
      // The standing dash-vs-zero rule travels with the table, not with one page's prose.
      expect(note).toContain("A dash means no bundle is committed yet");
      expect(note).toContain("reaches no verdict");
    }
  });
});

describe("the three site states stay three", () => {
  it("separates on-the-record, not-on-the-record, and never-measured", () => {
    const r = resolvers();
    expect(lensSiteState("ref", r)).toBe("on-record");
    expect(lensSiteState("worked", r)).toBe("on-record");
    expect(lensSiteState("thin", r)).toBe("unrecorded");
    expect(lensSiteState("unbuilt", r)).toBe("unmeasured");
    expect(lensNetworkCounts(FIXTURE, r)).toEqual({ "on-record": 2, unrecorded: 1, unmeasured: 1 });
  });

  it("never asks a bundle-less site for a lens status", () => {
    // `lensStatus` reads the manifest and throws where none is committed, so the ORDER of the two
    // probes is load-bearing, not stylistic: tier first, status only after.
    const r: LensResolvers = {
      tierOf: () => null,
      statusOf: () => {
        throw new Error("statusOf must not be reached for an unexported site");
      },
      countOf: () => null,
    };
    expect(() => buildLensView("land", FIXTURE, r)).not.toThrow();
    expect(buildLensView("land", FIXTURE, r).groups.every((g) => g.kind === "chips")).toBe(true);
  });

  it("tails them with the claims the primitive declares, in that order", () => {
    const view = buildLensView("land", FIXTURE, resolvers());
    const tails = view.groups.filter((g) => g.kind === "chips");
    expect(tails.map((g) => g.claim)).toEqual(["unrecorded", "unmeasured"]);
    // A lens may never make the hypothesis claim — that is the whole distinction this epic draws.
    expect(tails.map((g) => g.claim)).not.toContain("unassessed");
    expect(tails[0].label).toBe(TAIL_META.unrecorded.label);
    expect(tails[1].label).toBe(TAIL_META.unmeasured.label);
    // Every tail site still routes to its own page (#1862) — nothing is stranded.
    for (const t of tails) for (const c of t.chips) expect(c.href.startsWith("/network/")).toBe(true);
  });

  it("accounts for every registered site exactly once", () => {
    for (const id of LENS_ORDER) {
      const view = buildLensView(id, FIXTURE, resolvers());
      const placed = view.groups.flatMap((g) => [
        ...g.rows.map((r) => r.slug),
        ...g.chips.map((c) => c.place),
      ]);
      expect(placed, id).toHaveLength(FIXTURE.length);
    }
  });
});

describe("measured zero vs unmeasured dash", () => {
  it("renders a real 0 as a measurement and only a missing bundle as a dash", () => {
    const view = buildLensView("disclosure", FIXTURE, resolvers());
    const rows = view.groups.flatMap((g) => g.rows);
    const cells = (slug: string) => rows.find((r) => r.slug === slug)?.cells.slice(3) ?? [];
    // `ref` committed 3 rows on each declared feed.
    expect(cells("ref").map((c) => c.text)).toEqual(["3", "3", "3"]);
    // `worked` exported and carries none — 0, un-muted. A dash here would understate the network.
    expect(cells("worked").map((c) => c.text)).toEqual(["0", "0", "0"]);
    expect(cells("worked").every((c) => c.muted)).toBe(false);
    // `unbuilt` never exported, so it is in the tail — it gets no row to fabricate a zero into.
    expect(rows.some((r) => r.slug === "unbuilt")).toBe(false);
  });

  it("reports a presence column as plain text, never a pill", () => {
    // A pill in the evidence grammar's shape would read as a tag; a lens declares no weight (#1913).
    const view = buildLensView("power", FIXTURE, resolvers());
    const rows = view.groups.flatMap((g) => g.rows);
    const metrics = (slug: string) => rows.find((r) => r.slug === slug)?.cells.slice(3) ?? [];
    expect(metrics("ref").map((c) => c.kind)).toEqual(["text", "text"]);
    expect(metrics("ref").map((c) => c.text)).toEqual(["on file", "on file"]);
    expect(metrics("worked").map((c) => c.text)).toEqual(["—", "—"]);
    for (const c of [...metrics("ref"), ...metrics("worked")]) expect(c.pill).toBeUndefined();
  });
});

describe("the rendered view", () => {
  it("groups the rows by readiness tier, deepest first", () => {
    const view = buildLensView("land", FIXTURE, resolvers());
    const rowGroups = view.groups.filter((g) => g.kind === "rows");
    expect(rowGroups.map((g) => g.abbr)).toEqual(["REF", "CAS"]);
    expect(rowGroups.flatMap((g) => g.rows.map((r) => r.slug))).toEqual(["ref", "worked"]);
  });

  it("keeps one grid width per column", () => {
    for (const id of LENS_ORDER) {
      const view = buildLensView(id, FIXTURE, resolvers());
      expect(view.gridCols.split(" "), id).toHaveLength(view.cols.length);
      // Site, watershed point, build phase, then the metrics.
      expect(view.cols.length, id).toBe(3 + LENS_METRICS[id].length);
    }
  });

  it("carries no signal, tag, or verdict anywhere in the view", () => {
    // The structural version of "no lens page shows a verdict": the only pill a lens row can hold
    // is the build PHASE (our progress on the website), whose four labels are fixed and none of
    // which is a reading of the site.
    const phases = ["Live", "Building", "Queued", "Tracking"];
    for (const id of LENS_ORDER) {
      const view = buildLensView(id, FIXTURE, resolvers());
      for (const cell of view.groups.flatMap((g) => g.rows).flatMap((r) => r.cells)) {
        if (cell.pill) expect(phases, `${id}: ${cell.pill.label}`).toContain(cell.pill.label);
      }
    }
  });

  it("counts the network in the card line without ever ranking a site", () => {
    expect(lensCount(FIXTURE, resolvers())).toBe("2 on the record · 2 to assemble");
  });
});
