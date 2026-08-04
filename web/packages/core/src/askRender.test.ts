import { describe, expect, it } from "vitest";
import { documentId } from "./documentId";
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

const SITE = "/network/american-sugar-creek-allen-co";

// Shaped like what `buildAskIndex` actually emits, which is the whole point of the #1890 fix:
// `url` is SITE-ROOTED (`siteUrl(...)`, not `/site/...`), `source` is the extracted artifact the
// record was read from, and `doc_rel` — not `source` — is the join to the source document.
const CITES: AskCitation[] = [
  {
    marker: 1,
    id: "records:opc",
    feed: "records",
    title: "Roundabouts OPC — summary",
    url: `${SITE}/site/records/opc/`,
    source: "aedg/roundabouts.summary.opc.yaml",
    doc_rel: "aedg/PRR-01-bundle.ocr.pdf",
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
  it("resolves a document-joined citation to the document's permalink (#328, #1887)", () => {
    // The handle is derived from the rel, so the Worker resolves it with no lookup table —
    // see `documentId`. Pinned literally here: a drift silently 404s every published citation.
    expect(citationHref(CITES[0], "/")).toBe(`${SITE}/doc/ps6mee06/`);
    expect(documentId("aedg/PRR-01-bundle.ocr.pdf")).toBe("ps6mee06");
  });

  it("takes the site from the unit's url, not the deploy base (#1890)", () => {
    // `docPermalink` is site-relative and the only route serving it is `/network/<site>/doc/<id>/`.
    // The deploy base is `/` in every environment (BASE_PATH is unset), so a permalink built from
    // it alone — which is what this did before — is unroutable. Asserted against a peer so a
    // Lima-shaped answer can't pass: the site must come from the citation, not from a constant.
    const peer: AskCitation = { ...CITES[0], url: "/network/urbana/site/records/opc/" };
    expect(citationHref(peer, "/")).toBe("/network/urbana/doc/ps6mee06/");
    expect(citationHref(CITES[0], "/preview")).toBe(`/preview${SITE}/doc/ps6mee06/`);
  });

  it("keeps the unit's own page when nothing joins it to a document", () => {
    // The common case by volume: 2,481 of the network's 2,587 units carry no `doc_rel`.
    const c: AskCitation = { ...CITES[0], doc_rel: null, source_kind: "derived", source: null };
    expect(citationHref(c, "/")).toBe(`${SITE}/site/records/opc/`);
  });

  it("does not promise a permalink to a document that isn't routed (#1887)", () => {
    // `isRoutableDoc` excludes OS exhaust — 54 of Lima's catalogued files. They stay listed and
    // fetchable, but the static build mints no page, so the citation keeps the page that exists.
    const junk: AskCitation = { ...CITES[0], doc_rel: "aedg/scans/Thumbs.db" };
    expect(citationHref(junk, "/")).toBe(`${SITE}/site/records/opc/`);
  });

  it("keeps a network-global unit on its own page — it has no site to root a permalink in", () => {
    // A wiki entity carries `sources[0]` as its artifact but lives at `/wiki/entities/<slug>/`,
    // which names no site. Guessing one would be the same unroutable link by another route.
    const wiki: AskCitation = { ...CITES[0], url: "/wiki/entities/bistrozzi/" };
    expect(citationHref(wiki, "/")).toBe("/wiki/entities/bistrozzi/");
  });
});

describe("renderAnswer", () => {
  it("links a [n] marker to the document's permalink when the unit joins one (#328)", () => {
    const html = renderAnswer("The roundabouts cost ~$1.2M [1].", CITES, "/");
    expect(html).toContain(`<a href="${SITE}/doc/ps6mee06/"`);
    expect(html).toContain("[1]</a>");
    // Title tooltip still includes the source path and page for orientation.
    expect(html).toContain('title="Roundabouts OPC — summary — aedg/roundabouts.summary.opc.yaml p.318"');
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

  it("prefixes permalink citation links with the deploy base (#328)", () => {
    // `base` here is Astro's `BASE_URL` — the deploy prefix, which is `/` unless `BASE_PATH` is
    // set. The site segment is NOT it, and comes from the citation; see `citationHref`.
    expect(renderAnswer("x [1]", CITES, "/preview")).toContain(`href="/preview${SITE}/doc/ps6mee06/"`);
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
    // Document-joined citation links to the document itself, not the abstract records page.
    expect(html).toContain(`href="${SITE}/doc/ps6mee06/"`);
    expect(html).not.toContain(`href="${SITE}/site/records/opc/"`);
    expect(html).toContain("evidence-verified");
    expect(html).toContain("p.318");
  });
});

// The end-to-end guard these fixture cases cannot be lives in `functions/_test/askCitations.test.ts`
// — the ask index's real units, through the real `toCitation`, to the permalinks the build mints.
// It has to sit there rather than here because the projection that carries `doc_rel` onto a citation
// belongs to the Function, and `core` cannot depend on `functions` (the dependency runs the other
// way). Every assertion above passed for as long as the deep link was dead, which is the whole
// argument for having one.
