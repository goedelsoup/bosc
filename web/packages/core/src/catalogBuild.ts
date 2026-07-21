/**
 * The build-time catalog loader + web-only overlay (epic #1090 / #1093). Split from the pure
 * `./catalog` resolver core because this half uses `node:fs` (the bundle) and `import.meta.glob`
 * (the stories collection) — build-time only, never importable in a Worker.
 *
 * The catalog is assembled in **two tiers** (see `bosc.site.catalog_index`): the Python data tier
 * emits the feed-backed kinds as the `catalog-index` bundle feed; this module overlays the
 * **web-only** kinds (`teardown`/`doc`/`chapter`/`figure`) — teardowns, doc collections, story
 * chapters, and viz widgets the bundle can't see — so the resolver sees one merged catalog.
 */
import { activeSite, hasFeed, loadFeed } from "./bundle";
import { type Catalog, type CatalogAtom, atom, catalogFromAtoms } from "./catalog";
import { LEGAL } from "./legal";
import { NARRATIVE } from "./narrative";
import { REFERENCE } from "./reference";
import { LIMA_SLUG } from "./routes";
import { ALL_TEARDOWNS } from "./teardowns";
import { STORIES, siteSurfacesStory } from "./walk";

/** The wire shape of the `catalog-index` object feed (`bosc.site.feeds.CatalogIndex`, snake_case). */
interface CatalogIndexFeed {
  site: string;
  catalog_version: string;
  contract_version: string;
  atoms: {
    handle: string;
    kind: string;
    site: string;
    local_id: string;
    title: string;
    feed: string;
  }[];
}

/** The whole-widget viz figures grabbable in v1 (#1093 locked rough edge: figures grab as **whole
 *  widgets** keyed by builder name — per-scalar object-paths deferred). A small, extensible seed. */
const FIGURES: { localId: string; title: string }[] = [
  { localId: "dilution", title: "Effluent dilution" },
  { localId: "money-flow", title: "Money flow" },
];

/**
 * The web-only overlay (#1093): the four kinds the bundle can't see. Chapters carry their own
 * `story.site`; teardowns, doc collections, and figures are Lima editorial artifacts today (the
 * `narrative`/`legal`/`reference` collections route under Lima's network path), so they overlay
 * only onto the Lima catalog. A sibling site with its own stories still gets its chapters.
 */
export function webOnlyAtoms(site: string): CatalogAtom[] {
  const atoms: CatalogAtom[] = [];

  // chapter — the `stories` MDX collection; grabbable as `chapter:<site>:<codename>/<slug>`. Only a
  // *surfaced* (readable) story contributes atoms: a not-readable story — `hidden` (#1256) or
  // `comingSoon` (#1526), content retained — is grabbable nowhere, so it drops out of the catalog +
  // atoms. Lima's Project BOSC walk is readable, so its chapters are grabbable; Fort Wayne's Project
  // Zodiac stays `comingSoon`, so it emits no chapter atoms.
  for (const story of STORIES) {
    if (story.site !== site) continue;
    if (!siteSurfacesStory(story.site, story.codename)) continue;
    for (const ch of story.chapters) {
      atoms.push(atom("chapter", site, `${story.codename}/${ch.slug}`, ch.title, "stories"));
    }
  }

  // teardown / doc / figure — Lima-scoped editorial artifacts.
  if (site === LIMA_SLUG) {
    for (const t of ALL_TEARDOWNS) {
      // Grabbable only when it carries a `recordRel` (its stable key); curated-only teardowns
      // have no addressable anchor in v1 (mirrors the Python timeline `ref` gate).
      if (t.recordRel) atoms.push(atom("teardown", site, t.recordRel, t.title, "teardowns"));
    }
    // doc — three collections fold into one `doc` kind; a slug is unique within a collection but
    // could collide *across* them (`narrative`/`legal`/`reference`). Keep the first (narrative →
    // legal → reference order) so a later collection can't silently clobber an earlier doc when the
    // catalog collapses by handle. The `feed` label records which collection won.
    const seenDoc = new Set<string>();
    const pushDoc = (slug: string, title: string, feed: string): void => {
      const handle = `doc:${site}:${slug}`;
      if (seenDoc.has(handle)) return;
      seenDoc.add(handle);
      atoms.push(atom("doc", site, slug, title, feed));
    };
    for (const d of NARRATIVE) pushDoc(d.slug, d.title, "narrative");
    for (const d of LEGAL) pushDoc(d.slug, d.title, "legal");
    for (const d of REFERENCE) pushDoc(d.slug, d.title, "reference");
    for (const f of FIGURES) atoms.push(atom("figure", site, f.localId, f.title, "figure"));
  }

  return atoms;
}

/**
 * Assemble the merged catalog for a site: the `catalog-index` bundle feed (feed-backed atoms) plus
 * the web-only overlay. Feed-backed atoms win on a handle collision (the bundle is authoritative),
 * so they are appended last. Absent feed (a thin site) degrades to overlay-only — never throws.
 */
export function loadCatalog(site: string = activeSite()): Catalog {
  let version = "";
  let feedAtoms: CatalogAtom[] = [];
  if (hasFeed("catalog-index", site)) {
    const feed = loadFeed<CatalogIndexFeed>("catalog-index", site);
    version = feed.catalog_version;
    feedAtoms = feed.atoms.map((a) => ({
      handle: a.handle,
      kind: a.kind as CatalogAtom["kind"],
      site: a.site,
      localId: a.local_id,
      title: a.title,
      feed: a.feed,
    }));
  }
  return catalogFromAtoms(site, version, [...webOnlyAtoms(site), ...feedAtoms]);
}
