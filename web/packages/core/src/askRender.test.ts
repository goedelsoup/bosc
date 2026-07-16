import { describe, expect, it } from "vitest";
import { escapeHtml } from "./format";
import {
  type AskCitation,
  badgeKind,
  citationHref,
  renderAnswer,
  renderSources,
  searchingHint,
  withBasePath,
} from "./askRender";

const CITES: AskCitation[] = [
  {
    marker: 1,
    id: "records:opc",
    feed: "records",
    title: "Roundabouts OPC — summary",
    url: "/site/records/opc/",
    source: "data/documents/aedg/PRR-01-bundle.ocr.pdf",
    page: 318,
    source_kind: "document",
    verified: true,
  },
];

describe("escapeHtml", () => {
  it("neutralizes HTML in model/data text", () => {
    expect(escapeHtml('<img src=x onerror="alert(1)">')).toBe(
      "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;",
    );
  });
});

describe("withBasePath", () => {
  it("joins base + root-absolute path without doubling slashes", () => {
    expect(withBasePath("/network/american-sugar-creek-allen-co", "/site/records/opc/")).toBe(
      "/network/american-sugar-creek-allen-co/site/records/opc/",
    );
    expect(withBasePath("/", "/timeline")).toBe("/timeline");
  });
});

describe("citationHref", () => {
  it("resolves a document-sourced citation to the doc viewer page (#328)", () => {
    expect(citationHref(CITES[0], "/")).toBe("/site/documents/aedg/PRR-01-bundle.ocr.pdf");
  });

  it("falls back to the bundle url for non-document sources", () => {
    const c: AskCitation = { ...CITES[0], source_kind: "derived", source: null };
    expect(citationHref(c, "/")).toBe("/site/records/opc/");
  });

  it("prefixes with the site base", () => {
    expect(citationHref(CITES[0], "/network/american-sugar-creek-allen-co")).toBe(
      "/network/american-sugar-creek-allen-co/site/documents/aedg/PRR-01-bundle.ocr.pdf",
    );
  });
});

describe("renderAnswer", () => {
  it("links a [n] marker to the doc viewer page when source is a document (#328)", () => {
    const html = renderAnswer("The roundabouts cost ~$1.2M [1].", CITES, "/");
    expect(html).toContain('<a href="/site/documents/aedg/PRR-01-bundle.ocr.pdf"');
    expect(html).toContain("[1]</a>");
    // Title tooltip still includes the source path and page for orientation.
    expect(html).toContain(
      'title="Roundabouts OPC — summary — data/documents/aedg/PRR-01-bundle.ocr.pdf p.318"',
    );
  });

  it("flags an unresolved marker instead of dropping it", () => {
    const html = renderAnswer("Mystery [4].", CITES, "/");
    expect(html).toContain("ask-cite--unresolved");
    expect(html).toContain("[4]</sup>");
  });

  it("escapes HTML in the answer body", () => {
    expect(renderAnswer("<script>alert(1)</script>", [], "/")).not.toContain("<script>");
  });

  it("renders bullet lists and bold", () => {
    expect(renderAnswer("- one\n- two", [], "/")).toContain("<ul><li>one</li><li>two</li></ul>");
    expect(renderAnswer("**bold** claim", [], "/")).toContain("<strong>bold</strong>");
  });

  it("prefixes doc viewer citation links with the site base (#328)", () => {
    expect(renderAnswer("x [1]", CITES, "/network/american-sugar-creek-allen-co")).toContain(
      'href="/network/american-sugar-creek-allen-co/site/documents/aedg/PRR-01-bundle.ocr.pdf"',
    );
  });
});

describe("searchingHint", () => {
  it("pluralizes the record count (#331)", () => {
    expect(searchingHint(6)).toBe("Searching 6 records…");
    expect(searchingHint(1)).toBe("Searching 1 record…");
    expect(searchingHint(0)).toBe("Searching 0 records…");
  });
});

describe("badgeKind", () => {
  it("maps provenance to an evidence badge", () => {
    expect(badgeKind(CITES[0])).toBe("verified");
    expect(badgeKind({ ...CITES[0], verified: false, source_kind: "derived" })).toBe("open");
    expect(badgeKind({ ...CITES[0], verified: false, source_kind: "document" })).toBe("inference");
  });
});

describe("renderSources", () => {
  it("lists each cited source with its badge + doc viewer link, empty when none (#328)", () => {
    expect(renderSources([], "/")).toBe("");
    const html = renderSources(CITES, "/");
    expect(html).toContain("Sources used");
    // Document-sourced citation links to the viewer page, not the abstract records page.
    expect(html).toContain('href="/site/documents/aedg/PRR-01-bundle.ocr.pdf"');
    expect(html).not.toContain('href="/site/records/opc/"');
    expect(html).toContain("evidence-verified");
    expect(html).toContain("p.318");
  });
});
