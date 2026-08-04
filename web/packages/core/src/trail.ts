/**
 * Positional wayfinding — the route → breadcrumb-trail resolver (#1889, epic #1884 phase 5).
 *
 * The site's whole retrieval story drops readers into the *middle* of the tree: search, `/ask`,
 * the MCP server, wiki backlinks, and (since #1885) every citation in the impact study. Deep
 * landing is the normal case here, not the exception — yet the chrome was built for someone who
 * walked down from the home page. Before this module three of ninety-nine page templates rendered
 * a trail, each hand-assembling its own; everywhere else the only "up" affordance was the browser
 * back button, which fails outright for anyone arriving from outside.
 *
 * So the trail is **derived from the route**, not passed per page: `Base.astro` calls `trailFor`
 * with `Astro.url.pathname` and every template gets one for free. What a page contributes is only
 * what the URL cannot know — a record's title, a document container's as-received name — through
 * the three `TrailOptions` below.
 *
 * ## The model is declared, not inferred
 *
 * {@link ROOT} is an explicit tree over URL segments rather than a slug-humanizer, because a
 * segment's label is a matter of editorial voice, not of casing: `site` is "The record",
 * `leads` is "Open leads", `rsei` is "RSEI / toxics". A humanizer would render those "Site",
 * "Leads", "Rsei". The tree is also what makes the acceptance criterion checkable —
 * `trailCoverage.test.ts` walks `src/pages/**` and fails if any route template has no declared
 * trail, so a new page cannot ship without one.
 *
 * ## Purity
 *
 * DOM-free and `import.meta.env`-free. Hrefs come back **pre-deploy-base** (`/network/…`), the
 * same convention as `nav.ts`; the template applies `withBase`. The one impure-looking import is
 * `currentSiteForPath`, which resolves `/network/american-sugar-creek-allen-co` to "Lima, OH"
 * from the registry — the issue's requirement that a deep Lima page and a deep Fort Wayne page be
 * distinguishable at a glance.
 */

import { currentSiteForPath } from "./sites";

/** One step in a trail. The last crumb — the current page — carries no `href`. */
export interface Crumb {
  label: string;
  /** Root-absolute, pre-deploy-base. Omitted on the current page and on non-page ancestors. */
  href?: string;
}

/** The wildcard child key: a dynamic (`[param]`) segment. */
const PARAM = "*";

interface TrailNode {
  /**
   * Crumb text. A function receives the concrete segment, for nodes whose label is data
   * (a site's place name) rather than editorial.
   */
  label: string | ((segment: string) => string);
  /** This node addresses no page — its crumb renders as plain text rather than a link. */
  unlinked?: boolean;
  /** The node's canonical href ends in `/` (a directory-style landing, e.g. `/site/records/`). */
  slash?: boolean;
  /**
   * Contributes a crumb only when it IS the current page, never as an ancestor.
   *
   * Two shapes need this. `/network` is a real page (#1888's site index) but sits between
   * "Directory" and a site, and to a reader "Directory › All sites › Lima, OH" names the same
   * thing twice. `/network/<site>/doc` and `/network/<site>/stories` are pure namespace segments
   * with no landing at all, and their child already carries the name that matters (the document,
   * the story).
   */
  leafOnly?: boolean;
  /**
   * The leaf label comes from the page's `title` (via {@link TrailOptions.leaf}) rather than from
   * this table. Set on dynamic leaves whose name is data — a record, a person, a place.
   */
  fromTitle?: boolean;
  /** Consume every remaining segment into this one crumb (Astro's `[...rest]` routes). */
  rest?: boolean;
  children?: Record<string, TrailNode>;
}

/** Sentence-case a slug for a segment the model doesn't name: `page-2` → "Page 2". */
function humanize(segment: string): string {
  const words = segment.replace(/[-_]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** The record facets under `<site>/site/` — leaf pages of The Record, each an index + detail pair. */
const RECORD_CHILDREN: Record<string, TrailNode> = {
  documents: {
    label: "Documents",
    slash: true,
    children: {
      // collection → container → page-N. Below the container, nesting stops being navigation and
      // becomes provenance (see `docBrowse.ts`), so the tree stops here too.
      [PARAM]: {
        label: humanize,
        slash: true,
        children: {
          [PARAM]: { label: humanize, slash: true, children: { [PARAM]: { label: humanize } } },
        },
      },
    },
  },
  exhibits: { label: "Exhibits" },
  legal: { label: "Legal history", slash: true, children: { [PARAM]: { label: humanize, fromTitle: true } } },
  people: { label: "People", slash: true, children: { [PARAM]: { label: humanize, fromTitle: true } } },
  places: {
    label: "Places & parcels",
    slash: true,
    children: { [PARAM]: { label: humanize, fromTitle: true } },
  },
  records: {
    label: "Records",
    slash: true,
    children: {
      "how-to-read": { label: "How to read a record" },
      // The group segment is a feed value (`permits`, `oepa`); the page names it with
      // `groupLabel()` through `TrailOptions.labels`.
      [PARAM]: {
        label: humanize,
        slash: true,
        children: { [PARAM]: { label: humanize, fromTitle: true } },
      },
    },
  },
  reference: {
    label: "Reference data",
    slash: true,
    children: { [PARAM]: { label: humanize, fromTitle: true } },
  },
};

/** Everything under a site root, `/network/<id>/`. */
const SITE_CHILDREN: Record<string, TrailNode> = {
  contacts: { label: "Contacts" },
  // A document's permalink is deliberately flat and collection-free (#1887) — `doc` is a
  // namespace, not a landing. Where the file actually sits is spliced in by the page itself
  // (`TrailOptions.insert`), since only the feed knows its collection and container.
  doc: { label: "Documents", leafOnly: true, children: { [PARAM]: { label: humanize, fromTitle: true } } },
  economy: {
    label: "The economy",
    slash: true,
    children: {
      // Re-homed from `/environment/` (#1893): a labor baseline filed under the environment was
      // the one leaf whose route prefix contradicted the section its own page declares.
      "economics-baseline": { label: "Localized labor baseline" },
      grid: { label: "The grid backdrop" },
    },
  },
  environment: {
    label: "The environment",
    slash: true,
    children: {
      air: { label: "Air dispersion" },
      enclave: { label: "The federal enclave" },
      flow: { label: "Water flow" },
      groundwater: { label: "Groundwater" },
      hydrology: { label: "Hydrology" },
      imagery: { label: "Imagery" },
      map: { label: "Watershed map" },
      rsei: { label: "RSEI / toxics" },
      seasonal: { label: "Seasonal withdrawal" },
      thermal: { label: "Thermal / §316(a)" },
    },
  },
  leads: { label: "Open leads" },
  reports: {
    label: "Reports",
    slash: true,
    children: {
      "defense-nexus": { label: "The defense nexus" },
      "end-use-and-workloads": { label: "End use & workloads" },
      "opc-scenario": { label: "OPC scenario explorer" },
      "public-balance-sheet": { label: "The public balance sheet" },
      "the-economic-ledger": { label: "The economic ledger" },
      "the-load-and-the-grid": { label: "The load and the grid" },
      "toxics-and-the-corridor": { label: "Toxics and the corridor" },
    },
  },
  site: { label: "The record", slash: true, children: RECORD_CHILDREN },
  stories: {
    label: "The story",
    leafOnly: true,
    children: {
      compose: { label: "Compose a story" },
      "grab-demo": { label: "Grab a fact" },
      mine: { label: "Your stories" },
      read: { label: "Read" },
      // <codename>/ is the story home; its label is the story title, which the page supplies.
      [PARAM]: {
        label: humanize,
        slash: true,
        fromTitle: true,
        children: {
          contents: { label: "Contents" },
          [PARAM]: { label: humanize, fromTitle: true },
        },
      },
    },
  },
  study: {
    label: "The impact study",
    slash: true,
    children: { [PARAM]: { label: humanize, fromTitle: true } },
  },
  submit: { label: "Submit a tip or correction" },
  timeline: { label: "Timeline" },
};

/**
 * The root of the URL space — `/`, the network directory.
 *
 * Its own crumb opens every trail (the reader's way back out of any depth); the page at `/`
 * itself gets no trail, since a trail to the root is just the root.
 */
const ROOT: TrailNode = {
  label: "Directory",
  children: {
    "404": { label: "Not found" },
    about: {
      label: "About",
      children: {
        catalog: { label: "Data catalog" },
        contributing: { label: "Contributing" },
        data: { label: "The data tier" },
        mission: { label: "Mission" },
        sustainability: { label: "Sustainability" },
      },
    },
    "about-me": { label: "My research" },
    account: {
      label: "Account",
      slash: true,
      children: {
        admin: { label: "User management" },
        callback: { label: "Signing in" },
        login: { label: "Sign in" },
        logout: { label: "Signing out" },
        unsubscribe: { label: "Unsubscribe" },
      },
    },
    ask: { label: "Ask the corpus" },
    basin: { label: "The Maumee basin" },
    // `[...slug]` — a narrative doc's slug can itself be nested (`legal/mandamus-analysis`), and
    // the intermediate directory has no landing, so the whole remainder is one crumb.
    docs: {
      label: "Docs",
      slash: true,
      children: { [PARAM]: { label: humanize, fromTitle: true, rest: true } },
    },
    "locked-preview": { label: "Site Locked — preview" },
    methodology: { label: "Methodology", children: { [PARAM]: { label: humanize, fromTitle: true } } },
    network: {
      label: "All sites",
      leafOnly: true,
      children: {
        connect: { label: "Connect" },
        // A watershed-point site. The label is its registered place name, so a deep Lima page and
        // a deep Fort Wayne page are distinguishable at a glance — the issue's second criterion.
        [PARAM]: { label: siteLabel, children: SITE_CHILDREN },
      },
    },
    "pre-launch": { label: "Pre-launch" },
    privacy: { label: "Privacy" },
    research: { label: "Research", children: { hypotheses: { label: "The three hypotheses" } } },
    search: { label: "Search" },
    showcase: {
      label: "Component previews",
      unlinked: true,
      children: {
        charts: { label: "Chart set" },
        icons: { label: "Icon set" },
        teardown: { label: "Record Teardown" },
      },
    },
    submit: { label: "Submit a tip or correction" },
    wiki: {
      label: "Wiki",
      slash: true,
      children: {
        candidates: { label: "Cloud-consumer candidates" },
        concepts: {
          label: "Concepts",
          slash: true,
          children: { [PARAM]: { label: humanize, fromTitle: true } },
        },
        corpus: { label: "Corpus map" },
        "defense-contractors": { label: "Defense contractors" },
        entities: {
          label: "Entities",
          slash: true,
          children: { [PARAM]: { label: humanize, fromTitle: true } },
        },
        graph: { label: "Entity graph", children: { exports: { label: "Graph exports" } } },
        hypotheses: {
          label: "Hypotheses",
          slash: true,
          children: { [PARAM]: { label: humanize, fromTitle: true } },
        },
        lei: { label: "Entity LEIs" },
        "open-questions": { label: "Open questions" },
      },
    },
  },
};

/** A site segment's crumb: its registered place, or the raw id for a slug not in the registry. */
function siteLabel(segment: string): string {
  return currentSiteForPath(`/network/${segment}`)?.place ?? humanize(segment);
}

export interface TrailOptions {
  /**
   * Label for the current page's crumb, on a route whose leaf is data (`fromTitle`). Defaults to
   * the page title — which is right wherever the title is the thing's name, and wrong wherever
   * it's decorated ("Water — The impact study"), so those pages pass this explicitly.
   */
  leaf?: string;
  /**
   * Labels for segments the route model can't name — a record group, a document container's
   * as-received directory name. Keyed by the **segment value**, so a page supplies
   * `{ [record.group]: groupLabel(record.group) }` without counting positions.
   */
  labels?: Record<string, string>;
  /**
   * Ancestors the URL doesn't contain, spliced in immediately before the leaf. One consumer:
   * the document permalink, whose flat `/doc/<handle>/` address deliberately drops the
   * collection and container the reader still needs to climb back to.
   */
  insert?: readonly Crumb[];
  /** Astro's deploy base (`import.meta.env.BASE_URL`), stripped off `pathname` before resolving. */
  base?: string;
}

/** Strip the deploy base and any trailing slash: `/bosc/wiki/` → `/wiki`. */
function normalize(pathname: string, base: string): string {
  let p = pathname;
  if (base && base !== "/" && p.startsWith(base)) p = p.slice(base.length);
  if (!p.startsWith("/")) p = `/${p}`;
  return p.replace(/\/+$/, "") || "/";
}

/**
 * The ancestor trail for a route, ending in the current page (which carries no `href`).
 *
 * Returns `[]` for the root itself — the one page with nothing above it. Every other route
 * yields at least `Directory › <here>`. An undeclared segment degrades to a humanized,
 * unlinked crumb rather than throwing: a missing trail is a content bug, caught by
 * `trailCoverage.test.ts` at build time, and must never be a 500 at read time.
 */
export function trailFor(pathname: string, opts: TrailOptions = {}): Crumb[] {
  const path = normalize(pathname, opts.base ?? "");
  if (path === "/") return [];
  const segments = path.slice(1).split("/");

  const crumbs: Crumb[] = [{ label: ROOT.label as string, href: "/" }];
  let node: TrailNode = ROOT;
  let href = "";

  for (let i = 0; i < segments.length; i++) {
    const segment = segments[i];
    const child: TrailNode | undefined = node.children?.[segment] ?? node.children?.[PARAM];
    const isLeaf = child?.rest === true || i === segments.length - 1;
    href = child?.rest === true ? `${href}/${segments.slice(i).join("/")}` : `${href}/${segment}`;

    if (!child) {
      // Undeclared: name it as best we can and stop linking — an href we can't vouch for is
      // worse than plain text, since a broken crumb teaches a reader the trail can't be trusted.
      crumbs.push({ label: opts.labels?.[segment] ?? humanize(segment) });
      node = { label: humanize(segment) };
      continue;
    }
    node = child;

    if (child.leafOnly && !isLeaf) continue;

    const label =
      opts.labels?.[segment] ??
      (isLeaf && child.fromTitle && opts.leaf ? opts.leaf : undefined) ??
      (typeof child.label === "function" ? child.label(segment) : child.label);

    if (isLeaf) {
      if (opts.insert) crumbs.push(...opts.insert);
      crumbs.push({ label });
      break;
    }
    crumbs.push(child.unlinked ? { label } : { label, href: child.slash ? `${href}/` : href });
  }

  return crumbs;
}

/**
 * Whether a route declares a trail at all — the predicate behind the acceptance criterion.
 *
 * Takes a route **pattern** (`[param]` segments written as `*`), so `trailCoverage.test.ts` can
 * ask it of every file under `src/pages/**` without inventing concrete param values.
 */
export function trailDeclared(pattern: string): boolean {
  const path = normalize(pattern, "");
  if (path === "/") return true; // the root: no trail by design, and that IS its declaration
  let node: TrailNode = ROOT;
  for (const segment of path.slice(1).split("/")) {
    const child = node.children?.[segment] ?? node.children?.[PARAM];
    if (!child) return false;
    if (child.rest) return true;
    node = child;
  }
  return true;
}
