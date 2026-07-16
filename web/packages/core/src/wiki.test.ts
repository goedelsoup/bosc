import { describe, expect, it } from "vitest";
import { norm, renderBody, type WikiTarget } from "./wiki";

// An explicit index so the markdown rendering is tested in isolation (no feed loading).
const index = new Map<string, WikiTarget>([
  [
    norm("Cynthia Leis"),
    {
      url: "/network/american-sugar-creek-allen-co/site/people/cynthia-leis/",
      label: "Cynthia Leis",
      kind: "person",
    },
  ],
]);

describe("renderBody — light markdown", () => {
  it("renders `##` blocks as headings (## → h2, capped at h4)", () => {
    expect(renderBody("## How she appears", index)).toBe("<h2>How she appears</h2>");
    expect(renderBody("### Sub", index)).toBe("<h3>Sub</h3>");
    expect(renderBody("###### Deep", index)).toBe("<h4>Deep</h4>");
  });

  it("renders `- ` bullet blocks as a <ul>, folding soft-wrapped lines into one <li>", () => {
    const body = "- first item\n  wrapped onward\n- second item";
    expect(renderBody(body, index)).toBe("<ul><li>first item wrapped onward</li><li>second item</li></ul>");
  });

  it("renders inline bold, italic, and code", () => {
    expect(renderBody("a **bold** and *italic* and `code` here", index)).toBe(
      "<p>a <strong>bold</strong> and <em>italic</em> and <code>code</code> here</p>",
    );
  });

  it("renders `[text](url)` markdown links", () => {
    expect(renderBody("see [the policy](../extracted/x.yaml) now", index)).toBe(
      '<p>see <a href="../extracted/x.yaml">the policy</a> now</p>',
    );
  });

  it("resolves `[[wiki links]]` via the index; flags unresolved ones", () => {
    expect(renderBody("ask [[Cynthia Leis]] today", index)).toBe(
      '<p>ask <a href="/network/american-sugar-creek-allen-co/site/people/cynthia-leis/">Cynthia Leis</a> today</p>',
    );
    expect(renderBody("who is [[Nobody]]?", index)).toContain(
      '<span class="wikilink-missing" title="unresolved wiki link">Nobody</span>',
    );
  });

  it("collapses paragraph soft wraps to spaces and splits blocks on blank lines", () => {
    expect(renderBody("line one\nline two\n\nnext para", index)).toBe(
      "<p>line one line two</p>\n<p>next para</p>",
    );
  });

  it("escapes HTML in body text (no injection through prose)", () => {
    expect(renderBody("a <script>x</script> & b", index)).toBe(
      "<p>a &lt;script&gt;x&lt;/script&gt; &amp; b</p>",
    );
  });
});
