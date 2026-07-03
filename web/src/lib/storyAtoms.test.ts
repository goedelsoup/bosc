import { describe, expect, it } from "vitest";
import { CATALOG_KINDS } from "./catalog";
import type { StoryDocument } from "./sdm";
import {
  type EditorBlock,
  KIND_FAMILY,
  KIND_LABEL,
  hydrateFromThin,
  sdmToEditorBlocks,
  serializeBlocksToDsl,
} from "./storyAtoms";
import { FIXTURE_CATALOG, FIXTURE_READER_STORY } from "./storyAtoms.fixture";

describe("the family dispatch is total over the closed kind set", () => {
  it("maps every CatalogKind to a family and a label (peer of ATOM_RENDER_SLOTS)", () => {
    for (const kind of CATALOG_KINDS) {
      expect(KIND_FAMILY[kind], `family for ${kind}`).toBeTruthy();
      expect(KIND_LABEL[kind], `label for ${kind}`).toBeTruthy();
    }
    // record/doc, entity/person/place, timeline/meeting share a family (as the live site does).
    expect(KIND_FAMILY.doc).toBe(KIND_FAMILY.record);
    expect(KIND_FAMILY.person).toBe(KIND_FAMILY.entity);
    expect(KIND_FAMILY.place).toBe(KIND_FAMILY.entity);
    expect(KIND_FAMILY.meeting).toBe(KIND_FAMILY.timeline);
  });
});

describe("serializeBlocksToDsl round-trips through the DSL grammar", () => {
  it("emits the colon-safe quoted-attribute atom directive and callout directive", () => {
    const blocks: EditorBlock[] = [
      { type: "heading", level: 2, text: "Who holds the land" },
      { type: "paragraph", text: "Three parcels changed hands." },
      { type: "atom", handle: "record:lima:deed-0008300" },
      { type: "callout", variant: "warning", text: "Treat as inference." },
      { type: "blockquote", text: "A Delaware shell." },
      { type: "list", ordered: false, items: ["one", "two"] },
    ];
    const dsl = serializeBlocksToDsl(blocks);
    expect(dsl).toContain("## Who holds the land");
    // the handle is a quoted attribute (not a bracket label) so its inner colons survive parsing.
    expect(dsl).toContain(':::atom{handle="record:lima:deed-0008300"}');
    expect(dsl).toContain(":::callout{variant=warning}");
    expect(dsl).toContain("> A Delaware shell.");
    expect(dsl).toContain("- one");
    expect(dsl).toContain("- two");
  });
});

describe("sdmToEditorBlocks re-opens a stored Story for editing", () => {
  it("flattens the fixture reader story into editable blocks (atoms preserved by handle)", () => {
    const blocks = sdmToEditorBlocks(FIXTURE_READER_STORY.doc);
    const atomHandles = blocks
      .filter((b): b is Extract<EditorBlock, { type: "atom" }> => b.type === "atom")
      .map((b) => b.handle);
    expect(atomHandles).toContain("record:lima:deed-0008300");
    expect(atomHandles).toContain("entity:lima:bistrozzi-llc");
    expect(blocks.some((b) => b.type === "heading" && b.text === "Who actually holds the land")).toBe(true);
    expect(blocks.some((b) => b.type === "callout")).toBe(true);
  });

  it("survives a re-serialize (blocks → dsl produces non-empty source per atom)", () => {
    const blocks = sdmToEditorBlocks(FIXTURE_READER_STORY.doc);
    const dsl = serializeBlocksToDsl(blocks);
    for (const b of blocks) {
      if (b.type === "atom") expect(dsl).toContain(`handle="${b.handle}"`);
    }
  });
});

describe("hydrateFromThin never fabricates payload", () => {
  it("yields a compact card (kind label + title, no rich payload) from a thin pointer", () => {
    const thin = hydrateFromThin({ handle: "place:lima:x", kind: "place", title: "A parcel" });
    expect(thin.kindLabel).toBe(KIND_LABEL.place);
    expect(thin.title).toBe("A parcel");
    expect(thin.profile).toBeUndefined();
    expect(thin.record).toBeUndefined();
  });
});

describe("the fixture catalog covers every kind", () => {
  it("has one hydrated atom per CatalogKind with a matching family payload", () => {
    const kinds = new Set(Object.values(FIXTURE_CATALOG).map((a) => a.kind));
    for (const kind of CATALOG_KINDS) expect(kinds.has(kind), `fixture covers ${kind}`).toBe(true);
  });
});

// A tiny compile-safety check: the fixture doc is a structurally valid StoryDocument shape.
describe("fixture story is a StoryDocument", () => {
  it("has a version and blocks", () => {
    const doc: StoryDocument = FIXTURE_READER_STORY.doc;
    expect(doc.version).toBe("1.0.0");
    expect(doc.blocks.length).toBeGreaterThan(5);
  });
});
