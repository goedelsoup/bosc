import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { repoPath } from "./bundle";
import {
  instanceNoteId,
  instanceSites,
  REFERENCE,
  referenceForSite,
  referenceProse,
  scopedReference,
} from "./reference";
import { SITES } from "./sites";

// Pinned against the committed fixture pair used across the readiness tests: `sites/lima` (the live
// reference build, which owns the whole catalog) vs `sites/fort-wayne` (a real Maumee-basin peer in
// Indiana). The reference section must scope to the site's OWN datasets (catalog `site_scope`,
// resolved per-site in the bundle) — never leak the reference build's Lima/Allen-County datasets
// verbatim (#1260).

describe("reference dataset scope link", () => {
  it("every published dataset names at least one backing catalog entry", () => {
    // The scope seam: an empty `catalogIds` would silently drop the dataset from every site (it can
    // own no matching entry), so the link is required, not optional.
    for (const d of REFERENCE) expect(d.catalogIds.length).toBeGreaterThan(0);
  });
});

describe("scopedReference", () => {
  it("the reference build keeps its full set (it owns the whole catalog)", () => {
    expect(scopedReference("lima").map((d) => d.slug)).toEqual([
      "echo",
      "allen-gis",
      "lima-gis",
      "rsei",
      "gleif",
      "economics",
      "eia",
      "ohio-waterwells",
      "wbd",
    ]);
  });

  it("a sibling site sees only the datasets it owns — never Lima's `lima-legacy` set", () => {
    const fw = scopedReference("fort-wayne").map((d) => d.slug);
    // Its own / shared datasets surface: the Maumee ECHO inventory (shared basin), its own RSEI +
    // economics baseline (slug-scoped), the GLEIF resolution (basin-shared), and the EIA grid /
    // consumer series every site's backdrop floor is keyed to (#1885).
    expect(fw).toEqual(["echo", "rsei", "gleif", "economics", "eia"]);
    // The reference build's Lima/Allen-County-only datasets (all `lima-legacy`) must NOT leak.
    expect(fw).not.toContain("allen-gis");
    expect(fw).not.toContain("lima-gis");
    expect(fw).not.toContain("wbd");
    // Allen County's well census is `site:lima`, so the groundwater dataset stays home too.
    expect(fw).not.toContain("ohio-waterwells");
  });
});

// --- the prose scope declaration (#1905) -------------------------------------------------
//
// `scopedReference` has resolved the right DATASETS per site since #1260. What leaked was the
// PROSE: one README per dataset, all of it written about Allen County, OH — so Urbana and
// Troy-Piqua served byte-identical, Lima-worded documentation of their own different data, and
// Fort Wayne's `/site/reference/rsei` described an Ohio county under an Indiana watershed point.
// The guards below hold the fix's two halves: every README declares whose words it is, and no
// site's page names a county outside its own scope.

const SELECTABLE = SITES.filter((s) => s.selectable);

/** The prose a site actually reads for a dataset: the README plus its OWN instance note. */
function renderedText(datasetSlug: string, site: string): string {
  const dataset = REFERENCE.find((d) => d.slug === datasetSlug)!;
  const parts = [readFileSync(repoPath("data", "reference", dataset.repo), "utf8")];
  const note = instanceNoteId(datasetSlug, site);
  if (note) {
    const dir = dataset.repo.replace(/README\.md$/, "instances");
    parts.push(readFileSync(repoPath("data", "reference", dir, `${site}.md`), "utf8"));
  }
  return parts.join("\n");
}

describe("the reference prose-scope declaration", () => {
  it("every published README declares a scope and says why", () => {
    // `referenceProse` throws on a missing/malformed declaration rather than defaulting — a
    // silent default is how the bug got in, the un-declared README reading as network-general
    // to the routing layer while being written about one county.
    for (const d of REFERENCE) {
      const { scope, scopeNote } = referenceProse(d.slug);
      expect(scope).toMatch(/^(network|basin:[a-z0-9-]+|site:[a-z0-9-]+)$/);
      expect(scopeNote.length).toBeGreaterThan(0);
    }
  });

  it("every scope note is plain prose — the banner renders it as text, not markdown", () => {
    // `scope_note` is a front-matter string the page prints directly, so a backtick or a link
    // would render as literal punctuation in the banner. The technical spelling belongs in the
    // body below it, which IS markdown.
    for (const d of REFERENCE) {
      const { scopeNote } = referenceProse(d.slug);
      expect(scopeNote, `${d.repo} scope_note`).not.toMatch(/[`*_[\]]/);
    }
  });

  it("a `site:`-scoped README only ever renders on the site it names", () => {
    for (const site of SELECTABLE) {
      for (const d of scopedReference(site.slug)) {
        const { scope } = referenceProse(d.slug);
        if (scope.startsWith("site:")) expect(scope.slice("site:".length)).toBe(site.slug);
      }
    }
  });

  it("a `basin:`-scoped README only ever renders on a site in that basin", () => {
    for (const site of SELECTABLE) {
      for (const d of scopedReference(site.slug)) {
        const { scope } = referenceProse(d.slug);
        // `basin:` names the connector's pull basin (`echo`'s Maumee fileset), which the site's
        // registry `basin`/`basinMajor` label spells differently — assert the site is genuinely
        // in it by the catalog owner rule the bundle already applied, i.e. that it owns the entry.
        if (scope.startsWith("basin:")) {
          const basin = scope.slice("basin:".length);
          expect(`${site.basin} ${site.basinMajor}`.toLowerCase()).toContain(basin);
        }
      }
    }
  });

  it("each instance note's `site:` front matter agrees with its filename", () => {
    // The runtime resolves a note by its PATH-derived id, so nothing reads `site:` — which is
    // exactly why it is declared and checked here (the same guard the study collection's
    // `chapter:` gets). A misnamed file would otherwise become silently dead content: no error,
    // no page, and a site quietly missing the findings someone wrote for it.
    for (const d of REFERENCE) {
      for (const site of instanceSites(d.slug)) {
        const dir = d.repo.replace(/README\.md$/, "instances");
        const text = readFileSync(repoPath("data", "reference", dir, `${site}.md`), "utf8");
        expect(text, `${d.slug}/instances/${site}.md`).toMatch(
          new RegExp(`^---\\n(?:.*\\n)*?site: ${site}\\n`),
        );
      }
    }
  });

  it("an instance note exists only for a site that owns the dataset", () => {
    // A note is a site's OWN findings; one filed under a site that doesn't own the dataset would
    // be unreachable content, and worse, a claim about data that site doesn't hold.
    for (const d of REFERENCE) {
      for (const site of instanceSites(d.slug)) {
        expect(
          scopedReference(site).map((x) => x.slug),
          `${d.slug}/instances/${site}.md exists but ${site} does not own ${d.slug}`,
        ).toContain(d.slug);
      }
    }
  });
});

describe("no reference page names a county outside the reading site's scope", () => {
  // The acceptance criterion of #1905, made mechanical. Every registry county reads as it would
  // in a citation ("Allen County, OH"), which is exactly the string that must not appear on
  // another site's page — and it disambiguates Lima's Allen County, OH from Fort Wayne's
  // Allen County, IN, the pair that made the leak hard to see.
  const COUNTIES = [...new Set(SITES.map((s) => s.county).filter((c): c is string => !!c))];

  it("holds for every selectable site × every dataset it renders", () => {
    expect(COUNTIES.length).toBeGreaterThan(1);
    const leaks: string[] = [];
    for (const site of SELECTABLE) {
      for (const d of scopedReference(site.slug)) {
        const text = renderedText(d.slug, site.slug);
        for (const county of COUNTIES) {
          if (county !== site.county && text.includes(county)) {
            leaks.push(`/site/reference/${d.slug} on ${site.slug} names ${county}`);
          }
        }
      }
    }
    expect(leaks).toEqual([]);
  });

  it("catches the reported bug — the guard fails against the pre-fix, un-split RSEI prose", () => {
    // The README as it read before the split: the lede named Allen County, OH outright, so every
    // peer's page did too. Re-run the same check over that text to prove this test is standing
    // guard over the actual regression, not a property that happens to hold today.
    const preFix = "Per-facility RSEI results for **Allen County, OH (FIPS 39003)**.";
    const peers = SELECTABLE.filter((s) => s.county !== "Allen County, OH");
    expect(peers.length).toBeGreaterThan(0);
    for (const peer of peers) {
      const leaked = COUNTIES.filter((c) => c !== peer.county && preFix.includes(c));
      expect(leaked).toEqual(["Allen County, OH"]);
    }
  });
});

describe("referenceForSite", () => {
  it("resolves each site's OWN files — the reference build keeps the un-slugged peer", () => {
    const rsei = (slug: string) =>
      referenceForSite(slug)
        .find((e) => e.dataset.slug === "rsei")!
        .instances.flatMap((i) => i.files);
    // Lima is the reference build: `lima-legacy` storage means its copy is the un-slugged path.
    expect(rsei("lima")).toContain("reference/rsei/inventory.yaml");
    // Every peer reads its own slug-scoped copy — and this is what finally makes two peers
    // owning the same dataset serve distinguishable content.
    expect(rsei("urbana")).toContain("reference/rsei/urbana/inventory.yaml");
    expect(rsei("troy-piqua")).toContain("reference/rsei/troy-piqua/inventory.yaml");
    expect(rsei("urbana")).not.toContain("reference/rsei/inventory.yaml");
  });

  it("names no file the site does not actually hold", () => {
    // `reference/rsei/{site}/enclave.yaml` is templated for every site but committed only where
    // the facility is a federal installation (#1664). Naming it anyway would be the same
    // borrowed context this seam exists to stop, one level down.
    for (const slug of ["urbana", "troy-piqua", "fort-wayne"]) {
      const files = referenceForSite(slug).flatMap((e) => e.instances.flatMap((i) => i.files));
      expect(files).not.toContain(`reference/rsei/${slug}/enclave.yaml`);
    }
  });

  it("attaches Lima's instance notes to Lima and to no one else", () => {
    const noteFor = (slug: string, dataset: string) =>
      referenceForSite(slug).find((e) => e.dataset.slug === dataset)?.note ?? null;
    for (const dataset of ["rsei", "gleif", "eia"]) {
      expect(noteFor("lima", dataset)).toBe(`${dataset}/lima`);
      for (const peer of ["fort-wayne", "urbana", "troy-piqua"]) {
        expect(noteFor(peer, dataset)).toBeNull();
      }
    }
  });
});
