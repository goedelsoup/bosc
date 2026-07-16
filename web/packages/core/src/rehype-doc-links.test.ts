import { posix } from "node:path";
import { describe, expect, it } from "vitest";
import type { Element, Root } from "hast";
import rehypeDocLinks, { type DocLinkOptions } from "./rehype-doc-links";
import { LINK_MAP, MIGRATED, slugForRepoPath } from "./narrative";
import { PUBLISHED_REFERENCE, refSlugForRepoPath } from "./reference";
import { PUBLISHED_LEGAL, legalSlugForRepoPath } from "./legal";

/** Run the plugin over a single `<a href>` in `filePath` and return the rewritten href. */
function rewrite(filePath: string, href: string, opts?: DocLinkOptions): string {
  const node: Element = { type: "element", tagName: "a", properties: { href }, children: [] };
  const tree: Root = { type: "root", children: [node] };
  rehypeDocLinks(opts)(tree, { path: filePath } as never);
  return node.properties!.href as string;
}

const REPO = "https://github.com/watermark-directory/the-watermark-directory/blob/main/";

describe("rehype-doc-links — guards (data-independent)", () => {
  it("ignores files outside the as-is-rendered roots", () => {
    // A component, not a docs/reference/legal source — never touched.
    expect(rewrite("src/components/Foo.astro", "entities.md")).toBe("entities.md");
  });

  it("leaves external / absolute / anchor / mailto links alone", () => {
    for (const href of [
      "https://x.test/a",
      "http://x.test",
      "/already/abs",
      "#sec",
      "mailto:a@b.test",
      "tel:+1",
    ]) {
      expect(rewrite("docs/narrative/x.md", href)).toBe(href);
    }
  });

  it("leaves a link that escapes the repo root untouched", () => {
    expect(rewrite("docs/x.md", "../../etc/passwd")).toBe("../../etc/passwd");
  });

  it("falls back to the GitHub source for any other in-repo file", () => {
    // docs/x.md → ../src/foo.ts resolves to src/foo.ts (a REPO_DIR), so it points at source.
    expect(rewrite("docs/x.md", "../src/foo.ts")).toBe(`${REPO}src/foo.ts`);
  });

  it("guards the basename map against a same-named corpus file (issue #104 collision guard)", () => {
    // A `data/` file named entities.md must NOT become /wiki/entities/ — it goes to source.
    const out = rewrite("data/reference/echo/README.md", "entities.md");
    expect(out).toBe(`${REPO}data/reference/echo/entities.md`);
    expect(out).not.toContain("/wiki/entities");
  });
});

describe("rehype-doc-links — generated-page (LINK_MAP) branch", () => {
  it("rewrites a bare generated-page basename to its IA route, base-prefixed", () => {
    expect(rewrite("docs/narrative/x.md", "entities.md")).toBe("/wiki/entities/");
    expect(
      rewrite("docs/narrative/x.md", "entities.md", { base: "/network/american-sugar-creek-allen-co" }),
    ).toBe("/wiki/entities/");
  });

  it("rewrites the retired notebooks link to the OPC scenario page, base-prefixed", () => {
    // notebooks.md (the legacy generated page) now points at the native OPC scenario explorer.
    expect(LINK_MAP["notebooks.md"]).toBe("/reports/opc-scenario");
    expect(
      rewrite("docs/narrative/x.md", "notebooks.md", { base: "/network/american-sugar-creek-allen-co" }),
    ).toBe("/network/american-sugar-creek-allen-co/reports/opc-scenario");
  });

  it("preserves the #hash across a rewrite (splitHash)", () => {
    expect(rewrite("docs/narrative/x.md", "entities.md#section-2")).toBe("/wiki/entities/#section-2");
  });
});

/** Resolve a sibling-file href onto a known repo-path target, in that target's own dir. */
function siblingRewrite(target: string, opts?: DocLinkOptions): string {
  const filePath = posix.join(posix.dirname(target), "__sibling__.md");
  return rewrite(filePath, posix.basename(target), opts);
}

describe("rehype-doc-links — data-driven branches (representative real entries)", () => {
  it("rewrites a migrated narrative doc to its /docs/<slug> route", () => {
    const target = [...MIGRATED][0];
    expect(target).toBeTypeOf("string");
    expect(siblingRewrite(target)).toBe(`/docs/${slugForRepoPath(target)}`);
  });

  it("rewrites a published reference README to its /site/reference/<slug> route", () => {
    const target = [...PUBLISHED_REFERENCE][0];
    expect(target).toBeTypeOf("string");
    expect(siblingRewrite(target)).toBe(`/site/reference/${refSlugForRepoPath(target)}`);
  });

  it("rewrites a published legal doc to its /site/legal/<slug> route", () => {
    const target = [...PUBLISHED_LEGAL][0];
    expect(target).toBeTypeOf("string");
    expect(siblingRewrite(target)).toBe(`/site/legal/${legalSlugForRepoPath(target)}`);
  });

  it("keeps the migrated-doc route network-global (no site base) even when a base is set (#1304)", () => {
    // The docs build moved to a single root `/docs/`, so a migrated-doc link is NOT prefixed with
    // the Lima site base — it resolves to the same global route regardless of the plugin's `base`.
    const target = [...MIGRATED][0];
    expect(siblingRewrite(target, { base: "/network/american-sugar-creek-allen-co" })).toBe(
      `/docs/${slugForRepoPath(target)}`,
    );
  });
});
