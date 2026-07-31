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
import { facetKey, projectKey } from "./askFacets";
import { SITES } from "./sites";
import {
  type Citation,
  type ConceptItem,
  type DocumentCollectionItem,
  type EntityNode,
  type FacilityItem,
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
  /** Every 1-based page the claim was read from, when the read spanned more than one (#1584).
   * Lifted from `Citation.pages`; absent for a single-page or page-less source. */
  pages?: number[] | null;
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

  // --- Enrichment facets (#1691) ------------------------------------------------------------
  // The facets #1582 deliberately left un-modeled because they weren't indexed. Every one is
  // projected from a value the bundle ALREADY carries — none is inferred, and a unit whose feed
  // has nothing to say simply omits the field (and is therefore excluded by that filter, the
  // same contract `date` already has). Matching semantics live in `./askFacets`.

  /** The county this site's records are filed in, e.g. "Allen County, OH". Site identity, not a
   * feed value: stamped from the `data/sites.yaml` registry the way `site` is, so it is constant
   * across a single-site index and meaningful the day the index spans more than one. Absent for
   * a slug with no registered county. */
  county?: string | null;
  /** The issuing/administering body, verbatim from the record's own `agency` (or `issuing_agency`)
   * field — "Ohio EPA, Division of Surface Water", not a normalized taxonomy key. The corpus
   * writes an agency as the document names it, and inventing a controlled vocabulary here would
   * assert an equivalence the extraction never made; `agencyMatches` does the reconciling at query
   * time instead. Records only — no other feed carries an issuing body. */
  agency?: string | null;
  /** Every permit / case / filing identifier this unit is filed under (`permit_no`, `npdes_id`,
   * `application_no`, `case_no`, `filing_id`, `award_no` from a record's fields; a timeline
   * entry's `ref`, which is documented as exactly this). A LIST because one record commonly
   * carries both a state permit number and its federal NPDES id, and collapsing them would make
   * the record findable by only one. */
  permit_numbers?: string[] | null;
  /** The document genre, distinct from `feed` — a `records` feed spans permits, deeds,
   * enforcement orders, loan awards, pleadings and layoff notices, and `feed:"records"` can't
   * tell them apart. Taken from the closed vocabularies the feeds already carry:
   * `RecordItem.group`, `TimelineEntry.category`, `MeetingItem.kind`. */
  document_type?: string | null;
  /** The entity-graph keys this unit touches — the SAME keys `get_entities` returns, so a caller
   * can pivot from an entity to its records without a name-matching step. Joined exactly, never
   * fuzzily: an entity node lists the extraction paths it was read from (`EntityNode.sources`),
   * and that path IS a record's `rel` / a timeline entry's `source`. Place relationships and a
   * person's `entity_key` supply the rest. */
  entities?: string[] | null;
  /** The campus / named project this unit belongs to, as a slug — resolved to the `facility` feed's
   * key when it resolves there, else the slugified project name the record itself states. The
   * `project` and `campus` filters are two names for this one facet. */
  project?: string | null;
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

// --- Facet projection (#1691) ---------------------------------------------------------------

/** The record `fields` keys that hold a permit / case / filing identifier. Deliberately a fixed
 * list rather than a "any key matching /permit|case|no$/" heuristic: `fields` is a free-form
 * extraction payload, and a pattern would sweep in `instrument_no`, `project_no`, `sheet_id` and
 * `award_no`-adjacent numbers that are not permits. A genre that files under a new key adds it
 * here, explicitly. */
const PERMIT_FIELD_KEYS = [
  "permit_no",
  "permit_number",
  "npdes_id",
  "application_no",
  "case_no",
  "filing_id",
  "award_no",
] as const;

/** The record `fields` keys that name the issuing/administering body, most specific first. */
const AGENCY_FIELD_KEYS = ["agency", "issuing_agency"] as const;

/** Every non-empty string at `keys` in a free-form `fields` payload, flattening a list value
 * (a record may file under several permit numbers) and skipping anything that isn't a string. */
function fieldStrings(fields: Record<string, unknown>, keys: readonly string[]): string[] {
  const out: string[] = [];
  for (const k of keys) {
    const v = fields[k];
    if (typeof v === "string" && v.trim()) out.push(v.trim());
    else if (Array.isArray(v)) {
      for (const x of v) if (typeof x === "string" && x.trim()) out.push(x.trim());
    }
  }
  return [...new Set(out)];
}

/** The first non-empty string at `keys`, or undefined. */
function firstFieldString(fields: Record<string, unknown>, keys: readonly string[]): string | undefined {
  return fieldStrings(fields, keys)[0];
}

/**
 * The entity-graph join: extraction source path → the keys of every entity read from it.
 *
 * `EntityNode.sources` records the artifacts a node was extracted from, and those strings are the
 * same `rel`s the records feed is keyed by (and the same `source` a timeline entry / meeting
 * citation names). So this is an **exact** join on a shared identifier, not name matching — which
 * is the only kind of entity attribution the evidentiary discipline permits here.
 */
function entityKeysBySource(entities: EntityNode[]): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const e of entities) {
    for (const s of e.sources) {
      const at = out.get(s);
      if (at) at.push(e.key);
      else out.set(s, [e.key]);
    }
  }
  return out;
}

/** Resolve a party *name* (a place relationship's `entity`, which is a display string rather than
 * a key) to its graph key, via the node's display name and declared variants. Returns the input
 * unchanged when nothing resolves: the relationship named a real party the graph hasn't got a node
 * for, and dropping it would lose a true attribution. */
function entityKeyByName(entities: EntityNode[]): Map<string, string> {
  const out = new Map<string, string>();
  for (const e of entities) {
    for (const name of [e.key, e.display, ...e.variants]) {
      const k = facetKey(name);
      if (k) out.set(k, e.key);
    }
  }
  return out;
}

/** A list facet's value, or undefined when there's nothing to say — so a unit with no attribution
 * omits the field entirely rather than carrying an empty array a filter would have to
 * special-case (and the emitted index doesn't grow a key per unit for nothing). */
function nonEmpty(values: (string | null | undefined)[]): string[] | undefined {
  const out = [...new Set(values.filter((k): k is string => typeof k === "string" && k.length > 0))];
  return out.length > 0 ? out : undefined;
}

/**
 * The `facility` feed key a stated project/campus name resolves to, or undefined when the name
 * doesn't correspond to a facility this site discloses.
 *
 * The match is exact **or segment-prefixed**: Lima files records under "Project Bosc", "Project
 * BOSC" and "Project Bosc Lvl 2 IWP", all of which are the `project-bosc` campus. Requiring the
 * `-` boundary is what keeps `project-bosc` from swallowing a hypothetical `project-boscage`.
 */
function facilityKeyFor(name: string, facilities: FacilityItem[]): string | undefined {
  const slug = projectKey(name);
  if (!slug) return undefined;
  for (const f of facilities) {
    for (const candidate of [f.key, projectKey(f.name)]) {
      if (slug === candidate || slug.startsWith(`${candidate}-`)) return f.key;
    }
  }
  return undefined;
}

/** Lift the provenance fields off a Citation onto a unit (undefined when absent). */
function cite(c: Citation | null | undefined): Partial<AskUnit> {
  if (!c) return {};
  return {
    source: c.source ?? undefined,
    page: c.page ?? undefined,
    pages: c.pages ?? undefined,
    source_kind: c.source_kind ?? undefined,
    confidence: c.confidence ?? undefined,
    verified: c.verified,
  };
}

export function buildAskIndex(): AskUnit[] {
  const site = activeSite();
  const units: AskUnit[] = [];

  // The enrichment facets' cross-feed joins (#1691), resolved once. `entities` and `facility` are
  // read here rather than inside each block because a record/timeline/meeting unit is attributed
  // through them — the entity graph is what says which parties a filing touches, and the facility
  // feed is what says which campus a stated project name is.
  const entities = hasFeed("entities") ? loadFeed<EntityNode[]>("entities") : [];
  const facilities = hasFeed("facility") ? loadFeed<FacilityItem[]>("facility") : [];
  const entsBySource = entityKeysBySource(entities);
  const entsByName = entityKeyByName(entities);
  // The campus a record names implicitly by citing its air permit — the facility feed's own
  // `air_permit_relpath` IS a record `rel`, so this attributes the permit record to the campus
  // without reading a project name off it.
  const projectByRecordRel = new Map<string, string>(
    facilities.flatMap((f) => (f.air_permit_relpath ? [[f.air_permit_relpath, f.key] as const] : [])),
  );

  if (hasFeed("records")) {
    for (const r of loadFeed<RecordItem[]>("records")) {
      const stated = firstFieldString(r.fields, ["project_name"]);
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
        // The record genre IS the document type — `feed:"records"` spans all of them (#1691).
        document_type: r.group,
        permit_numbers: nonEmpty(fieldStrings(r.fields, PERMIT_FIELD_KEYS)),
        agency: firstFieldString(r.fields, AGENCY_FIELD_KEYS),
        entities: nonEmpty(entsBySource.get(r.rel) ?? []),
        // The air-permit join is the stronger claim (the facility feed asserts it), so it wins
        // over a name the record states in passing. An unresolved name still indexes under its
        // own slug — "Project Dazzler" is a real named project the site has no facility row for,
        // and dropping it would make it unfindable.
        project:
          projectByRecordRel.get(r.rel) ??
          (stated ? (facilityKeyFor(stated, facilities) ?? projectKey(stated)) : undefined),
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
        document_type: e.category,
        // `ref` is documented as the "logical id (instrument / permit no) for cross-doc dedup" —
        // it is this facet, already normalized by the extraction.
        permit_numbers: nonEmpty(e.ref ? [e.ref] : []),
        entities: nonEmpty([
          ...(entsBySource.get(e.source) ?? []),
          ...(e.citation?.source ? (entsBySource.get(e.citation.source) ?? []) : []),
        ]),
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
        // A meeting's `kind` is its instrument genre (minutes, resolution, …) — the same axis
        // `RecordItem.group` names for a filing.
        document_type: m.kind ?? undefined,
        entities: nonEmpty(entsBySource.get(m.citation.source ?? "") ?? []),
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
        // A person page names its own graph node when the roster resolved one (#1691).
        entities: nonEmpty([p.entity_key]),
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
        // A place names its parties by DISPLAY name, not graph key, so resolve them through the
        // node's display + declared variants; an unresolvable name is kept as stated rather than
        // dropped (it is still a true attribution, just one the graph has no node for).
        entities: nonEmpty(p.relationships.map((r) => entsByName.get(facetKey(r.entity)) ?? r.entity)),
        // A campus place tags itself with its project (Fort Wayne's carries `project-zodiac`).
        // Only a tag that resolves to a disclosed facility counts — `datacenter` and `campus` are
        // vocabulary, not a project name.
        project: p.tags.map((t) => facilityKeyFor(t, facilities)).find(Boolean),
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
        // An entity's own node is trivially "about" that entity — so `filters.entity` returns the
        // party's page alongside the filings that touch it, not just the filings.
        entities: [e.key],
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

  // `county` rides alongside `site` because it is the same kind of value — the site's identity,
  // not something any one feed said — and it comes from the same registry (#1691). A slug with no
  // registered county (a tracking-only entry) stamps nothing rather than guessing one.
  const county = SITES.find((s) => s.slug === site)?.county ?? undefined;
  return uniquifyIds(units).map((u) => ({ ...u, site, ...(county ? { county } : {}) }));
}

/**
 * Make every unit id unique, disambiguating only where one repeats (#1422).
 *
 * A unit id is the retrieval index's JOIN KEY: `retrieval.ts` builds
 * `new Map(embeddings.map((e) => [e.id, e.embedding]))`, and a `Map` keeps the LAST entry for a
 * repeated key — so two units sharing an id are scored against one vector and one of them
 * silently loses its own semantics. The rank-fusion maps a few lines later collapse them too.
 *
 * The timeline is where this bites. Its `ref` is documented as a "logical id (instrument /
 * permit no) for cross-doc dedup" — it is *designed* to be shared by every event about one
 * instrument, so it was never a unique key. Ottawa's NPDES fact sheet alone yields two dated
 * events under `2PD00028*PD` (the public notice, and the comment-period close).
 *
 * Only the second and later occurrences are suffixed, so every id that was already unique stays
 * byte-identical and no committed bundle churns. Feed order is deterministic, so the suffixes are
 * stable. Mirrored exactly by `_uniquify_ids()` in `watermark/site/embeddings.py` — the two must
 * agree or the BM25 unit and its vector stop joining.
 */
export function uniquifyIds<T extends { id: string }>(units: T[]): T[] {
  const seen = new Map<string, number>();
  return units.map((u) => {
    const n = (seen.get(u.id) ?? 0) + 1;
    seen.set(u.id, n);
    return n === 1 ? u : { ...u, id: `${u.id}#${n}` };
  });
}
