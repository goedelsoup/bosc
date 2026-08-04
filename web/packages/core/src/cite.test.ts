import { describe, expect, it } from "vitest";
import {
  citeCorpusPath,
  citeDataset,
  citeDocument,
  citeGroups,
  citeRecord,
  citedSourcesIn,
  corpusPathsIn,
} from "./cite";
import { slugify } from "./feeds";

/**
 * The citation resolver (#1885). Pinned against the committed fixture pair the readiness tests
 * already use: `sites/lima` (the reference build, every facet open) and `sites/fort-wayne` (a
 * real Maumee-basin peer in Indiana with a much thinner record).
 *
 * The load-bearing property is the NEGATIVE one. A resolver that returns a plausible-looking
 * href for a source the site doesn't hold reintroduces exactly the defect this module exists to
 * fix — a `[verified]` tag over a link into a 404 — so most of what's asserted here is that
 * unresolvable inputs come back `null` rather than "close enough".
 */

const LIMA_PERMIT = "permits/4132514.epa.yaml";
const LIMA_DOC = "oepa/2DP00130.pdf";

describe("citeRecord", () => {
  it("resolves a rel on the site's own record to its record screen", () => {
    const cited = citeRecord(LIMA_PERMIT, "lima");
    expect(cited).not.toBeNull();
    expect(cited?.kind).toBe("record");
    expect(cited?.key).toBe(LIMA_PERMIT);
    // The SAME address the record screen mints (`[group]/[id].astro` keys on `slugify(rel)`) —
    // a second spelling of the id here would 404 silently.
    expect(cited?.href).toBe(`/site/records/permits-epa/${slugify(LIMA_PERMIT)}`);
    expect(cited?.label.length).toBeGreaterThan(0);
    expect(cited?.detail).toBe("Permits");
  });

  it("returns null for a rel this site does not hold — never a guessed href", () => {
    // Lima's own permit, resolved against a peer that has no such record.
    expect(citeRecord(LIMA_PERMIT, "fort-wayne")).toBeNull();
    expect(citeRecord("permits/does-not-exist.epa.yaml", "lima")).toBeNull();
  });

  it("matches the rel verbatim — no case folding, no path normalization", () => {
    // The rel is the chain-of-custody path; a fuzzy match here would let a citation drift onto
    // a different record than the one the prose names.
    expect(citeRecord(LIMA_PERMIT.toUpperCase(), "lima")).toBeNull();
    expect(citeRecord(`/${LIMA_PERMIT}`, "lima")).toBeNull();
  });
});

describe("citeDocument", () => {
  it("resolves a catalogued document to its stable-handle permalink", () => {
    const cited = citeDocument(LIMA_DOC, "lima");
    expect(cited).not.toBeNull();
    expect(cited?.kind).toBe("document");
    expect(cited?.href).toMatch(/^\/doc\/[0-9a-z]{8}\/$/);
    expect(cited?.label).toBe("2DP00130.pdf");
  });

  it("resolves a document whose bytes are gated — the production record is still public", () => {
    // 3,215 of Lima's 3,247 files are behind the publish allowlist. A gated file still has a
    // page, and citing it is how a reader learns the record exists at all.
    const cited = citeDocument("aedg/PRR-01-bundle.ocr.pdf", "lima");
    expect(cited).not.toBeNull();
  });

  it("returns null for a catalogued file the route filter excludes", () => {
    // `Thumbs.db` is listed in its container's manifest and fetchable, but mints no page
    // (`isRoutableDoc`), so there is nothing for a citation to point at.
    const thumbs = citeDocument(
      "legal/prr-mandamus/prr-production-2026-07-24-sanitary/9/SH & AB SSO Findings and Orders/Phase 1 SECAP Constr Projects/Informational Meeting 3-26-13/Thumbs.db",
      "lima",
    );
    expect(thumbs).toBeNull();
  });

  it("returns null for a rel this site does not hold", () => {
    expect(citeDocument(LIMA_DOC, "fort-wayne")).toBeNull();
  });
});

describe("citeDataset", () => {
  it("resolves a dataset the site owns", () => {
    const cited = citeDataset("eia", "lima");
    expect(cited?.kind).toBe("reference");
    expect(cited?.href).toBe("/site/reference/eia");
    expect(cited?.evidence).toBe("reference");
  });

  it("returns null for a dataset the site does not own", () => {
    // `ohio-waterwells` is Allen County's census (`site:lima`); an Indiana peer owns no part of
    // it, and the reference route emits no page for it there.
    expect(citeDataset("ohio-waterwells", "fort-wayne")).toBeNull();
    expect(citeDataset("not-a-dataset", "lima")).toBeNull();
  });
});

describe("citeCorpusPath", () => {
  it("dispatches on the corpus root", () => {
    expect(citeCorpusPath(`data/extracted/${LIMA_PERMIT}`, "lima")?.kind).toBe("record");
    expect(citeCorpusPath(`data/documents/${LIMA_DOC}`, "lima")?.kind).toBe("document");
    expect(citeCorpusPath("data/reference/rsei/inventory.yaml", "lima")?.key).toBe("rsei");
    expect(citeCorpusPath("src/lib/whatever.ts", "lima")).toBeNull();
  });

  it("resolves a reference file to its dataset by longest matching directory", () => {
    // `wbd` lives at `hydrology/wbd/`, nested under a `hydrology/` tree that is NOT itself a
    // published dataset. A first-match-wins scan would resolve this to the wrong README the day
    // one is published there.
    expect(citeCorpusPath("data/reference/hydrology/wbd/huc12.geojson", "lima")?.key).toBe("wbd");
    // A file in an unpublished reference directory resolves to nothing at all.
    expect(citeCorpusPath("data/reference/wqs/ohio-temperature-criteria.yaml", "lima")).toBeNull();
  });
});

describe("corpusPathsIn", () => {
  it("pulls corpus paths out of a prose citation, trimming sentence punctuation", () => {
    const text =
      "committed data/extracted/permits/4132514.epa.yaml (final, 2026-05-28); see also " +
      "`data/documents/oepa/2DP00130.pdf`, and data/reference/rsei/inventory.yaml.";
    expect(corpusPathsIn(text)).toEqual([
      "data/extracted/permits/4132514.epa.yaml",
      "data/documents/oepa/2DP00130.pdf",
      "data/reference/rsei/inventory.yaml",
    ]);
  });

  it("ignores a bare directory mention — it addresses no single source", () => {
    expect(corpusPathsIn("filed under data/documents/watershed/ somewhere")).toEqual([]);
  });

  it("dedupes and scans any JSON value, not just strings", () => {
    const feed = [
      { citation: `read from data/extracted/${LIMA_PERMIT}` },
      { nested: { note: `also data/extracted/${LIMA_PERMIT}` } },
    ];
    expect(corpusPathsIn(feed)).toEqual([`data/extracted/${LIMA_PERMIT}`]);
  });
});

describe("citedSourcesIn", () => {
  it("resolves what the site holds and silently drops what it does not", () => {
    const text = `data/extracted/${LIMA_PERMIT} and data/extracted/legal/prr-mandamus/cra-agreement.cra.yaml`;
    // The CRA extraction is a real committed artifact but is NOT projected into the records
    // feed, so it has no record screen — one resolves, one doesn't, and nothing is invented.
    const sources = citedSourcesIn(text, "lima");
    expect(sources.map((s) => s.key)).toEqual([LIMA_PERMIT]);
  });

  it("resolves nothing on a site that holds none of the cited sources", () => {
    expect(citedSourcesIn(`data/extracted/${LIMA_PERMIT}`, "fort-wayne")).toEqual([]);
  });
});

describe("citeGroups", () => {
  it("resolves declared groups against the site's own records, with counts", () => {
    const groups = citeGroups(["permits-epa", "deeds"], "lima");
    expect(groups.map((g) => g.group)).toEqual(["permits-epa", "deeds"]);
    expect(groups[0].href).toBe("/site/records/permits-epa/");
    expect(groups[0].count).toBeGreaterThan(0);
  });

  it("drops a group the site has no rows in — no doors onto an empty index", () => {
    // Lima holds no IDEM permits (that is Indiana's program); Fort Wayne holds no Ohio EPA ones.
    expect(citeGroups(["permits-idem"], "lima")).toEqual([]);
    expect(citeGroups(["permits-epa"], "fort-wayne")).toEqual([]);
    expect(citeGroups(["permits-idem"], "fort-wayne").map((g) => g.group)).toEqual(["permits-idem"]);
  });
});
