/**
 * Wiki cross-linking (issue #68): resolve inline `[[wiki links]]` and compute
 * backlinks across the concepts, entities, and people feeds.
 *
 * A `[[Target]]` in a concept/profile body resolves — by normalized title, key,
 * slug, or alias — to the page for that concept, entity, or person. Unresolved
 * links render as a dotted "missing" span (a TODO marker), never a dead anchor.
 */
import { activeSite, hasFeed, loadFeed } from "./bundle";
import { slugify, type ConceptItem, type EntityNode, type OpenQuestionItem, type PersonItem } from "./feeds";
import { escapeHtml } from "./format";
import { withBase, withSite } from "./site";

export interface WikiTarget {
  url: string;
  label: string;
  kind: "concept" | "entity" | "person";
}

export interface WikiIndexOptions {
  /**
   * Resolve concept links to the **active site's own** glossary
   * (`/network/<id>/site/concepts/<slug>/`) instead of the network-global
   * `/wiki/concepts/<slug>/` (#1567). Set it on per-site pages so a `[[term]]` in a
   * concept/person/place body stays inside that site's build and points at the same
   * scoped concept feed the page renders. People are always site-scoped; entities stay
   * network-global (the entity graph is a network-global host) in both modes.
   */
  scoped?: boolean;
}

/** Normalize any label/key/slug to a comparable token. */
export function norm(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/**
 * The concept page URL for a slug, network-global or scoped to the active site.
 * Both feed off the same per-site `concepts` feed; only the page root differs.
 */
function conceptHref(slug: string, scoped: boolean): string {
  return scoped ? withSite(`/site/concepts/${slug}/`) : `${withBase("/wiki/concepts/")}${slug}/`;
}

// Keyed by `${activeSite()}::${scoped}` — a single module-level Map that isn't
// site-aware silently serves the first site's index to every other site in a
// multi-site build (#1567), bleeding e.g. Lima's concepts into a peer's pages.
const cache = new Map<string, Map<string, WikiTarget>>();

/** The resolution index: normalized name/alias/slug → its page, for the active site. */
export function wikiIndex(options: WikiIndexOptions = {}): Map<string, WikiTarget> {
  const scoped = options.scoped ?? false;
  const key = `${activeSite()}::${scoped ? "site" : "global"}`;
  const hit = cache.get(key);
  if (hit) return hit;

  const index = new Map<string, WikiTarget>();
  const add = (names: (string | null | undefined)[], target: WikiTarget): void => {
    for (const n of names) {
      const k = n ? norm(n) : "";
      if (k && !index.has(k)) index.set(k, target);
    }
  };

  if (hasFeed("concepts")) {
    for (const c of loadFeed<ConceptItem[]>("concepts")) {
      add([c.slug, c.title, ...c.aliases], {
        url: conceptHref(c.slug, scoped),
        label: c.title,
        kind: "concept",
      });
    }
  }
  if (hasFeed("entities")) {
    for (const e of loadFeed<EntityNode[]>("entities")) {
      add([e.key, e.display, ...e.variants], {
        url: `${withBase("/wiki/entities/")}${slugify(e.key)}/`,
        label: e.display,
        kind: "entity",
      });
    }
  }
  if (hasFeed("people")) {
    for (const p of loadFeed<PersonItem[]>("people")) {
      add([p.slug, p.name, ...p.aliases], {
        url: `${withSite("/site/people/")}${p.slug}/`,
        label: p.name,
        kind: "person",
      });
    }
  }
  cache.set(key, index);
  return index;
}

/**
 * Inline markdown on an already-HTML-escaped string: code spans, `[[wiki links]]`,
 * `[text](url)` links, then `**bold**` and `*italic*`. Code spans are resolved first
 * so emphasis markers inside them are left alone; wiki links before markdown links so
 * `[[x]]` isn't mistaken for a `[x](y)`. The order is load-bearing — don't reshuffle.
 */
function inlineMd(escaped: string, index: Map<string, WikiTarget>): string {
  let h = escaped.replace(/`([^`]+)`/g, "<code>$1</code>");
  h = h.replace(/\[\[([^\]]+)\]\]/g, (_m, inner: string) => {
    const t = index.get(norm(inner));
    return t
      ? `<a href="${t.url}">${inner}</a>`
      : `<span class="wikilink-missing" title="unresolved wiki link">${inner}</span>`;
  });
  h = h.replace(
    /\[([^\]]+)\]\(([^)\s]+)\)/g,
    (_m, text: string, url: string) => `<a href="${url}">${text}</a>`,
  );
  h = h.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  return h;
}

/**
 * Render a markdown-ish body to a block of HTML — `##`–`######` headings, `- `/`* `
 * bullet lists (soft-wrapped items folded into one `<li>`), and paragraphs (soft wraps
 * collapsed to spaces) — with inline markdown via `inlineMd`. Blocks are split on blank
 * lines. Returns one HTML string for `set:html` (no per-block `<p>` wrapping — headings
 * and lists are block-level). Full markdown/MDX rendering is still #69; this covers the
 * constructs the corpus bodies actually use.
 */
export function renderBody(body: string, index = wikiIndex()): string {
  const out: string[] = [];
  for (const block of body.split(/\n\s*\n/)) {
    const lines = block.replace(/\s+$/, "").split("\n");
    if (!lines.some((l) => l.trim())) continue;

    // Heading — `##`+ on the first line; any remaining lines fall through as a paragraph.
    const head = lines[0].match(/^\s*(#{2,6})\s+(.*)$/);
    if (head) {
      const level = Math.min(head[1].length, 4);
      out.push(`<h${level}>${inlineMd(escapeHtml(head[2].trim()), index)}</h${level}>`);
      const rest = lines
        .slice(1)
        .map((l) => l.trim())
        .filter(Boolean);
      if (rest.length) out.push(`<p>${inlineMd(escapeHtml(rest.join(" ")), index)}</p>`);
      continue;
    }

    // Bullet list — a `- `/`* ` line starts an item; non-bullet lines continue the prior one.
    if (/^\s*[-*]\s+/.test(lines[0])) {
      const items: string[] = [];
      for (const line of lines) {
        const m = line.match(/^\s*[-*]\s+(.*)$/);
        if (m) items.push(m[1].trim());
        else if (items.length) items[items.length - 1] += ` ${line.trim()}`;
      }
      const lis = items.map((it) => `<li>${inlineMd(escapeHtml(it), index)}</li>`).join("");
      out.push(`<ul>${lis}</ul>`);
      continue;
    }

    // Paragraph — soft wraps collapse to spaces.
    const text = lines
      .map((l) => l.trim())
      .filter(Boolean)
      .join(" ");
    out.push(`<p>${inlineMd(escapeHtml(text), index)}</p>`);
  }
  return out.join("\n");
}

/** Concepts that point at `slug` — via `related` or a `[[link]]` in their body. */
export function conceptBacklinks(
  slug: string,
  options: WikiIndexOptions = {},
): { url: string; label: string }[] {
  if (!hasFeed("concepts")) return [];
  const scoped = options.scoped ?? false;
  const concepts = loadFeed<ConceptItem[]>("concepts");
  const self = concepts.find((c) => c.slug === slug);
  const names = self
    ? new Set([norm(self.slug), norm(self.title), ...self.aliases.map(norm)])
    : new Set([slug]);
  const out: { url: string; label: string }[] = [];
  for (const c of concepts) {
    if (c.slug === slug) continue;
    const viaRelated = c.related.some((r) => norm(r) === norm(slug));
    const viaBody = [...c.body.matchAll(/\[\[([^\]]+)\]\]/g)].some((m) => names.has(norm(m[1])));
    if (viaRelated || viaBody) {
      out.push({ url: conceptHref(c.slug, scoped), label: c.title });
    }
  }
  return out;
}

/** One open question that raises a node — the backlink row on a concept/entity page (#1569). */
export interface OpenQuestionBacklink {
  id: string;
  question: string;
  origin: OpenQuestionItem["origin"];
  kind?: OpenQuestionItem["kind"];
  status?: OpenQuestionItem["status"];
  /** The `/wiki/open-questions/#…` deep link to this row on the board. */
  url: string;
}

/** The stable `#anchor` an open-question row is addressable at on the board page. */
export function openQuestionAnchor(id: string): string {
  return slugify(id);
}

/**
 * Whether a normalized name is specific enough to raise a backlink. The `open-questions` feed
 * carries plain prose, not `[[wiki links]]`, so a name is matched as a whole phrase against a
 * question's text — but a very short single token (`pH`, an initialism of two) would match noise,
 * so only multi-word names or single tokens of ≥4 chars qualify.
 */
function backlinkable(name: string): boolean {
  const n = norm(name);
  return n.length > 0 && (n.includes(" ") || n.length >= 4);
}

/**
 * Open questions whose prose (`question` + `detail`) *raises* any of these names — the reverse of
 * the `[[wiki link]]` backlink (#68), for a feed that names its subjects in prose rather than in
 * bracket syntax (#1569). Pass a node's own names (a concept's title/aliases, an entity's
 * display/variants); a name matches only as a whole normalized phrase (`ohio epa`, not a substring
 * of `ohio epated`), so the resulting backlinks stay on-topic. Reads the active site's feed, so a
 * build whose site ships no `open-questions` feed yields none — no empty backlink block.
 */
export function openQuestionBacklinks(names: (string | null | undefined)[]): OpenQuestionBacklink[] {
  if (!hasFeed("open-questions")) return [];
  const tokens = [...new Set(names.filter((n): n is string => n != null && backlinkable(n)).map(norm))];
  if (!tokens.length) return [];
  const out: OpenQuestionBacklink[] = [];
  for (const q of loadFeed<OpenQuestionItem[]>("open-questions")) {
    const hay = ` ${norm(`${q.question} ${q.detail}`)} `;
    if (tokens.some((t) => hay.includes(` ${t} `))) {
      out.push({
        id: q.id,
        question: q.question,
        origin: q.origin,
        kind: q.kind,
        status: q.status,
        url: `${withBase("/wiki/open-questions/")}#${openQuestionAnchor(q.id)}`,
      });
    }
  }
  return out;
}
