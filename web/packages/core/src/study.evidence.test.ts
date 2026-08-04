import { describe, expect, it } from "vitest";
import { hasFeed, loadFeed, manifestOrNull } from "./bundle";
import { isRoutableDoc } from "./docRouting";
import { slugify, type DocumentCollectionItem, type RecordItem } from "./feeds";
import { facetAvailable } from "./readiness";
import { RECORD_GROUP_LABELS } from "./records";
import { REFERENCE, scopedReference } from "./reference";
import { SITES } from "./sites";
import {
  hasChapterEvidence,
  STUDY_CHAPTERS,
  studyChapterEvidence,
  studyChapterModel,
  type StudyChapterEvidence,
} from "./study";

/**
 * The citation invariant (#1885 acceptance) — over EVERY committed bundle.
 *
 * The finding this closes: all thirteen study chapters rendered zero links into documents,
 * records, or reference datasets, while the hero prose promised every figure is checkable. A
 * chapter that asserts a `[verified]` figure is asserting it was read from a cited source; if
 * the page offers no way to reach that source, the tag is a claim of provenance the page does
 * not provide.
 *
 * The gate reads each chapter's **verdict and model**, never its name. The annex chapter
 * (`missing`) is exempt because it asserts no `[verified]` figure, not because it is called
 * `missing` — and a new chapter that ships a verified figure with nothing behind it fails here
 * whatever it is called.
 */
const bundled = SITES.map((s) => s.slug).filter((slug) => manifestOrNull(slug) !== null);

/** Every link the annex would render for a chapter, as site-relative hrefs. */
function hrefs(evidence: StudyChapterEvidence): string[] {
  return [
    ...evidence.groups.map((g) => g.href),
    ...evidence.sources.map((s) => s.href),
    ...evidence.datasets.map((d) => d.href),
  ];
}

/** Whether a site serves ANY of the three citation targets — the invariant's precondition. */
function citable(slug: string): boolean {
  return (["records", "documents", "reference"] as const).some((f) => facetAvailable(slug, f));
}

describe("study chapter evidence — the registry's declarations", () => {
  it("every declared record group is a real group in the shared vocabulary", () => {
    // A typo'd group id resolves to zero rows on every site and silently vanishes, so it would
    // never show up as a broken link — only as a chapter that quietly stopped citing.
    for (const def of STUDY_CHAPTERS) {
      for (const group of def.recordGroups ?? []) {
        expect(Object.keys(RECORD_GROUP_LABELS), `${def.id}: unknown record group`).toContain(group);
      }
    }
  });

  it("every declared reference dataset is a published one", () => {
    const published = new Set(REFERENCE.map((d) => d.slug));
    for (const def of STUDY_CHAPTERS) {
      for (const dataset of def.datasets ?? []) {
        expect(published, `${def.id}: unknown reference dataset "${dataset}"`).toContain(dataset);
      }
    }
  });
});

describe(`study chapter evidence — every committed bundle (${bundled.length} sites)`, () => {
  it("finds a real cohort to guard", () => {
    expect(bundled.length).toBeGreaterThanOrEqual(3);
    for (const slug of ["lima", "fort-wayne", "urbana"]) expect(bundled).toContain(slug);
  });

  it("every site whose study actually builds publishes a citable surface", () => {
    // `[chapter].astro` emits paths only for SELECTABLE sites, and the invariant below can only
    // hold where at least one of the three citation targets is served at all. Pinning that
    // those two sets line up is what keeps the exemption from ever quietly covering a study a
    // reader can reach: promoting a site with no record and no reference data fails HERE.
    const selectable = SITES.filter((s) => s.selectable && manifestOrNull(s.slug) !== null);
    expect(selectable.length).toBeGreaterThanOrEqual(3);
    expect(selectable.filter((s) => !citable(s.slug)).map((s) => s.slug)).toEqual([]);
  });

  it.each(bundled)("%s — a chapter asserting a [verified] figure resolves at least one link", (slug) => {
    const bare: string[] = [];
    for (const def of STUDY_CHAPTERS) {
      const model = studyChapterModel(def.id, slug);
      // The antecedent is read off the MODEL, so the exemption is by verdict: a chapter with no
      // verified figure (the gap inventory, the method front matter, a peer's `na` watch state)
      // passes because it claims no provenance, not because it was skipped by name.
      if (!model.stats.some((s) => s.evidence === "verified")) continue;
      if (!hasChapterEvidence(studyChapterEvidence(def.id, slug))) bare.push(def.id);
    }
    // The one exemption, measured rather than listed: a registered site whose record domain
    // hasn't activated serves NO record screens, NO document pages, and NO reference pages, so
    // there is no destination in existence for its connector-grounded backdrop figures to
    // reach. Its study doesn't build either (see above). The day it activates, the assertion
    // binds with no edit here.
    if (!citable(slug)) {
      expect(hrefs(studyChapterEvidence("labor", slug)), `${slug} serves no citable page`).toEqual([]);
      return;
    }
    expect(bare, `${slug}: [verified] figures with no resolving evidence link`).toEqual([]);
  });

  it.each(bundled)("%s — every offered link is a page this site actually builds", (slug) => {
    // `cite.ts` is the only thing standing between a citation and a 404, so re-derive the three
    // route sets independently here rather than trusting the resolver that produced them.
    const records: RecordItem[] =
      facetAvailable(slug, "records") && hasFeed("records", slug)
        ? loadFeed<RecordItem[]>("records", slug)
        : [];
    const recordHrefs = new Set(records.map((r) => `/site/records/${r.group}/${slugify(r.rel)}`));
    const groupHrefs = new Set(records.map((r) => `/site/records/${r.group}/`));
    const documents =
      facetAvailable(slug, "documents") && hasFeed("documents", slug)
        ? loadFeed<DocumentCollectionItem[]>("documents", slug).flatMap((c) =>
            c.entries.filter(isRoutableDoc),
          )
        : [];
    const datasetHrefs = new Set(
      (facetAvailable(slug, "reference") ? scopedReference(slug) : []).map(
        (d) => `/site/reference/${d.slug}`,
      ),
    );

    for (const def of STUDY_CHAPTERS) {
      const evidence = studyChapterEvidence(def.id, slug);
      for (const group of evidence.groups) {
        expect(groupHrefs, `${slug}/${def.id}`).toContain(group.href);
        expect(group.count).toBeGreaterThan(0);
      }
      for (const source of evidence.sources) {
        if (source.kind === "record") expect(recordHrefs, `${slug}/${def.id}`).toContain(source.href);
        else
          expect(
            documents.map((d) => d.rel),
            `${slug}/${def.id}`,
          ).toContain(source.key);
      }
      for (const dataset of evidence.datasets) {
        expect(datasetHrefs, `${slug}/${def.id}`).toContain(dataset.href);
      }
    }
  });

  it.each(bundled)("%s — a chapter with no disclosed project offers no record at all", (slug) => {
    // The `na` watch state means nothing is screened here yet. Dressing that chapter in the
    // site's record groups anyway would attach evidence to a finding that doesn't exist.
    for (const def of STUDY_CHAPTERS) {
      if (studyChapterModel(def.id, slug).status !== "na") continue;
      expect(hrefs(studyChapterEvidence(def.id, slug)), `${slug}/${def.id}`).toEqual([]);
    }
  });

  it.each(bundled)("%s — the three bands stay one kind each", (slug) => {
    // However a citation was written — declared on the chapter, derived from a feed, or
    // authored in the note's prose — a dataset lands in `datasets` and a leaf in `sources`.
    for (const def of STUDY_CHAPTERS) {
      const { sources, datasets } = studyChapterEvidence(def.id, slug);
      expect(
        sources.some((s) => s.kind === "reference"),
        `${slug}/${def.id}`,
      ).toBe(false);
      expect(
        datasets.every((d) => d.kind === "reference"),
        `${slug}/${def.id}`,
      ).toBe(true);
      // Deduped across the axes: one destination, one row.
      const keys = [...sources, ...datasets].map((s) => `${s.kind}:${s.key}`);
      expect(new Set(keys).size, `${slug}/${def.id}: duplicate rows`).toBe(keys.length);
    }
  });
});

describe("study chapter evidence — the derived scan is scoped to the chapter's own feeds", () => {
  it("the labor baseline never inherits the air permit's citations", () => {
    // The whole bundle is one directory; scanning it wholesale would look harmless (more
    // links!) and would be a misattribution. Lima is the fixture that can actually show this:
    // its air feeds cite two Ohio EPA permits and its labor feed cites no corpus path at all.
    const air = studyChapterEvidence("air", "lima").sources.map((s) => s.key);
    expect(air).toContain("permits/4132514.epa.yaml");
    expect(studyChapterEvidence("labor", "lima").sources).toEqual([]);
  });

  it("a note's authored citation joins the annex, and only its own chapter's", () => {
    // The air note names the DOE §202(c) order; nothing derives that from a feed, so without
    // the note axis the annex would omit the one source the prose links.
    const withNote = studyChapterEvidence("air", "lima", {
      noteBody: '<Cite document="grid/pjm-202c-2026/doe-order-202-26-33.pdf">Order 202-26-33</Cite>',
    });
    expect(withNote.sources.map((s) => s.key)).toContain("grid/pjm-202c-2026/doe-order-202-26-33.pdf");
    expect(studyChapterEvidence("air", "lima").sources.map((s) => s.key)).not.toContain(
      "grid/pjm-202c-2026/doe-order-202-26-33.pdf",
    );
  });

  it("an authored citation the site cannot resolve is dropped, not rendered bare", () => {
    // The `<Cite>` component fails the build on this; the annex must not paper over it with a
    // row that goes nowhere.
    const evidence = studyChapterEvidence("air", "lima", {
      noteBody: '<Cite record="permits/does-not-exist.epa.yaml">nothing</Cite>',
    });
    expect(evidence.sources.map((s) => s.key)).not.toContain("permits/does-not-exist.epa.yaml");
  });
});
