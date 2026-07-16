import { describe, expect, it } from "vitest";
import type { RecordItem } from "./feeds";
import { recordToBlock } from "./recordBlock";

// BASE_URL is "/" under vitest, so withBase is a no-op prefix throughout.
const baseRecord = (over: Partial<RecordItem> = {}): RecordItem => ({
  rel: "permits/4132514.epa.yaml",
  group: "permits",
  title: "Air Permit-to-Install 4132514",
  warnings: ["one warning"],
  fields: {
    instrument_no: "P0138965", // scalar
    issued: true, // scalar boolean → "yes"
    flow: "~12345", // scalar carrying an inline ~ AND listed approximate
    empty: [], // empty array is a scalar "—", not structured
    applicant: { name: "Tilted Gate LLC" }, // structured object
    tags: ["air", "pti"], // structured (non-empty) array
  },
  approximate_paths: ["flow", "applicant.name"],
  citation: { source: "data/documents/oepa/permit.pdf", source_kind: "document", page: 3, verified: true },
  ...over,
});

describe("recordToBlock", () => {
  const b = recordToBlock(baseRecord());

  it("derives the id, record id, and collection from the rel", () => {
    expect(b.id).toBe("permits-4132514-epa-yaml");
    expect(b.recordId).toBe("4132514"); // both .epa and .yaml extensions stripped
    expect(b.source.collection).toBe("permits");
  });

  it("splits scalar fields from structured ones (no JSON.stringify blob)", () => {
    expect(b.fields.map((f) => f.label)).toEqual(["instrument_no", "issued", "flow", "empty"]);
    expect(b.nested.map((n) => n.label)).toEqual(["applicant", "tags"]);
    expect(b.nested[0]).toMatchObject({
      label: "applicant",
      path: "applicant",
      value: { name: "Tilted Gate LLC" },
    });
  });

  it("formats scalars and marks approximate fields without doubling the ~", () => {
    const byLabel = Object.fromEntries(b.fields.map((f) => [f.label, f]));
    expect(byLabel.issued.value).toBe("yes");
    expect(byLabel.empty.value).toBe("—");
    expect(byLabel.instrument_no).toMatchObject({ value: "P0138965", warn: false });
    // flow is approximate AND already carries an inline ~ → stays single, warn set.
    expect(byLabel.flow).toMatchObject({ value: "~12345", warn: true });
  });

  it("carries provenance and the approximate-path list through", () => {
    expect(b.source).toMatchObject({ file: "data/documents/oepa/permit.pdf", pages: "p.3" });
    expect(b.evidence).toBe("verified");
    expect(b.approxPaths).toEqual(["flow", "applicant.name"]);
    expect(b.warnings).toEqual(["one warning"]);
  });

  it("links the compact row at the record screen and pre-fills the correction deep link", () => {
    expect(b.href).toBe(
      "/network/american-sugar-creek-allen-co/site/records/permits/permits-4132514-epa-yaml",
    );
    expect(b.correctHref).toContain(
      "/network/american-sugar-creek-allen-co/submit?ref_kind=record&ref_id=permits%2F4132514.epa.yaml",
    );
    expect(b.kind.startsWith("Record · ")).toBe(true);
  });

  it("marks unverified citations as inference and shows pages as '—' when absent", () => {
    const b2 = recordToBlock(
      baseRecord({ citation: { source: null, source_kind: "document", page: null, verified: false } }),
    );
    expect(b2.evidence).toBe("inference");
    expect(b2.source.pages).toBe("—");
    expect(b2.source.file).toBe("permits/4132514.epa.yaml"); // falls back to rel
  });

  it("drops the record→chapter walk backlink while the story is held coming-soon (#1526)", () => {
    // The active site under vitest is Lima; its Project BOSC walk is `comingSoon`, so it surfaces no
    // *readable* story and `activeStoryAnchorFor` resolves nothing. A record that would anchor a
    // chapter therefore carries NO `seenIn` and NO `walk` connect chip — a held story contributes no
    // readable backlinks, exactly like an unanchored record. (The anchor-resolution mechanism itself
    // is covered in walk.test via `storyAnchorFor` / `activeStoryAnchorFor`.)
    const anchored = recordToBlock(baseRecord({ rel: "aedg/roundabouts.summary.opc.yaml", group: "aedg" }));
    expect(anchored.seenIn).toBeUndefined();
    expect(anchored.connect.map((c) => c.kind)).toEqual(["records"]);
    expect(anchored.connect.some((c) => c.kind === "walk")).toBe(false);

    const unanchored = recordToBlock(baseRecord({ rel: "permits/9999999.epa.yaml" }));
    expect(unanchored.seenIn).toBeUndefined();
    expect(unanchored.connect.some((c) => c.kind === "walk")).toBe(false);
  });
});
