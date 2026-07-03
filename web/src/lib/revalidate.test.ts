import { describe, expect, it } from "vitest";
import type { SdmBlock, StoryDocument } from "./sdm";
import { remapSdmHandles, revalidateHandles } from "./revalidate";

type AtomBlock = Extract<SdmBlock, { type: "atom" }>;

describe("revalidateHandles (#1099)", () => {
  it("passes resolvable handles, flags dangling ones, heals renamed ones", () => {
    const catalog = new Set(["record:lima:a", "record:lima:new"]);
    const r = revalidateHandles(["record:lima:a", "record:lima:gone", "record:lima:old"], catalog, {
      "record:lima:old": "record:lima:new",
    });
    expect(r.heals).toEqual([{ from: "record:lima:old", to: "record:lima:new" }]);
    expect(r.stillDangling).toEqual(["record:lima:gone"]);
    expect(r.stale).toBe(true);
  });

  it("is clean when every handle resolves", () => {
    const r = revalidateHandles(["record:lima:a"], new Set(["record:lima:a"]));
    expect(r.stale).toBe(false);
    expect(r.heals).toEqual([]);
    expect(r.stillDangling).toEqual([]);
  });

  it("dedups repeated dangling handles", () => {
    const r = revalidateHandles(["x:y:z", "x:y:z"], new Set());
    expect(r.stillDangling).toEqual(["x:y:z"]);
  });

  it("does not heal to a rename target that is itself gone", () => {
    const r = revalidateHandles(["a:b:c"], new Set(), { "a:b:c": "a:b:d" });
    expect(r.heals).toEqual([]);
    expect(r.stillDangling).toEqual(["a:b:c"]);
  });
});

describe("remapSdmHandles (#1099)", () => {
  it("rewrites atom handles (incl. nested), preserving snapshot + prose, purely", () => {
    const doc: StoryDocument = {
      version: "1.0.0",
      blocks: [
        { type: "paragraph", children: [{ type: "text", value: "hi" }] },
        { type: "atom", handle: "record:lima:old", kind: "record", title: "R" },
        {
          type: "callout",
          variant: "note",
          children: [{ type: "atom", handle: "record:lima:old", kind: "record", title: "R" }],
        },
      ],
    };
    const out = remapSdmHandles(doc, { "record:lima:old": "record:lima:new" });
    expect((out.blocks[1] as AtomBlock).handle).toBe("record:lima:new");
    const callout = out.blocks[2] as Extract<SdmBlock, { type: "callout" }>;
    expect((callout.children[0] as AtomBlock).handle).toBe("record:lima:new");
    // the snapshot is preserved; only the handle moved
    expect((out.blocks[1] as AtomBlock).title).toBe("R");
    // pure — the input document is untouched
    expect((doc.blocks[1] as AtomBlock).handle).toBe("record:lima:old");
  });

  it("leaves a doc with no matching handles unchanged", () => {
    const doc: StoryDocument = {
      version: "1.0.0",
      blocks: [{ type: "atom", handle: "a:b:c", kind: "record", title: "R" }],
    };
    const out = remapSdmHandles(doc, { "x:y:z": "x:y:w" });
    expect((out.blocks[0] as AtomBlock).handle).toBe("a:b:c");
  });
});
