/**
 * Which network site OWNS an artifact under `data/extracted/` — the frontend peer of
 * `watermark.sites.effective_corpus_scope` / `watermark.sites._scope` (#762/#780/#1405/#1505).
 *
 * The feed-backed facets never needed this: Python already resolves the scope at export, so a
 * peer's `records`/`documents`/`timeline` feed simply *is* its own subtree. The **legal-history**
 * facet is the exception (#1886) — it renders committed markdown straight out of `data/extracted/`
 * through an Astro content collection, with no bundle feed in between, so nothing was deciding
 * whose record it was. That is how Fort Wayne (Indiana) and Urbana came to serve all fifteen of
 * Lima's legal pages, an Ohio legislative hearing among them.
 *
 * The rule is the Python one, and it is **derived from the slug**, not enumerated (#1405): every
 * site owns two prefixes — its own `<slug>/` collection and `*\/<slug>`, the site subdirectory
 * inside a collection named for the issuing agency (`oepa/van-wert/`, `idem/fort-wayne/`). The
 * reference build owns the residue: the whole tree minus every registered peer's prefixes, so a
 * peer's artifact never lands in Lima's record either.
 *
 * What this module deliberately does NOT carry is the Python profile's `corpus_relpaths` — the
 * *exceptions* for a corpus filed by project or case name (`legal/thor-v-urbana`,
 * `permits/highland55`), which no slug rule can derive. Those live per-registry-entry Python-side
 * and have no frontend mirror, so a caller declares them at the call site instead (see
 * `LegalDoc.site`). Derive the rule; list the exceptions.
 */
import { LIMA_SLUG } from "./routes";
import { SITES } from "./sites";

/**
 * Marker for a **site-attribution nesting** term (`watermark.sites._scope._NEST`). `"*\/van-wert"`
 * matches a path whose *second* segment is `van-wert` under any collection. It is not a general
 * glob: only this one leading form is understood, and only against the second segment.
 */
const NEST = "*/";

/**
 * Whether `rel` equals or is nested under any of `prefixes` as a *path segment* — the port of
 * `watermark.sites._scope._matches_segment`.
 *
 * `"fort-wayne"` matches `fort-wayne` and `fort-wayne/…` but never `fort-wayne-foo/…`;
 * `"idem/fort-wayne"` matches `idem/fort-wayne/…` but not a bare `idem/…`; a `"*\/<slug>"` term
 * matches any `<collection>/<slug>`.
 */
export function matchesSegment(rel: string, prefixes: readonly string[]): boolean {
  const norm = rel.replace(/\\/g, "/");
  const segments = norm.split("/");
  for (const p of prefixes) {
    if (p.startsWith(NEST)) {
      if (segments.length >= 2 && segments[1] === p.slice(NEST.length)) return true;
      continue;
    }
    if (norm === p || norm.startsWith(`${p}/`)) return true;
  }
  return false;
}

/**
 * The two prefixes a site's slug DERIVES (`watermark.sites._eponymous_prefixes`): the collection
 * named for the site, and the site subdirectory inside a collection named for its source agency.
 */
export function eponymousPrefixes(slug: string): string[] {
  return [slug, `${NEST}${slug}`];
}

/**
 * The registry slug of the site whose corpus an extracted-tree `rel` belongs to.
 *
 * A peer wins on its own eponymous prefixes; everything else is the reference build's, which is
 * the `include=None` minus `_peer_scope_prefixes` half of the Python scope. `rel` is relative to
 * `data/extracted/` — the same key `LegalDoc.repo` and `PUBLISHED_LEGAL` use.
 */
export function corpusOwner(rel: string, sites: readonly { slug: string }[] = SITES): string {
  for (const site of sites) {
    if (site.slug === LIMA_SLUG) continue; // the residual owner, resolved last
    if (matchesSegment(rel, eponymousPrefixes(site.slug))) return site.slug;
  }
  return LIMA_SLUG;
}
