/**
 * Rehype plugin (issue #69): rewrite the in-repo links inside the migrated
 * `docs/` narrative so they resolve in the new Astro IA — WITHOUT editing the
 * source (the docs are also the legacy Python SSG's input, where the original
 * links still work). Runs only on files under `docs/`.
 *
 * The docs author links against the legacy `web/docs/` layout, so resolving a
 * link relative to the doc's `docs/` location yields the right repo-root path.
 * From there:
 *   1. a migrated narrative doc  → its `/docs/<slug>` route
 *   2. a known legacy generated page (LINK_MAP) → its new-IA route
 *   3. any other in-repo file (data/, docs/, …) → the GitHub source (so corpus
 *      and not-yet-migrated links resolve to the canonical artifact, not a 404)
 *   4. anything else → left untouched
 */
import { posix } from "node:path";
import { visit } from "unist-util-visit";
import type { Element, Root } from "hast";
import type { VFile } from "vfile";
import { LINK_MAP, MIGRATED, slugForRepoPath } from "./narrative";

export interface DocLinkOptions {
  /** Astro `base` to prefix onto internal routes (default ""). */
  base?: string;
  /** Base for the GitHub-source fallback. */
  repoBase?: string;
}

const SKIP = /^(https?:|mailto:|tel:|#|\/|data:)/;
const REPO_DIR = /^(data|docs|src|notebooks|spikes|\.claude|\.github)\//;

function splitHash(href: string): [string, string] {
  const i = href.indexOf("#");
  return i < 0 ? [href, ""] : [href.slice(0, i), href.slice(i)];
}

export default function rehypeDocLinks(options: DocLinkOptions = {}) {
  const base = options.base ?? "";
  const repoBase = options.repoBase ?? "https://github.com/goedelsoup/bosc/blob/main/";

  return (tree: Root, file: VFile): void => {
    const path = String(file.path ?? "").replace(/\\/g, "/");
    const m = path.match(/(?:^|\/)docs\/(.+)$/);
    if (!m) return; // only the narrative docs under docs/
    const docDir = posix.dirname(`docs/${m[1]}`);

    visit(tree, "element", (node: Element) => {
      if (node.tagName !== "a") return;
      const href = node.properties?.href;
      if (typeof href !== "string" || SKIP.test(href)) return;

      const [rel, hash] = splitHash(href);
      if (!rel) return;
      const resolved = posix.normalize(posix.join(docDir, rel));
      if (resolved.startsWith("..")) return; // escaped the repo root — leave as-is
      const basename = posix.basename(resolved);

      // Map values are site-relative unless absolute (passed through verbatim).
      const toRoute = (v: string): string => (/^https?:/.test(v) ? v : `${base}${v}`);

      let target: string | null = null;
      if (MIGRATED.has(resolved)) {
        // 1. a migrated narrative doc → its /docs/<slug> route
        target = `${base}/docs/${slugForRepoPath(resolved)}`;
      } else if (LINK_MAP[resolved]) {
        // 2. a correctly-pathed legacy generated page → its IA route
        target = toRoute(LINK_MAP[resolved]);
      } else if (!resolved.startsWith("data/") && LINK_MAP[basename]) {
        // 3. a wrong-depth generated-page link (e.g. bare `entities.md`) → IA,
        //    by basename — guarded so a same-named corpus file can't collide.
        target = toRoute(LINK_MAP[basename]);
      } else if (REPO_DIR.test(resolved)) {
        // 4. any other in-repo file (corpus, dev docs) → the GitHub source
        target = `${repoBase}${resolved}`;
      }
      if (target !== null) node.properties.href = `${target}${hash}`;
    });
  };
}
