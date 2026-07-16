import { describe, expect, it } from "vitest";
import type { Catalog, CatalogAtom } from "./catalog";
import { validateStoryDocument } from "./sdm";
import { compileDsl, compileStory, mdxDataFormat } from "./storyCompile";

// A catalog holding one resolvable record atom — the compiler resolves handles against it.
const recordAtom: CatalogAtom = {
  handle: "record:lima:x.deed.yaml",
  kind: "record",
  site: "lima",
  localId: "x.deed.yaml",
  title: "A deed",
  feed: "records",
};
const catalog: Catalog = {
  site: "lima",
  version: "v",
  byHandle: new Map([[recordAtom.handle, recordAtom]]),
  sites: new Set(["lima"]),
};

function compiled(source: string) {
  const r = compileDsl(source, catalog);
  if (!r.ok) throw new Error(`expected ok, got errors: ${r.errors.map((e) => e.message).join("; ")}`);
  return r.doc;
}

// --- DSL: the markdown subset ---------------------------------------------------------------
describe("compileDsl — prose subset", () => {
  it("lowers headings, inline marks, links, lists, and blockquotes to SDM", () => {
    const doc = compiled(
      [
        "## Heading",
        "",
        "Some **bold** and *em* and `code` and [a link](/x).",
        "",
        "- one",
        "- two",
        "",
        "> quoted",
      ].join("\n"),
    );
    expect(doc.blocks[0]).toEqual({
      type: "heading",
      level: 2,
      children: [{ type: "text", value: "Heading" }],
    });
    expect(doc.blocks[1]).toEqual({
      type: "paragraph",
      children: [
        { type: "text", value: "Some " },
        { type: "strong", children: [{ type: "text", value: "bold" }] },
        { type: "text", value: " and " },
        { type: "emphasis", children: [{ type: "text", value: "em" }] },
        { type: "text", value: " and " },
        { type: "code", value: "code" },
        { type: "text", value: " and " },
        { type: "link", href: "/x", children: [{ type: "text", value: "a link" }] },
        { type: "text", value: "." },
      ],
    });
    expect(doc.blocks[2]).toEqual({
      type: "list",
      ordered: false,
      items: [
        [{ type: "paragraph", children: [{ type: "text", value: "one" }] }],
        [{ type: "paragraph", children: [{ type: "text", value: "two" }] }],
      ],
    });
    expect(doc.blocks[3].type).toBe("blockquote");
    // The whole doc is structurally valid data-not-code.
    expect(validateStoryDocument(doc)).toEqual(doc);
  });

  it("clamps a forbidden h1 into the body range [2,4]", () => {
    const doc = compiled("# Title\n");
    expect(doc.blocks[0]).toMatchObject({ type: "heading", level: 2 });
  });
});

// --- DSL: directives ------------------------------------------------------------------------
describe("compileDsl — directives", () => {
  it("lowers `:::atom{handle}` to a resolved atom block with the thin snapshot", () => {
    const doc = compiled(':::atom{handle="record:lima:x.deed.yaml"}\n:::\n');
    expect(doc.blocks[0]).toEqual({
      type: "atom",
      handle: "record:lima:x.deed.yaml",
      kind: "record",
      title: "A deed", // snapshot captured from the live catalog atom
    });
  });

  it("lowers `:::callout{variant=…}` wrapping prose, and degrades an unknown variant to note", () => {
    const warn = compiled(":::callout{variant=warning}\nHeads up.\n:::\n");
    expect(warn.blocks[0]).toMatchObject({ type: "callout", variant: "warning" });
    const odd = compiled(":::callout{variant=zzz}\nHi.\n:::\n");
    expect(odd.blocks[0]).toMatchObject({ type: "callout", variant: "note" });
  });
});

// --- DSL: author-facing errors --------------------------------------------------------------
describe("compileDsl — errors", () => {
  const errs = (source: string) => {
    const r = compileDsl(source, catalog);
    return r.ok ? [] : r.errors.map((e) => e.kind);
  };

  it("rejects raw HTML (assertNoCode)", () => {
    expect(errs("<div>hi</div>\n")).toContain("code");
  });

  it("rejects an unknown handle", () => {
    expect(errs(':::atom{handle="record:lima:nope.yaml"}\n:::\n')).toContain("unknown-handle");
  });

  it("rejects an unknown directive", () => {
    expect(errs(":::mystery[x]\n:::\n")).toContain("unknown-directive");
  });

  it("rejects an unsafe link URL", () => {
    expect(errs("[click](javascript:alert(1))\n")).toContain("unsafe-link");
  });
});

// --- MDX-as-data + the bake-off -------------------------------------------------------------
describe("mdx-as-data front-end", () => {
  const compileMdx = (source: string) => compileStory(source, mdxDataFormat, catalog);

  it("hard-rejects executable MDX (expressions + imports) but keeps JSX", () => {
    const expr = compileMdx("Value {1 + 1}.\n");
    expect(expr.ok).toBe(false);
    if (!expr.ok) expect(expr.errors[0].kind).toBe("code");

    const esm = compileMdx('import x from "y"\n\nText.\n');
    expect(esm.ok).toBe(false);
    if (!esm.ok) expect(esm.errors[0].kind).toBe("code");
  });

  it("lowers `<Atom/>` and `<Callout>` JSX to atom/callout SDM", () => {
    const r = compileMdx('<Atom handle="record:lima:x.deed.yaml" />\n');
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.doc.blocks[0]).toMatchObject({ type: "atom", kind: "record", title: "A deed" });
  });

  it("produces byte-identical SDM to the DSL for an equivalent Story (the bake-off)", () => {
    const dsl = compileDsl(
      ["## Title", "", "Some **bold** text.", "", ':::atom{handle="record:lima:x.deed.yaml"}', ":::"].join(
        "\n",
      ),
      catalog,
    );
    const mdx = compileMdx(
      ["## Title", "", "Some **bold** text.", "", '<Atom handle="record:lima:x.deed.yaml" />'].join("\n"),
    );
    expect(dsl.ok && mdx.ok).toBe(true);
    if (dsl.ok && mdx.ok) expect(mdx.doc.blocks).toEqual(dsl.doc.blocks);
  });
});
