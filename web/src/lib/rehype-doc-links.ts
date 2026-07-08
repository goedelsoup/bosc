/**
 * Rehype plugin (issue #69, generalized in #104): rewrite the in-repo links inside
 * the markdown the Astro site renders AS-IS — the migrated `docs/` narrative, the
 * `data/reference/` READMEs, and the `data/extracted/` legal docs — so they resolve
 * in the new IA WITHOUT editing the source (the docs source stays canonical, with the
 * original links intact). Runs on files under those roots.
 *
 * A link is resolved relative to its file's repo location, then rewritten:
 *   1. a migrated narrative doc            → its `/docs/<slug>` route
 *   2. a published reference README        → its `/site/reference/<slug>` route
 *   3. a known legacy generated page (LINK_MAP) → its new-IA route
 *   4. any other in-repo file (data/, …)   → the GitHub source (so corpus and
 *      not-yet-migrated links resolve to the canonical artifact, not a 404)
 *   5. anything else → left untouched
 */
import { posix } from "node:path";
import { visit } from "unist-util-visit";
import type { Element, Root } from "hast";
import type { VFile } from "vfile";
import { legalSlugForRepoPath, PUBLISHED_LEGAL } from "./legal";
import { LINK_MAP, MIGRATED, slugForRepoPath } from "./narrative";
import { PUBLISHED_REFERENCE, refSlugForRepoPath } from "./reference";

export interface DocLinkOptions {
  /** Astro `base` to prefix onto internal routes (default ""). */
  base?: string;
  /** Base for the GitHub-source fallback. */
  repoBase?: string;
}

const SKIP = /^(https?:|mailto:|tel:|#|\/|data:)/;
const REPO_DIR = /^(data|docs|src|spikes|\.claude|\.github)\//;
// Network-global routes live at the site root, shared across every watershed site, so they
// are NOT prefixed with the Lima base (#307 follow-up: about/about-me/wiki/ask/privacy are global).
// `docs` joined them at the network-global-host move (#1304): the long-form prose is one root build.
const GLOBAL_ROUTE = /^\/(about|about-me|wiki|ask|privacy|docs)(\/|#|$)/;

function splitHash(href: string): [string, string] {
  const i = href.indexOf("#");
  return i < 0 ? [href, ""] : [href.slice(0, i), href.slice(i)];
}

export default function rehypeDocLinks(options: DocLinkOptions = {}) {
  const base = options.base ?? "";
  const repoBase =
    options.repoBase ?? "https://github.com/watermark-directory/the-watermark-directory/blob/main/";

  return (tree: Root, file: VFile): void => {
    const path = String(file.path ?? "").replace(/\\/g, "/");
    // The repo-root path of this file, for any of the AS-IS-rendered roots.
    const m = path.match(/(?:^|\/)((?:docs|data\/reference|data\/extracted)\/.+)$/);
    if (!m) return;
    const docDir = posix.dirname(m[1]);

    visit(tree, "element", (node: Element) => {
      if (node.tagName !== "a") return;
      const href = node.properties?.href;
      if (typeof href !== "string" || SKIP.test(href)) return;

      const [rel, hash] = splitHash(href);
      if (!rel) return;
      const resolved = posix.normalize(posix.join(docDir, rel));
      if (resolved.startsWith("..")) return; // escaped the repo root — leave as-is
      const basename = posix.basename(resolved);

      // Map values are Lima-relative (base-prefixed) unless absolute or network-global,
      // which pass through verbatim.
      const toRoute = (v: string): string => (/^https?:/.test(v) || GLOBAL_ROUTE.test(v) ? v : `${base}${v}`);

      let target: string | null = null;
      if (MIGRATED.has(resolved)) {
        // 1. a migrated narrative doc → its network-global /docs/<slug> route (#1304): the docs
        //    build moved to a single root, so it is NOT prefixed with the Lima site base.
        target = `/docs/${slugForRepoPath(resolved)}`;
      } else if (PUBLISHED_REFERENCE.has(resolved)) {
        // 2. a published reference README → its /site/reference/<slug> route
        target = `${base}/site/reference/${refSlugForRepoPath(resolved)}`;
      } else if (PUBLISHED_LEGAL.has(resolved)) {
        // 2b. a published legal-history doc → its /site/legal/<slug> route
        target = `${base}/site/legal/${legalSlugForRepoPath(resolved)}`;
      } else if (LINK_MAP[resolved]) {
        // 3. a correctly-pathed legacy generated page → its IA route
        target = toRoute(LINK_MAP[resolved]);
      } else if (!resolved.startsWith("data/") && LINK_MAP[basename]) {
        // 4. a wrong-depth generated-page link (e.g. bare `entities.md`) → IA,
        //    by basename — guarded so a same-named corpus file can't collide.
        target = toRoute(LINK_MAP[basename]);
      } else if (REPO_DIR.test(resolved)) {
        // 5. any other in-repo file (corpus, dev docs) → the GitHub source
        target = `${repoBase}${resolved}`;
      }
      if (target !== null) node.properties.href = `${target}${hash}`;
    });
  };
}
