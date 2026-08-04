/**
 * Pure rendering for the Ask portal answer (#212 + #213): turn the model's markdown
 * answer + its structured citations into safe HTML, resolving every `[n]` marker to a
 * deep link into the bundle so a reader can verify each claim.
 *
 * No DOM, no dependencies — the client (`scripts/ask.ts`) owns fetch + state and injects
 * this HTML. Everything model- or data-derived is HTML-escaped here; the only markup
 * introduced is ours. Markers the model emits that don't resolve to a returned citation
 * are **flagged, not silently dropped** (the whole point of grounding an evidence corpus).
 */

import { isRoutableDoc } from "./docRouting";
import { docPermalinkForRel } from "./documentId";
import { escapeHtml } from "./format";

/** One source the answer cited — mirrors `AskCitation` in functions/api/_lib/ask.ts. */
export interface AskCitation {
  marker: number;
  id: string;
  feed: string;
  title: string;
  url: string;
  source?: string | null;
  /** The `data/documents` rel of the source document, when the unit joined to one — see
   * `AskUnit.doc_rel`. The only field that reliably names a document; `source` does not. */
  doc_rel?: string | null;
  page?: number | null;
  source_kind?: string | null;
  verified?: boolean;
}

/** Pre-answer status: how many records the answer is grounded in (#331). */
export function searchingHint(n: number): string {
  return `Searching ${n} record${n === 1 ? "" : "s"}…`;
}

/** Prefix a root-absolute bundle path with the site base (mirrors lib/site withBase). */
export function withBasePath(base: string, path: string): string {
  const left = base.endsWith("/") ? base.slice(0, -1) : base;
  const right = path.startsWith("/") ? path : `/${path}`;
  return `${left}${right}` || "/";
}

/**
 * The `/network/<id>` root of a site-rooted bundle URL, or null when the URL is network-global.
 *
 * A unit's `url` is stamped at index-build time and is the only thing a citation carries that
 * knows which site it belongs to — the wiki's entity and concept units are rooted at `/wiki/`
 * instead, and have no site to speak of.
 */
function siteRootOf(url: string): string | null {
  return /^(\/network\/[^/]+)(?=\/|$)/.exec(url)?.[1] ?? null;
}

/**
 * The most precise deep link for a citation (#328): a citation that joined to a source document
 * goes to that document's permalink so the reader can verify against the source bytes; otherwise
 * it falls back to the page the unit itself lives on (`c.url`).
 *
 * The join key is **`doc_rel`**, not `source` (#1890). This used to test `source` for a leading
 * `data/documents/` and strip it — a prefix no unit's `source` has ever carried, because `source`
 * is as often the extracted-YAML artifact the claim was read from. Measured across all 26 committed
 * bundles: 2,587 units, **zero** matches. So the deep link had been inert since it was written, and
 * every citation silently resolved to the fallback. `doc_rel` is the field that exists for exactly
 * this — set from a record's `source_doc_rel` (the #276 join), and already the join the MCP
 * `search_corpus` tool returns as `document_id`. It matches 106 units, 52 of them in Lima's, which
 * is the bundle the deployed `/ask-index.json` is built from.
 *
 * Two conditions guard the link, because the permalink route is narrower than the corpus:
 *
 *  - The site root comes from `c.url`. `docPermalink` is site-relative by contract, and the one
 *    route that serves it is `/network/<site>/doc/<id>/`; prefixing it with the *deploy* base (`/`
 *    in every environment — `BASE_PATH` is unset) is what the old code did, and would have 404'd
 *    had it ever fired. A network-global unit has no site, so it keeps its own page.
 *  - `isRoutableDoc` — the same predicate `network/[site]/doc/[id].astro` builds from. 54 of Lima's
 *    catalogued files are OS exhaust that is listed and fetchable but deliberately not routed, and
 *    a citation is not a reason to promise one a page.
 */
export function citationHref(c: AskCitation, base: string): string {
  const rel = c.doc_rel;
  const site = rel ? siteRootOf(c.url) : null;
  if (rel && site && isRoutableDoc({ rel, name: rel.split("/").pop() ?? "" })) {
    return withBasePath(base, `${site}${docPermalinkForRel(rel)}`);
  }
  return withBasePath(base, c.url);
}

/** The evidence badge for a source — record/connector-grounded vs. inferred/derived. */
export function badgeKind(c: AskCitation): "verified" | "inference" | "open" {
  if (c.verified) return "verified";
  return c.source_kind === "derived" || c.source_kind === "assumption" ? "open" : "inference";
}

/** Light, safe markdown: paragraphs, `- ` bullet lists, `**bold**`, and `` `code` ``. */
function renderMarkdown(escaped: string): string {
  const blocks = escaped.split(/\n\s*\n/);
  const inline = (s: string): string =>
    s.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  return blocks
    .map((block) => {
      const lines = block.split("\n").filter((l) => l.trim().length > 0);
      if (lines.length > 0 && lines.every((l) => /^\s*[-*]\s+/.test(l))) {
        const items = lines.map((l) => `<li>${inline(l.replace(/^\s*[-*]\s+/, ""))}</li>`).join("");
        return `<ul>${items}</ul>`;
      }
      return `<p>${inline(lines.join("<br>"))}</p>`;
    })
    .join("");
}

/**
 * Render the answer body: markdown → HTML, with each `[n]` marker turned into a
 * superscript link to the cited source's page. Unresolved markers render flagged.
 */
export function renderAnswer(answer: string, citations: AskCitation[], base = "/"): string {
  const byMarker = new Map(citations.map((c) => [c.marker, c]));
  const html = renderMarkdown(escapeHtml(answer));
  return html.replace(/\[(\d+)\]/g, (_m, d: string) => {
    const marker = Number(d);
    const c = byMarker.get(marker);
    if (!c) {
      return `<sup class="ask-cite ask-cite--unresolved" title="citation not resolved to a source">[${marker}]</sup>`;
    }
    const href = escapeHtml(citationHref(c, base));
    const title = escapeHtml(
      `${c.title}${c.source ? ` — ${c.source}` : ""}${c.page != null ? ` p.${c.page}` : ""}`,
    );
    return `<sup class="ask-cite"><a href="${href}" title="${title}">[${marker}]</a></sup>`;
  });
}

/** Render the "Sources used" list under the answer (empty string when there are none). */
export function renderSources(citations: AskCitation[], base = "/"): string {
  if (citations.length === 0) return "";
  const items = citations
    .map((c) => {
      const kind = badgeKind(c);
      const href = escapeHtml(citationHref(c, base));
      const loc = [c.source, c.page != null ? `p.${c.page}` : null].filter(Boolean).join(" ");
      return (
        `<li class="ask-source">` +
        `<span class="ask-source-marker">[${c.marker}]</span>` +
        `<span class="evidence evidence-${kind}" data-kind="${kind}"><span class="evidence-dot" aria-hidden="true"></span>[${kind}]</span>` +
        `<a class="ask-source-link" href="${href}">${escapeHtml(c.title)}</a>` +
        (loc ? `<code class="ask-source-loc">${escapeHtml(loc)}</code>` : "") +
        `</li>`
      );
    })
    .join("");
  return `<p class="ask-sources-title">Sources used</p><ul class="ask-sources">${items}</ul>`;
}
