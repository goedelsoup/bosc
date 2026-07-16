import { describe, expect, it } from "vitest";
import type { Catalog, CatalogAtom, CatalogKind } from "./catalog";
import { CATALOG_KINDS } from "./catalog";
import {
  ATOM_RENDER_SLOTS,
  SDM_CONTRACT_VERSION,
  type SdmBlock,
  type StoryDocument,
  resolveSdmAtoms,
  sdmHandles,
  sdmIsResolvable,
  validateStoryDocument,
} from "./sdm";

const doc = (blocks: SdmBlock[]): StoryDocument => ({ version: SDM_CONTRACT_VERSION, blocks });

/** An atom block with its thin snapshot (kind + title). */
const at = (handle: string, kind: CatalogKind = "record", title = "x"): SdmBlock => ({
  type: "atom",
  handle,
  kind,
  title,
});

function catalogOf(atoms: CatalogAtom[]): Catalog {
  return {
    site: "lima",
    version: "v",
    byHandle: new Map(atoms.map((a) => [a.handle, a])),
    sites: new Set(atoms.map((a) => a.site)),
  };
}

const recordAtom: CatalogAtom = {
  handle: "record:lima:x.deed.yaml",
  kind: "record",
  site: "lima",
  localId: "x.deed.yaml",
  title: "A deed",
  feed: "records",
};

// --- the preordained component vocabulary ---------------------------------------------------
describe("ATOM_RENDER_SLOTS", () => {
  it("has exactly one render slot per catalog kind (a closed, exhaustive dispatch table)", () => {
    expect(Object.keys(ATOM_RENDER_SLOTS).sort()).toEqual([...CATALOG_KINDS].sort());
    for (const kind of CATALOG_KINDS) expect(ATOM_RENDER_SLOTS[kind]).toBe(`atom:${kind}`);
  });
});

// --- structural validation: the "data, not code" guard --------------------------------------
describe("validateStoryDocument", () => {
  it("accepts a doc of only the closed vocabulary, including callouts and nested blocks", () => {
    const value = doc([
      { type: "heading", level: 2, children: [{ type: "text", value: "Title" }] },
      {
        type: "paragraph",
        children: [
          { type: "text", value: "See " },
          { type: "strong", children: [{ type: "text", value: "this" }] },
          { type: "link", href: "/x", children: [{ type: "text", value: "link" }] },
        ],
      },
      { type: "list", ordered: false, items: [[at("record:lima:x.deed.yaml", "record", "A deed")]] },
      {
        type: "callout",
        variant: "warning",
        children: [{ type: "paragraph", children: [{ type: "text", value: "heads up" }] }],
      },
      { type: "blockquote", children: [{ type: "paragraph", children: [{ type: "text", value: "q" }] }] },
    ]);
    expect(validateStoryDocument(value)).toEqual(value);
  });

  it("rejects an unknown / code-bearing block type (nowhere for a script node to hide)", () => {
    expect(
      validateStoryDocument(doc([{ type: "html", value: "<script>" } as unknown as SdmBlock])),
    ).toBeNull();
    expect(
      validateStoryDocument(doc([{ type: "mdxJsxFlowElement", name: "img" } as unknown as SdmBlock])),
    ).toBeNull();
  });

  it("rejects an atom missing its snapshot, a bad callout variant, and a bad heading level", () => {
    expect(
      validateStoryDocument(doc([{ type: "atom", handle: "record:lima:x" } as unknown as SdmBlock])),
    ).toBeNull(); // no kind/title snapshot
    expect(
      validateStoryDocument(
        doc([{ type: "atom", handle: "x", kind: "bogus", title: "t" } as unknown as SdmBlock]),
      ),
    ).toBeNull(); // kind not a real catalog kind
    expect(
      validateStoryDocument(doc([{ type: "callout", variant: "boom", children: [] } as unknown as SdmBlock])),
    ).toBeNull();
    expect(
      validateStoryDocument(doc([{ type: "heading", level: 1, children: [] } as unknown as SdmBlock])),
    ).toBeNull();
    expect(validateStoryDocument({ blocks: [] })).toBeNull(); // missing version
  });
});

// --- the resolver seam ----------------------------------------------------------------------
describe("sdmHandles", () => {
  it("collects every atom handle depth-first, including nested in lists, callouts, blockquotes", () => {
    const value = doc([
      at("record:lima:a"),
      { type: "blockquote", children: [at("entity:lima:b", "entity")] },
      { type: "callout", variant: "note", children: [at("lead:lima:d", "lead")] },
      {
        type: "list",
        ordered: true,
        items: [[at("record:lima:c")], [{ type: "paragraph", children: [{ type: "text", value: "x" }] }]],
      },
    ]);
    expect(sdmHandles(value)).toEqual(["record:lima:a", "entity:lima:b", "lead:lima:d", "record:lima:c"]);
  });
});

describe("resolveSdmAtoms / sdmIsResolvable", () => {
  const catalog = catalogOf([recordAtom]);

  it("resolves a live handle to its atom and dedupes repeats", () => {
    const value = doc([at("record:lima:x.deed.yaml"), at("record:lima:x.deed.yaml")]);
    const resolved = resolveSdmAtoms(value, catalog);
    expect(resolved.size).toBe(1);
    expect(resolved.get("record:lima:x.deed.yaml")).toEqual({ ok: true, atom: recordAtom });
    expect(sdmIsResolvable(value, catalog)).toBe(true);
  });

  it("surfaces the failure reason for a dangling handle and fails the write-time gate", () => {
    const value = doc([at("record:lima:retired.deed.yaml")]);
    expect(resolveSdmAtoms(value, catalog).get("record:lima:retired.deed.yaml")).toEqual({
      ok: false,
      handle: "record:lima:retired.deed.yaml",
      reason: "dangling",
    });
    expect(sdmIsResolvable(value, catalog)).toBe(false);
  });
});
