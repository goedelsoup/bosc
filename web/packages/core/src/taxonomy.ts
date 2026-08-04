/**
 * One taxonomy per noun (#1892, epic #1884 phase 8) — the declared canonical page for every
 * noun the corpus models.
 *
 * Before this declaration existed, people, concepts, and hypotheses each rendered twice
 * (`/wiki/*` vs `/network/<site>/site/*`, or vs `/research/hypotheses`) with no stated
 * canonical and no cross-reference — a reader couldn't tell which page was authoritative for
 * "who is X", which is the exact failure mode the entity graph exists to prevent. This module
 * is the single statement of where each noun's record lives; the nav model (`nav.ts`), the
 * corpus map (`/wiki/corpus`), and the hub pages read it rather than each re-deciding.
 *
 * The boundary settled here:
 *
 *  - **Network-global (the wiki):** entities, concepts, hypotheses — nouns that recur across
 *    sites and whose value is the cross-site view. One build, at the root.
 *  - **Per-site:** people — profiles curated from *this* site's record, with the wiki entity
 *    as the canonical spine and the site page as its site-specific evidence view.
 *
 * A noun may have a *projection* — a second read of the same data (the `/research/hypotheses`
 * cross-site scorecard) — but never a second record. Each projection links its canonical and
 * vice versa.
 *
 * Zero-dependency on purpose (like `routes.ts`): plain data + string helpers, so anything from
 * `astro.config.ts` to a page template can read it without a cycle.
 */

import { siteBase } from "./routes";

export type NounKind = "entity" | "concept" | "hypothesis" | "person";

export type NounScope = "network-global" | "per-site";

export interface NounTaxonomy {
  kind: NounKind;
  /** Plural label, as hubs and tocs show it. */
  label: string;
  /** The hub-door / toc anchor id for the noun's entry on its hub page. */
  anchor: string;
  scope: NounScope;
  /**
   * The canonical index route (pre-deploy-base). Root-absolute for a `network-global` noun;
   * site-relative (appended to `siteBase(slug)`) for a `per-site` one — use `canonicalIndex`.
   */
  index: string;
  /** Why the canonical is where it is — required reasoning, in the module, not a commit message. */
  note: string;
  /** A secondary read of the same data, where one exists. Never a second record of the noun. */
  projection?: { route: string; label: string };
}

export const TAXONOMY: Record<NounKind, NounTaxonomy> = {
  entity: {
    kind: "entity",
    label: "Entities",
    anchor: "entities",
    scope: "network-global",
    index: "/wiki/entities/",
    note:
      "Resolved parties recur across sites — the same operator, counsel, or shell surfaces at " +
      "more than one watershed point — so the entity graph is the network-global spine. An " +
      "individual's site-curated profile (`people`, per-site) hangs off its entity page, never " +
      "the other way around. Network-global is now true by CONSTRUCTION, not just by declaration " +
      "(#1906): the pages are minted from `networkEntities`, the union across every selectable " +
      "site, with the merge rule stated there. Until then this build rendered the reference " +
      "bundle alone — `getStaticPaths` runs outside `runWithSite` — so a party only a peer " +
      "carried had no page here and, there being deliberately no per-site entity route, none " +
      "anywhere.",
  },
  concept: {
    kind: "concept",
    label: "Concepts",
    anchor: "concepts",
    scope: "network-global",
    index: "/wiki/concepts/",
    note:
      "The glossary is the network's shared method vocabulary — 7Q10, consumptive cooling, NPDES " +
      "mean the same thing at every watershed point, and 75 of its 77 entries were byte-identical " +
      "in every site bundle. It therefore builds ONCE, here (#1892, superseding the per-site " +
      "render #1567 chose): a record's `[[wiki links]]` resolve to the wiki, and the retired " +
      "`/site/concepts/` routes 301 to it. The per-site `concepts` feed survives for term " +
      "MATCHING only — a peer still never linkifies a term tagged for another site.",
  },
  hypothesis: {
    kind: "hypothesis",
    label: "Hypotheses",
    anchor: "hypotheses",
    scope: "network-global",
    index: "/wiki/hypotheses/",
    note:
      "A boom-origin reading is one claim held against the whole network, so its record is the " +
      "network-global wiki node — definition, evidence matrix, and the concepts and entities it " +
      "bears on. The scorecard is the same data read the other way (per lens, across every " +
      "site), a projection, not a second record; the two link each other.",
    projection: { route: "/research/hypotheses", label: "Cross-site scorecard" },
  },
  person: {
    kind: "person",
    label: "People",
    anchor: "people",
    scope: "per-site",
    index: "/site/people/",
    note:
      "A profile is curated from ONE site's record — roles, affiliations, and sources as they " +
      "appear in that corpus — so the site page is the canonical view and there is deliberately " +
      "no `/wiki/people/` route. The wiki entity is the canonical spine: the profile links its " +
      "entity, the entity page backlinks the profile.",
  },
};

/** The network-global nouns, in hub order — the wiki hub's doors and the wiki toc read this. */
export const NETWORK_NOUNS: NounTaxonomy[] = Object.values(TAXONOMY).filter(
  (n) => n.scope === "network-global",
);

/**
 * A noun's canonical index route. A `per-site` noun needs the site whose record it reads
 * (`canonicalIndex("person", "fort-wayne")` → `/network/fort-wayne/site/people/`); a
 * `network-global` one ignores `slug` — there is exactly one build.
 */
export function canonicalIndex(kind: NounKind, slug?: string): string {
  const noun = TAXONOMY[kind];
  if (noun.scope === "per-site") {
    if (!slug) throw new Error(`canonicalIndex("${kind}") needs a site slug — the noun is per-site`);
    return `${siteBase(slug)}${noun.index}`;
  }
  return noun.index;
}
