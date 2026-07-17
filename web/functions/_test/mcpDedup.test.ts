// Duplicate-cluster collapse kernel tests (#1590). Pure — no fetch/harness needed.
// Exercises dedupeByCluster over a synthetic OEPA-permit triad (final/draft/fact-sheet) plus an
// unclustered hit, across every deduplicate × version_policy combination.

import { describe, expect, it } from "vitest";
import type { VersionInfo } from "@watermark/functions/api/_lib/docVersionsLoad";
import {
  type DedupAccess,
  DEFAULT_DEDUPLICATE,
  DEFAULT_VERSION_POLICY,
  dedupeByCluster,
  parseDeduplicate,
  parseVersionPolicy,
} from "@watermark/functions/api/_lib/mcpDedup";

interface Item {
  rel: string | null;
  text: string;
}

const PERMIT = "oepa/permit.pdf";
const DRAFT = "oepa/draft.pdf";
const FACT = "oepa/fact-sheet.pdf";

// The final permit has the count but NOT the engine "rating"; the draft carries the un-redacted
// rating; the fact sheet is prose that shares no novel query term with the canonical.
const POOL: Item[] = [
  { rel: PERMIT, text: "generator count 115 final permit" },
  { rel: DRAFT, text: "generator rating 313 mw unredacted draft" },
  { rel: FACT, text: "generator summary fact sheet" },
  { rel: "aedg/other.pdf", text: "unrelated roundabout estimate" }, // unclustered → always kept
];

function versionMap(opts?: {
  canonicalPresent?: boolean;
  duplicateOnly?: boolean;
}): Map<string, VersionInfo> {
  const { canonicalPresent = true, duplicateOnly = false } = opts ?? {};
  const canonical = canonicalPresent ? PERMIT : DRAFT;
  const mk = (version: string, rel: string): VersionInfo => ({
    cluster: "oepa:x",
    canonical,
    version,
    isCanonical: rel === canonical,
  });
  const m = new Map<string, VersionInfo>();
  if (canonicalPresent) m.set(PERMIT, mk(duplicateOnly ? "duplicate" : "final", PERMIT));
  m.set(DRAFT, mk(duplicateOnly ? "duplicate" : "draft", DRAFT));
  m.set(FACT, mk(duplicateOnly ? "duplicate" : "fact_sheet", FACT));
  return m;
}

const access: DedupAccess<Item> = { relOf: (i) => i.rel, textOf: (i) => i.text };
const rels = (items: Item[]): (string | null)[] => items.map((i) => i.rel);

describe("dedupeByCluster", () => {
  it("deduplicate:none returns the pool unchanged", () => {
    const out = dedupeByCluster(POOL, {
      deduplicate: "none",
      versionPolicy: "latest_with_relevant_older_evidence",
      query: "generator rating",
      versions: versionMap(),
      access,
    });
    expect(out).toEqual(POOL);
  });

  it("version_policy:all keeps every version (no collapse)", () => {
    const out = dedupeByCluster(POOL, {
      deduplicate: "canonical",
      versionPolicy: "all",
      query: "generator rating",
      versions: versionMap(),
      access,
    });
    expect(rels(out)).toEqual(rels(POOL));
  });

  it("latest_only keeps only the canonical member (+ unclustered)", () => {
    const out = dedupeByCluster(POOL, {
      deduplicate: "canonical",
      versionPolicy: "latest_only",
      query: "generator rating",
      versions: versionMap(),
      access,
    });
    expect(rels(out)).toEqual([PERMIT, "aedg/other.pdf"]);
  });

  it("latest_with_relevant_older_evidence retains a draft that adds a query term the final lacks", () => {
    const out = dedupeByCluster(POOL, {
      deduplicate: "canonical",
      versionPolicy: "latest_with_relevant_older_evidence",
      query: "generator rating",
      versions: versionMap(),
      access,
    });
    // permit kept (canonical); draft kept (carries "rating"); fact-sheet dropped (no novel term).
    expect(rels(out)).toEqual([PERMIT, DRAFT, "aedg/other.pdf"]);
  });

  it("drops an older version that shares no novel query term with the canonical", () => {
    // Query only mentions "generator", which the canonical already has → draft adds nothing.
    const out = dedupeByCluster(POOL, {
      deduplicate: "canonical",
      versionPolicy: "latest_with_relevant_older_evidence",
      query: "generator",
      versions: versionMap(),
      access,
    });
    expect(rels(out)).toEqual([PERMIT, "aedg/other.pdf"]);
  });

  it("never zeroes a cluster: with no canonical present, the best-ranked member represents it", () => {
    const noCanonical = POOL.filter((i) => i.rel !== PERMIT);
    const out = dedupeByCluster(noCanonical, {
      deduplicate: "canonical",
      versionPolicy: "latest_only",
      query: "generator rating",
      versions: versionMap({ canonicalPresent: false }),
      access,
    });
    // draft is the best-ranked present member → becomes the representative; fact-sheet drops.
    expect(rels(out)).toEqual([DRAFT, "aedg/other.pdf"]);
  });

  it("collapsibleVersions restricts collapse to byte-identical duplicates (passages mode)", () => {
    // Non-duplicate variant labels → nothing is collapse-eligible, so every member survives.
    const out = dedupeByCluster(POOL, {
      deduplicate: "canonical",
      versionPolicy: "latest_only",
      query: "generator rating",
      versions: versionMap(),
      access,
      collapsibleVersions: new Set(["duplicate"]),
    });
    expect(rels(out)).toEqual(rels(POOL));
  });

  it("collapses byte-identical duplicates to the canonical under passages mode", () => {
    const out = dedupeByCluster(POOL, {
      deduplicate: "canonical",
      versionPolicy: "latest_only",
      query: "generator rating",
      versions: versionMap({ duplicateOnly: true }),
      access,
      collapsibleVersions: new Set(["duplicate"]),
    });
    expect(rels(out)).toEqual([PERMIT, "aedg/other.pdf"]);
  });

  it("an empty version map is a no-op", () => {
    const out = dedupeByCluster(POOL, {
      deduplicate: "canonical",
      versionPolicy: "latest_only",
      query: "generator",
      versions: new Map(),
      access,
    });
    expect(out).toEqual(POOL);
  });

  it("passes through hits with no rel or an unmapped rel", () => {
    const pool: Item[] = [
      { rel: null, text: "no source" },
      { rel: "oepa/unmapped.pdf", text: "not in the map" },
    ];
    const out = dedupeByCluster(pool, {
      deduplicate: "canonical",
      versionPolicy: "latest_only",
      query: "source",
      versions: versionMap(),
      access,
    });
    expect(out).toEqual(pool);
  });
});

describe("arg parsing", () => {
  it("defaults deduplicate to canonical and version_policy to latest_with_relevant_older_evidence", () => {
    expect(parseDeduplicate(undefined)).toBe(DEFAULT_DEDUPLICATE);
    expect(parseDeduplicate("bogus")).toBe("canonical");
    expect(parseVersionPolicy(undefined)).toBe(DEFAULT_VERSION_POLICY);
    expect(parseVersionPolicy("bogus")).toBe("latest_with_relevant_older_evidence");
  });

  it("honors explicit values", () => {
    expect(parseDeduplicate("none")).toBe("none");
    expect(parseVersionPolicy("latest_only")).toBe("latest_only");
    expect(parseVersionPolicy("all")).toBe("all");
  });
});
