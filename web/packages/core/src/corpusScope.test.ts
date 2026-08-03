import { describe, expect, it } from "vitest";
import { corpusOwner, eponymousPrefixes, matchesSegment } from "./corpusScope";
import { LEGAL } from "./legal";

// The frontend port of the Python corpus-scope rule (`watermark.sites._scope`). Its only consumer
// today is the legal facet (#1886) — the one record surface with no bundle feed to scope it — so
// these pin the rule itself, not just the answer it happens to give the fifteen current docs.

describe("matchesSegment", () => {
  it("matches a prefix as a whole path SEGMENT, never as a string prefix", () => {
    expect(matchesSegment("fort-wayne", ["fort-wayne"])).toBe(true);
    expect(matchesSegment("fort-wayne/permits/x.yaml", ["fort-wayne"])).toBe(true);
    // The trap the segment rule exists for: a sibling slug that merely starts the same.
    expect(matchesSegment("fort-wayne-foo/x.yaml", ["fort-wayne"])).toBe(false);
  });

  it("reads a `*/<slug>` term against the SECOND segment only", () => {
    // Site attribution inside a collection named for the issuing agency.
    expect(matchesSegment("oepa/van-wert/permit.yaml", ["*/van-wert"])).toBe(true);
    expect(matchesSegment("idem/fort-wayne/401.yaml", ["*/fort-wayne"])).toBe(true);
    // Not a general glob: a third-segment match is not the site-attribution shape.
    expect(matchesSegment("oepa/permits/van-wert.yaml", ["*/van-wert"])).toBe(false);
    expect(matchesSegment("van-wert", ["*/van-wert"])).toBe(false);
  });

  it("normalizes Windows separators", () => {
    expect(matchesSegment("oepa\\van-wert\\permit.yaml", ["*/van-wert"])).toBe(true);
  });
});

describe("eponymousPrefixes", () => {
  it("DERIVES both prefixes from the slug — nothing is enumerated per site (#1405)", () => {
    expect(eponymousPrefixes("van-wert")).toEqual(["van-wert", "*/van-wert"]);
  });
});

describe("corpusOwner", () => {
  const sites = [{ slug: "lima" }, { slug: "fort-wayne" }, { slug: "van-wert" }, { slug: "urbana" }];

  it("gives a peer its own eponymous subtrees", () => {
    expect(corpusOwner("fort-wayne/notes.md", sites)).toBe("fort-wayne");
    expect(corpusOwner("oepa/van-wert/permit-to-install.yaml", sites)).toBe("van-wert");
    expect(corpusOwner("idem/fort-wayne/401-cert.yaml", sites)).toBe("fort-wayne");
  });

  it("gives the residue to the reference build — the `include=None` minus peers half", () => {
    expect(corpusOwner("legal/select-committee-2026/relator-testimony/x.md", sites)).toBe("lima");
    expect(corpusOwner("commissioners/README.md", sites)).toBe("lima");
    expect(corpusOwner("aedg/roundabouts.summary.opc.yaml", sites)).toBe("lima");
  });
});

describe("the published legal set against the rule", () => {
  it("resolves every doc to the reference build — the committed set is Allen-County OH", () => {
    // This is the FINDING behind #1886 stated as an assertion: not one of these fifteen documents
    // belongs to Fort Wayne (Indiana) or Urbana, and each was being served by both. If a peer ever
    // publishes its own legal record, this expectation is what has to change — deliberately.
    for (const doc of LEGAL) expect(corpusOwner(doc.repo)).toBe("lima");
  });

  it("keeps every published `repo` path rule-derivable (no `site` override needed)", () => {
    // A `site` literal here is the frontend peer of the Python `corpus_relpaths` exceptions and is
    // only for a corpus filed by project/case name. An unnecessary one re-hardcodes the site axis.
    for (const doc of LEGAL) expect(doc.site).toBeUndefined();
  });
});
