/**
 * Build-time assembly of the **ask-index** — the retrieval corpus the "Ask the
 * corpus" portal grounds answers in (Epic #207, issue #209).
 *
 * One retrieval unit per citation-bearing bundle thing (a record, timeline event,
 * entity, person, place, meeting, concept, document collection). Each unit carries the
 * item's provenance (lifted from its `Citation`) and a stable deep link to the page it
 * lives on, so an answer can cite a claim straight back to a verifiable page (#213).
 *
 * This mirrors `buildSearchIndex` (src/lib/search.ts) and is emitted as a static asset
 * by `src/pages/ask-index.json.ts` — the `/api/ask` Worker fetches it the same way the
 * client search box fetches `/search-index.json`. BM25 tokenization + scoring live in
 * the Worker (functions/api/_lib/retrieval.ts), at query time, so the build only ships
 * raw text + provenance.
 */
import { blob } from "./format";
import { siteUrl } from "./routes";
import { activeSite, hasFeed, loadFeed } from "./bundle";
import {
  type Citation,
  type ConceptItem,
  type DocumentCollectionItem,
  type EntityNode,
  type MeetingItem,
  type PersonItem,
  type PlaceItem,
  type RecordItem,
  slugify,
  type TimelineEntry,
} from "./feeds";

/**
 * A retrieval unit. Structurally identical to `AskUnit` in
 * `functions/api/_lib/retrieval.ts` (the consumer) — the emitted `/ask-index.json` is
 * the contract between them, exactly as `SearchDoc` is shared between `lib/search.ts`
 * and `scripts/search.ts`.
 */
export interface AskUnit {
  id: string;
  feed: string;
  title: string;
  url: string;
  text: string;
  source?: string | null;
  page?: number | null;
  source_kind?: string | null;
  confidence?: string | null;
  verified?: boolean;
  /** Site slug (e.g. "lima"). Set at build time from the active bundle. */
  site?: string;
  /** Structured event/record date (ISO-ish), when the source feed carries one — timeline
   * and meeting units today. Surfaced on discovery cards so a caller can filter/sort by
   * date without paying for the full record (#1580). */
  date?: string | null;
  /** The `data/documents` rel of the source document this unit reads from — the robust join key
   * for version/duplicate-cluster dedup (#1590), keyed the same as `DocumentItem.rel`. Set from a
   * record's `source_doc_rel` (the #276 join), else from `source` with a leading `data/documents/`
   * stripped; absent when the unit has no documents-feed source. Unlike `source` (which is often
   * an extracted-yaml path and carries a `data/documents/` prefix), this always matches a rel. */
  doc_rel?: string | null;
}

/** The `data/documents`-relative rel a unit's `source` points at, or undefined when `source`
 * isn't a documents path (e.g. an extracted-yaml artifact). Strips the corpus prefix so the
 * value matches `DocumentItem.rel`. */
function docRelOf(source: string | null | undefined): string | undefined {
  if (!source) return undefined;
  const prefix = "data/documents/";
  return source.startsWith(prefix) ? source.slice(prefix.length) : undefined;
}

/** Flatten a record's `fields` into "key value" pairs so figures are searchable (#327).
 * Recurses into nested objects so structured values (e.g. markup breakdowns) are indexed. */
function fieldText(fields: Record<string, unknown>): string {
  const bits: string[] = [];
  function collect(obj: Record<string, unknown>): void {
    for (const [k, v] of Object.entries(obj)) {
      if (v == null) continue;
      if (Array.isArray(v)) {
        const scalars = v.filter((x) => x != null && typeof x !== "object").map(String);
        if (scalars.length > 0) bits.push(`${k} ${scalars.join(" ")}`);
      } else if (typeof v === "object") {
        collect(v as Record<string, unknown>);
      } else {
        bits.push(`${k} ${String(v)}`);
      }
    }
  }
  collect(fields);
  return bits.join(" · ");
}

/** Lift the provenance fields off a Citation onto a unit (undefined when absent). */
function cite(c: Citation | null | undefined): Partial<AskUnit> {
  if (!c) return {};
  return {
    source: c.source ?? undefined,
    page: c.page ?? undefined,
    source_kind: c.source_kind ?? undefined,
    confidence: c.confidence ?? undefined,
    verified: c.verified,
  };
}

export function buildAskIndex(): AskUnit[] {
  const site = activeSite();
  const units: AskUnit[] = [];

  if (hasFeed("records")) {
    for (const r of loadFeed<RecordItem[]>("records")) {
      units.push({
        id: `records:${r.rel}`,
        feed: "records",
        title: r.title,
        url: siteUrl(`/site/records/${r.group}/`),
        text: blob(r.group, r.confidence, ...r.warnings, fieldText(r.fields)),
        ...cite(r.citation),
        // The #276 join to the real source document is the robust dedup key (#1590) — far more
        // reliable than citation.source, which is often the extracted-yaml path.
        doc_rel: r.source_doc_rel ?? docRelOf(r.citation?.source),
      });
    }
  }

  if (hasFeed("timeline")) {
    for (const e of loadFeed<TimelineEntry[]>("timeline")) {
      units.push({
        id: `timeline:${e.ref || slugify(`${e.date}-${e.title}`)}`,
        feed: "timeline",
        title: `${e.date} — ${e.title}`,
        url: siteUrl("/timeline"),
        date: e.date,
        text: blob(e.category, e.detail, e.source, ...e.parties, ...e.also_sources),
        // The timeline carries an explicit source string even when citation is null.
        ...(e.citation ? cite(e.citation) : { source: e.source, source_kind: "document" }),
        doc_rel: docRelOf(e.citation?.source ?? e.source),
      });
    }
  }

  if (hasFeed("documents")) {
    for (const c of loadFeed<DocumentCollectionItem[]>("documents")) {
      units.push({
        id: `documents:${c.slug}`,
        feed: "documents",
        title: c.title,
        url: siteUrl(`/site/documents/#doc-${c.slug}`),
        text: blob(c.description, ...c.entries.map((x) => x.name)),
        source: c.entries[0]?.rel,
        source_kind: "document",
      });
    }
  }

  if (hasFeed("meetings")) {
    for (const m of loadFeed<MeetingItem[]>("meetings")) {
      units.push({
        id: `meetings:${m.slug}`,
        feed: "meetings",
        title: `${m.date ?? ""} — ${m.kind ?? "meeting"} (${m.slug})`.trim(),
        url: siteUrl("/site/legal#meetings"),
        date: m.date ?? null,
        text: blob(m.summary, m.corridor_relevance, ...m.decisions, ...m.parties, ...m.dollar_figures),
        ...cite(m.citation),
      });
    }
  }

  if (hasFeed("people")) {
    for (const p of loadFeed<PersonItem[]>("people")) {
      units.push({
        id: `people:${p.slug}`,
        feed: "people",
        title: p.name,
        url: siteUrl(`/site/people/${p.slug}/`),
        text: blob(...p.aliases, ...p.roles, ...p.affiliations, p.summary, p.body),
        ...cite(p.sources[0]),
      });
    }
  }

  if (hasFeed("places")) {
    for (const p of loadFeed<PlaceItem[]>("places")) {
      units.push({
        id: `places:${p.slug}`,
        feed: "places",
        title: p.name,
        url: siteUrl(`/site/places/${p.slug}/`),
        text: blob(p.kind, ...p.aliases, ...p.tags, ...p.parcels, p.body),
        ...cite(p.citations[0]),
      });
    }
  }

  if (hasFeed("entities")) {
    for (const e of loadFeed<EntityNode[]>("entities")) {
      units.push({
        id: `entities:${e.key}`,
        feed: "entities",
        title: e.display,
        url: `/wiki/entities/${slugify(e.key)}/`,
        text: blob(
          e.kind,
          e.classification,
          ...e.variants,
          ...Object.keys(e.roles ?? {}),
          ...e.addresses,
          ...e.parcels,
        ),
        // Entities carry source paths, not a Citation; treat the first as the artifact.
        source: e.sources[0],
        source_kind: "document",
        doc_rel: docRelOf(e.sources[0]),
      });
    }
  }

  if (hasFeed("concepts")) {
    for (const c of loadFeed<ConceptItem[]>("concepts")) {
      units.push({
        id: `concepts:${c.slug}`,
        feed: "concepts",
        title: c.title,
        url: `/wiki/concepts/${c.slug}/`,
        text: blob(c.summary, ...c.aliases, ...c.tags, c.body),
        // The glossary is editorial synthesis over the corpus, not a single source.
        source_kind: "derived",
      });
    }
  }

  return units.map((u) => ({ ...u, site }));
}
