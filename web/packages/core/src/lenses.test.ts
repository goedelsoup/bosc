// The Lens model (#1913, epic #1911 phase 1).
//
// `lenses.ts` is PURE — no bundle read — so everything here runs offline with no `web/sites/`
// present. The bundle-backed half (`lensStatus`) is tested against committed fixtures in
// `readiness.test.ts`, where the bundle loader already lives.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { type Lens, LENS_ORDER, LENSES, type LensId } from "./lenses";
import { RECORD_FACETS, SECTION_META } from "./readiness";

const SOURCE = join(process.cwd(), "packages/core/src/lenses.ts");

const lenses = (): Lens[] => LENS_ORDER.map((id) => LENSES[id]);

describe("the five lenses", () => {
  it("reads in the buildout's causal chain — land, power, environment, economy, disclosure", () => {
    // Not an alphabet and not a ranking: the ground is taken first and the decision that
    // authorized it surfaces last. A reorder here is a change to the argument, not to a list.
    expect(LENS_ORDER).toEqual(["land", "power", "environment", "economy", "disclosure"]);
  });

  it("declares every ordered lens exactly once, and nothing else", () => {
    expect(Object.keys(LENSES).sort()).toEqual([...LENS_ORDER].sort());
    for (const id of LENS_ORDER) expect(LENSES[id].id).toBe(id);
  });

  it("numbers them 01…05 in reading order", () => {
    expect(lenses().map((l) => l.number)).toEqual(["01", "02", "03", "04", "05"]);
  });

  it("asks a question and never states a claim", () => {
    // The load-bearing discipline of the epic: a lens is a standing view, so its headline is
    // interrogative. The moment one asserts, it has become a hypothesis and owes provenance.
    for (const l of lenses()) {
      expect(l.name.length, l.id).toBeGreaterThan(0);
      expect(l.question.endsWith("?"), `${l.id}: "${l.question}"`).toBe(true);
      expect(l.blurb.length, l.id).toBeGreaterThan(40);
    }
  });

  it("carries no evidentiary weight — no signal, tag, citation, or cell store", () => {
    // The tripwire, asserted rather than left to the docstring: a lens that grows any of these
    // fields has become a hypothesis and belongs in `data/hypotheses/`.
    for (const l of lenses()) {
      for (const forbidden of ["signal", "tag", "citation", "cell", "verdict", "confidence"]) {
        expect(Object.hasOwn(l, forbidden), `${l.id} grew a "${forbidden}" field`).toBe(false);
      }
    }
  });

  it("rests each reading on named feeds", () => {
    for (const l of lenses()) expect(l.feeds.length, l.id).toBeGreaterThan(0);
  });
});

describe("the ids reuse the existing vocabulary", () => {
  it("names the two promoted sections exactly as `readiness.ts` already names them", () => {
    // #1912 took "lens" back from the hypotheses precisely so a second name for one thing could
    // not creep in. Coining "Water & air" / "Money" here would repeat that mistake.
    const sections = Object.keys(SECTION_META);
    expect(sections).toContain("environment");
    expect(sections).toContain("economy");
    expect(LENSES.environment.id).toBe("environment");
    expect(LENSES.economy.id).toBe("economy");
  });
});

describe("the gating declaration", () => {
  // The table from #1913, asserted here so the composition in `readiness.ts` has a spec to
  // disagree with. `land`/`disclosure` are pure domain reads; `environment`/`economy` inherit
  // their same-named section verbatim; `power` is the one split that takes both.
  const expected: Record<LensId, { sections: string[]; domains: string[] }> = {
    land: { sections: [], domains: ["places"] },
    power: { sections: ["economy"], domains: ["facility"] },
    environment: { sections: ["environment"], domains: [] },
    economy: { sections: ["economy"], domains: [] },
    disclosure: { sections: [], domains: ["record"] },
  };

  it("gates each lens on the sections and domains #1913 specifies", () => {
    for (const id of LENS_ORDER) {
      expect({ sections: [...LENSES[id].sections], domains: [...LENSES[id].domains] }, id).toEqual(
        expected[id],
      );
    }
  });

  it("stands on at least one gate — no lens opens unconditionally", () => {
    for (const l of lenses()) {
      expect(l.sections.length + l.domains.length, l.id).toBeGreaterThan(0);
    }
  });
});

describe("the facets a lens gathers", () => {
  const allFacets = lenses().flatMap((l) => l.facets.map((f) => ({ lens: l.id, ...f })));

  it("gathers only site-relative leaf routes — a view over them, not a new store", () => {
    for (const f of allFacets) {
      expect(f.route.startsWith("/"), `${f.lens}: ${f.route}`).toBe(true);
      // No site prefix and no deploy base baked in: the caller applies `siteBase(slug)`.
      expect(f.route.startsWith("/network/"), `${f.lens}: ${f.route}`).toBe(false);
      expect(f.label.length, f.route).toBeGreaterThan(0);
      expect(f.blurb.length, f.route).toBeGreaterThan(0);
    }
  });

  it("never routes two lenses at the same destination", () => {
    // Page boundaries and lens boundaries don't align, so a shared page is reached through an
    // ANCHOR (`/economy/economics-baseline#consumer-energy` for Power) — the lens reaches only the
    // band it is a view over. Two lenses claiming the same href would be a real ambiguity.
    const routes = allFacets.map((f) => f.route);
    expect(new Set(routes).size).toBe(routes.length);
  });

  it("agrees with `RECORD_FACETS` on every route that IS a declared record facet", () => {
    // The drift guard for the one place two modules write the same URL down. (The dependency runs
    // one way at runtime — `readiness.ts` imports the lenses, never the reverse — so the routes
    // are re-typed here on purpose and pinned there.)
    const bound = allFacets.filter((f) => f.facet !== undefined);
    expect(bound.length).toBeGreaterThan(0);
    for (const f of bound) {
      expect(RECORD_FACETS[f.facet!].route, `${f.lens} · ${f.label}`).toBe(f.route);
    }
  });

  it("leaves the long-form reports at Reports (#1893)", () => {
    // #1893 pulled `/reports/*` out of the Reference dropdown because a destination linked from
    // everywhere is emphasized nowhere. The lens layer must not quietly put them back.
    for (const f of allFacets) expect(f.route.startsWith("/reports"), f.route).toBe(false);
  });
});

describe("presentation", () => {
  it("marks each lens with its own position on the forest data ramp", () => {
    expect(lenses().map((l) => l.accent.token)).toEqual([
      "--data-1",
      "--data-2",
      "--data-3",
      "--data-4",
      "--data-5",
    ]);
    expect(new Set(lenses().map((l) => l.accent.mark)).size).toBe(LENS_ORDER.length);
    for (const l of lenses()) expect(l.accent.mark, l.id).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("spends no evidence-palette fill on a lens", () => {
    // "The evidence palette encodes evidence only." The `--ev-*` chip fills and borders say how
    // well a figure is sourced; a lens has no evidentiary weight of its own to declare, so it
    // takes a data-ramp mark and the ordinary bone surface. (`--data-1` and `--ev-verified-fg`
    // share a hex — forest is one hue — but it is the FILL that makes a chip read as evidence.)
    const evidenceFills = new Set([
      "#e4ece4",
      "#bcd2c4", // verified bg / border
      "#efe6d0",
      "#dcc98a", // inference bg / border
      "#e8e4d8",
      "#cdc8b8", // open bg / border
      "#f3e6e2",
      "#d8b8b2", // scope-gap bg / border
      "#f3e7c4", // key-figure bg
    ]);
    for (const l of lenses()) {
      // The accent is a MARK, not a fill — the model deliberately carries no background field.
      expect(Object.keys(l.accent).sort()).toEqual(["mark", "token"]);
      if (l.id !== "disclosure") {
        expect(evidenceFills.has(l.accent.mark), `${l.id} took an evidence fill`).toBe(false);
      }
    }
    // `--data-5` (the ramp's quietest tint) and `--ev-verified-border` are the same hex, which is
    // the token system's, not a choice made here: the ramp bottoms out where the hairline lives.
    expect(LENSES.disclosure.accent.token).toBe("--data-5");
  });
});

describe("purity (#1913 acceptance)", () => {
  it("reads no bundle — its only sibling imports are erased type imports", () => {
    // Asserted against the source rather than by observing behavior, because the failure mode is
    // a future edit reaching for `loadFeed`/`loadManifest` to enrich a lens — which would both
    // break offline unit-testing AND be the first step toward an evidence store living here.
    const source = readFileSync(SOURCE, "utf-8");
    // Tolerates a wrapped multi-line import — biome breaks long ones, and a value import that
    // slipped in below the fold is exactly the edit this guards against.
    const imports = [...source.matchAll(/^import\s+(type\s+)?[\s\S]*?\s+from\s+"([^"]+)";$/gm)];
    expect(imports.length).toBeGreaterThan(0);
    for (const [line, typeOnly] of imports) {
      expect(typeOnly?.trim(), `not a type-only import: ${line}`).toBe("type");
    }
    expect(source).not.toMatch(/\bloadFeed\b|\bloadManifest\b|\bhasFeed\b/);
  });
});
