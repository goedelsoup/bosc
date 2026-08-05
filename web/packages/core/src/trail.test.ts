import { describe, expect, it } from "vitest";
import { RECORD_FACETS, SECTION_META } from "./readiness";
import { SITE_BASE, WALK_BASE } from "./routes";
import { type Crumb, trailDeclared, trailFor } from "./trail";

/** `Directory › A › B` — the shape assertions read against, so a diff shows the whole trail. */
const render = (crumbs: Crumb[]): string => crumbs.map((c) => c.label).join(" › ");

describe("trailFor", () => {
  it("gives the root no trail — there is nothing above the directory", () => {
    expect(trailFor("/")).toEqual([]);
    expect(trailFor("")).toEqual([]);
  });

  it("opens every other trail with a link back to the directory", () => {
    expect(trailFor("/wiki/")[0]).toEqual({ label: "Directory", href: "/" });
    expect(trailFor("/about/mission")[0]).toEqual({ label: "Directory", href: "/" });
  });

  it("ends on the current page, unlinked", () => {
    const crumbs = trailFor("/about/mission");
    expect(render(crumbs)).toBe("Directory › About › Mission");
    expect(crumbs.at(-1)).toEqual({ label: "Mission" });
  });

  it("names the site a deep page sits under", () => {
    // The issue's second criterion: a deep Lima page and a deep Fort Wayne page must be
    // distinguishable at a glance. The label is the registry's place, not the URL id.
    expect(render(trailFor(`${SITE_BASE}/timeline`))).toBe("Directory › Lima › Timeline");
    expect(render(trailFor("/network/fort-wayne/timeline"))).toBe("Directory › Fort Wayne › Timeline");
  });

  it("resolves the deepest content route in the build", () => {
    const crumbs = trailFor(`${SITE_BASE}/site/records/permits/4132514-epa-yaml`, {
      leaf: "Air permit-to-install 04-13251",
      labels: { permits: "Permits & approvals" },
    });
    expect(render(crumbs)).toBe(
      "Directory › Lima › The record › Records › Permits & approvals › Air permit-to-install 04-13251",
    );
    expect(crumbs.map((c) => c.href)).toEqual([
      "/",
      SITE_BASE,
      `${SITE_BASE}/site/`,
      `${SITE_BASE}/site/records/`,
      `${SITE_BASE}/site/records/permits/`,
      undefined,
    ]);
  });

  it("elides /network between the directory and a site, but keeps it as its own page", () => {
    // `/network` IS a page (#1888), so it gets a crumb when a reader is standing on it. As an
    // ancestor it would read "Directory › All sites › Lima" — the same thing named twice.
    expect(render(trailFor("/network"))).toBe("Directory › All sites");
    expect(render(trailFor(SITE_BASE))).toBe("Directory › Lima");
  });

  it("keeps a static sibling of the site param on the network tier", () => {
    // `/network/connect` must not resolve as a site slug.
    expect(render(trailFor("/network/connect"))).toBe("Directory › Connect");
  });

  it("drops the namespace segments that address no page", () => {
    // `<site>/doc` and `<site>/stories` have no landing; the child carries the name that matters.
    expect(render(trailFor(`${SITE_BASE}/doc/a1b2c3d4`, { leaf: "PRR-01-bundle.ocr.pdf" }))).toBe(
      "Directory › Lima › PRR-01-bundle.ocr.pdf",
    );
    // The codename segment is a URL key, not a title — the story page names it via `labels`.
    expect(
      render(trailFor(`${WALK_BASE}/water`, { leaf: "Water", labels: { "project-bosc": "Project BOSC" } })),
    ).toBe("Directory › Lima › Project BOSC › Water");
  });

  it("splices in ancestors the URL deliberately does not carry", () => {
    // The document permalink is flat by design (#1887) — the collection and container it drops
    // are exactly what a reader needs to climb back to.
    const crumbs = trailFor(`${SITE_BASE}/doc/a1b2c3d4`, {
      leaf: "0001_Notice.pdf",
      insert: [
        { label: "Documents", href: `${SITE_BASE}/site/documents/` },
        { label: "legal", href: `${SITE_BASE}/site/documents/legal/` },
        { label: "prr-mandamus", href: `${SITE_BASE}/site/documents/legal/prr-mandamus/` },
      ],
    });
    expect(render(crumbs)).toBe("Directory › Lima › Documents › legal › prr-mandamus › 0001_Notice.pdf");
  });

  it("prefers a page-supplied label for a segment the model cannot name", () => {
    const crumbs = trailFor(`${SITE_BASE}/site/documents/legal/prr-mandamus/page-4`, {
      labels: { legal: "Legal & records-access", "prr-mandamus": "prr-mandamus" },
    });
    expect(render(crumbs)).toBe(
      "Directory › Lima › The record › Documents › Legal & records-access › prr-mandamus › Page 4",
    );
  });

  it("uses the page title only where the leaf's name is data", () => {
    // A declared leaf keeps its editorial label even though Base always passes the page title.
    expect(render(trailFor(`${SITE_BASE}/environment/rsei`, { leaf: "RSEI / toxics" }))).toBe(
      "Directory › Lima › The environment › RSEI / toxics",
    );
    expect(render(trailFor("/wiki/entities/qts-realty-trust", { leaf: "QTS Realty Trust" }))).toBe(
      "Directory › Wiki › Entities › QTS Realty Trust",
    );
  });

  it("folds a nested narrative slug into one crumb — its parent directory has no landing", () => {
    expect(render(trailFor("/docs/legal/mandamus-analysis", { leaf: "The mandamus analysis" }))).toBe(
      "Directory › Docs › The mandamus analysis",
    );
  });

  it("does not link an ancestor that addresses no page", () => {
    const showcase = trailFor("/showcase/charts");
    expect(render(showcase)).toBe("Directory › Component previews › Chart set");
    expect(showcase[1].href).toBeUndefined();
  });

  it("strips the deploy base before resolving, and returns hrefs without it", () => {
    // Hrefs come back pre-base (the `nav.ts` convention); the template applies `withBase`.
    const crumbs = trailFor(`/bosc${SITE_BASE}/timeline`, { base: "/bosc" });
    expect(render(crumbs)).toBe("Directory › Lima › Timeline");
    expect(crumbs[1].href).toBe(SITE_BASE);
  });

  it("degrades an undeclared segment to plain text rather than a link it cannot vouch for", () => {
    const crumbs = trailFor("/wiki/entities/qts/nonsense");
    expect(render(crumbs)).toBe("Directory › Wiki › Entities › Qts › Nonsense");
    expect(crumbs.at(-1)?.href).toBeUndefined();
  });
});

describe("trailDeclared", () => {
  it("accepts a declared route pattern and rejects an undeclared one", () => {
    expect(trailDeclared("/network/*/site/records/*/*")).toBe(true);
    expect(trailDeclared("/docs/**")).toBe(true);
    expect(trailDeclared("/")).toBe(true);
    expect(trailDeclared("/network/*/site/newthing")).toBe(false);
  });
});

describe("the trail model agrees with the section model", () => {
  // Two tables name the same destinations. They're declared separately — `readiness.ts` gates
  // pages, `trail.ts` names URL segments — so this pins them together rather than trusting the
  // labels to be re-typed identically.
  it("labels each record facet's index the way the facet declares it", () => {
    for (const facet of Object.values(RECORD_FACETS)) {
      // `route` is site-relative (`/site/records/`); the facets that live off `/site/` are the
      // record's own leaves, which is what this trail level covers.
      const crumbs = trailFor(`${SITE_BASE}${facet.route}`);
      expect(crumbs.at(-1)?.label, `facet ${facet.route}`).toBe(facet.label);
    }
  });

  it("labels the section landings the way SECTION_META does", () => {
    const landings: [string, keyof typeof SECTION_META][] = [
      ["/site/", "record"],
      ["/timeline", "timeline"],
      ["/environment/", "environment"],
      ["/leads", "leads"],
      ["/contacts", "contacts"],
      ["/reports/", "reports"],
    ];
    for (const [route, section] of landings) {
      expect(trailFor(`${SITE_BASE}${route}`).at(-1)?.label, route).toBe(SECTION_META[section].label);
    }
  });
});
