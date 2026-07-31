// Structured-citation primitive tests (#1584).
// buildCitation is pure — no fetch, no bundle — so these assert the contract directly: what gets
// omitted, how a page span renders, where `verified` comes from, and that nothing is invented.

import { describe, expect, it } from "vitest";
import { QUOTE_MAX_CHARS, buildCitation } from "@watermark/functions/api/_lib/mcpCitation";

describe("buildCitation — omission", () => {
  it("omits every field the source doesn't carry rather than nulling it", () => {
    const c = buildCitation({ source: "recorder/x.deed.yaml", source_kind: "document" });
    expect(c).toEqual({
      source: "recorder/x.deed.yaml",
      source_kind: "document",
      verified: true,
      evidence: "verified",
      label: "recorder/x.deed.yaml [verified]",
    });
    // A page the source never carried is ABSENT, not null and not guessed.
    expect(c).not.toHaveProperty("page");
    expect(c).not.toHaveProperty("pages");
    expect(c).not.toHaveProperty("document_id");
  });

  it("drops blank and non-positive values instead of emitting them", () => {
    const c = buildCitation({
      source: "   ",
      document_id: "",
      page: 0,
      pages: [0, -3],
      section: "  ",
      confidence: "",
    });
    expect(Object.keys(c).sort()).toEqual(["evidence", "label", "verified"]);
    expect(c.label).toBe("uncited [inference]");
  });

  it("keeps a page span only when it says more than `page` alone", () => {
    expect(buildCitation({ page: 7, pages: [7] })).not.toHaveProperty("pages");
    expect(buildCitation({ page: 7, pages: [8, 7, 7] }).pages).toEqual([7, 8]);
  });
});

describe("buildCitation — evidence class", () => {
  it("derives verified from source_kind when the row doesn't record it", () => {
    expect(buildCitation({ source_kind: "document" }).verified).toBe(true);
    expect(buildCitation({ source_kind: "connector" }).verified).toBe(true);
    expect(buildCitation({ source_kind: "reference" }).verified).toBe(false);
    expect(buildCitation({ source_kind: "assumption" }).verified).toBe(false);
    expect(buildCitation({ source_kind: "derived" }).verified).toBe(false);
    expect(buildCitation({}).verified).toBe(false);
  });

  it("takes a recorded verified flag verbatim, so it can never disagree with the bundle", () => {
    // The bundle computes `verified` itself; a row that carries it wins over the derivation.
    expect(buildCitation({ source_kind: "derived", verified: true }).verified).toBe(true);
    expect(buildCitation({ source_kind: "document", verified: false }).evidence).toBe("inference");
  });
});

describe("buildCitation — the human label", () => {
  it("renders a single page as `p.` and a span as `pp.`", () => {
    const doc = { source: "a.yaml", source_kind: "document" };
    expect(buildCitation({ ...doc, page: 17 }).label).toBe("a.yaml p. 17 [verified]");
    expect(buildCitation({ ...doc, page: 17, pages: [17, 18] }).label).toBe("a.yaml pp. 17-18 [verified]");
  });

  it("collapses a non-contiguous read into runs rather than a false range", () => {
    // The real shape from data/extracted/oepa/2PE00000.npdes.yaml — 9 pages, 4 runs. Rendering
    // it "1-93" would claim 84 pages the extraction never read.
    const c = buildCitation({
      source: "oepa/2PE00000.npdes.yaml",
      source_kind: "document",
      page: 1,
      pages: [1, 2, 3, 4, 37, 40, 84, 85, 93],
    });
    expect(c.label).toBe("oepa/2PE00000.npdes.yaml pp. 1-4, 37, 40, 84-85, 93 [verified]");
  });

  it("appends a section and leads with the document id when there is no source", () => {
    expect(
      buildCitation({ document_id: "oepa/permit.pdf", source_kind: "document", page: 3, section: "IV.B" })
        .label,
    ).toBe("oepa/permit.pdf p. 3 (IV.B) [verified]");
  });

  it("falls back to free-text provenance — the only cite most projected facts have", () => {
    const c = buildCitation({
      source_kind: "assumption",
      note: "OPSB case 24-0809-EL-BNR, application Exhibit 3",
    });
    expect(c.note).toBe("OPSB case 24-0809-EL-BNR, application Exhibit 3");
    expect(c.label).toBe("OPSB case 24-0809-EL-BNR, application Exhibit 3 [inference]");
  });
});

describe("buildCitation — quote and url", () => {
  it("caps a quote to a lead excerpt so the object can't duplicate a whole page", () => {
    const page = "x".repeat(QUOTE_MAX_CHARS * 3);
    const c = buildCitation({ quote: page });
    expect((c.quote as string).length).toBe(QUOTE_MAX_CHARS + 1); // + the ellipsis
    expect((c.quote as string).endsWith("…")).toBe(true);
  });

  it("leaves a short quote verbatim", () => {
    expect(buildCitation({ quote: "Outfall 001 shall not exceed 0.5 mg/L." }).quote).toBe(
      "Outfall 001 shall not exceed 0.5 mg/L.",
    );
  });

  it("resolves a root-absolute source_url against the request so a client can follow it", () => {
    const c = buildCitation({ source_url: "/network/lima/site/records/opc/" }, "https://ex.test/api/mcp");
    expect(c.source_url).toBe("https://ex.test/network/lima/site/records/opc/");
  });

  it("leaves an already-absolute url alone and drops an unresolvable one", () => {
    expect(
      buildCitation({ source_url: "https://cdn.test/a.pdf" }, "https://ex.test/api/mcp").source_url,
    ).toBe("https://cdn.test/a.pdf");
    expect(buildCitation({ source_url: "/a" }, "not-a-url")).not.toHaveProperty("source_url");
  });
});
