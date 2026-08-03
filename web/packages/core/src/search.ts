/**
 * Build-time assembly of the client search index over the content bundle.
 *
 * One entry per searchable thing: a section page, or a bundle row (record,
 * timeline event, person, entity, concept, meeting, place, document collection).
 * Each entry deep-links to the page that thing lives on. The emitted JSON is
 * consumed by the dependency-free client matcher in `scripts/search.ts` — no
 * lunr, no CDN.
 */
import { blob } from "./format";
import { siteUrl } from "./routes";
import { hasFeed, loadFeed } from "./bundle";
import {
  evidenceKind,
  slugify,
  type CandidateItem,
  type ConceptItem,
  type DefenseContractors,
  type DocumentCollectionItem,
  type EconomicBaseline,
  type EntityNode,
  type LeiInventory,
  type MeetingItem,
  type PersonItem,
  type PlaceItem,
  type RecordItem,
  type TimelineEntry,
} from "./feeds";
import { LEGAL } from "./legal";
import { getSection, sections } from "./nav";
import { NARRATIVE } from "./narrative";
import { REFERENCE } from "./reference";
import { SITES, siteBadge, siteState } from "./sites";
import type { TagKind } from "./teardown";

export interface SearchDoc {
  title: string;
  url: string;
  section: string;
  text: string;
  /** Short kind eyebrow for the result row (#307): Record, Entity, Concept, … */
  kind: string;
  /** A mono identifier shown on the row, when the thing carries a real one. */
  id?: string;
  /** Evidence dot — set only where the row carries a genuine evidence signal
   *  (records, via their citation). Absent rows show no dot — no fabricated tag. */
  tag?: TagKind;
}

export function buildSearchIndex(): SearchDoc[] {
  const docs: SearchDoc[] = [];

  // Section landings + their TOC areas — always present, bundle or not.
  for (const s of sections()) {
    docs.push({ title: s.label, url: s.href, section: s.label, text: s.blurb, kind: "Section" });
    for (const t of s.toc) {
      docs.push({
        title: `${t.label} — ${s.label}`,
        url: `${s.href}#${t.anchor}`,
        section: s.label,
        text: `${t.label} ${s.blurb}`,
        kind: "Section",
      });
    }
  }

  // The network's own sites (#1888) — the canonical index, plus one entry per REGISTERED site.
  // Off the registry, not the bundle, so a site is findable the moment it's registered and a
  // reader searching a place name lands on that site instead of on whichever page happens to
  // mention it. Deeper per-site corpus coverage is #1890.
  const network = getSection("directory").label;
  docs.push({
    title: "The network — every site",
    url: "/network",
    section: network,
    text: blob(
      "network index directory every registered watershed point site",
      `${SITES.length} sites`,
      ...SITES.map((s) => s.place),
    ),
    kind: "Section",
  });
  for (const site of SITES) {
    docs.push({
      title: site.place,
      url: site.href,
      section: network,
      text: blob(site.basin, site.county, site.codename, site.mono, siteState(site.slug)),
      kind: "Site",
      id: siteBadge(site),
    });
  }

  // Migrated narrative prose (#69) — by title + blurb. Network-global at the root (#1304), so a
  // plain `/docs/<slug>` path (like the `/wiki/...` entries), not the Lima-scoped `siteUrl`.
  for (const d of NARRATIVE) {
    docs.push({
      title: d.title,
      url: `/docs/${d.slug}`,
      section: getSection(d.section).label,
      text: d.blurb,
      kind: "Doc",
    });
  }

  // Reference datasets (Pages cutover #104) — by title + blurb.
  for (const d of REFERENCE) {
    docs.push({
      title: d.title,
      url: siteUrl(`/site/reference/${d.slug}`),
      section: "The record",
      text: blob("reference data", d.blurb),
      kind: "Reference",
    });
  }

  // Legal-history docs (Pages cutover #105) — by title + group + blurb.
  for (const d of LEGAL) {
    docs.push({
      title: d.title,
      url: siteUrl(`/site/legal/${d.slug}`),
      section: "The record",
      text: blob(d.group, d.blurb),
      kind: "Legal",
    });
  }

  const SITE = "The record";
  const WIKI = "Wiki";

  if (hasFeed("records")) {
    for (const r of loadFeed<RecordItem[]>("records")) {
      const instrument = r.fields?.instrument_no;
      docs.push({
        title: r.title,
        url: siteUrl(`/site/records/${r.group}/`),
        section: SITE,
        text: blob(r.group, r.confidence, ...r.warnings, String(instrument ?? "")),
        kind: "Record",
        // Records carry a real per-row evidence signal — its citation's verified flag.
        tag: evidenceKind(r.citation),
        id: instrument ? String(instrument) : undefined,
      });
    }
  }

  if (hasFeed("timeline")) {
    for (const e of loadFeed<TimelineEntry[]>("timeline")) {
      docs.push({
        title: `${e.date} — ${e.title}`,
        url: siteUrl("/timeline"),
        section: SITE,
        text: blob(e.category, e.detail, e.source, ...e.parties),
        kind: "Timeline",
      });
    }
  }

  if (hasFeed("documents")) {
    for (const c of loadFeed<DocumentCollectionItem[]>("documents")) {
      docs.push({
        title: c.title,
        url: siteUrl(`/site/documents/#doc-${c.slug}`),
        section: SITE,
        text: blob(c.description, ...c.entries.slice(0, 12).map((e) => e.name)),
        kind: "Document",
      });
    }
  }

  if (hasFeed("meetings")) {
    for (const m of loadFeed<MeetingItem[]>("meetings")) {
      docs.push({
        title: `${m.date} — ${m.kind}`,
        url: siteUrl("/site/legal#meetings"),
        section: SITE,
        text: blob(m.summary),
        kind: "Meeting",
        id: m.slug,
      });
    }
  }

  if (hasFeed("places")) {
    for (const p of loadFeed<PlaceItem[]>("places")) {
      docs.push({
        title: p.name,
        url: siteUrl(`/site/places/${p.slug}/`),
        section: SITE,
        text: blob(p.kind, ...p.aliases, ...p.tags, p.body),
        kind: "Place",
      });
    }
  }

  if (hasFeed("people")) {
    for (const p of loadFeed<PersonItem[]>("people")) {
      docs.push({
        title: p.name,
        url: siteUrl(`/site/people/${p.slug}/`),
        section: SITE,
        text: blob(...p.aliases, ...p.roles, ...p.affiliations, p.summary),
        kind: "Person",
      });
    }
  }

  if (hasFeed("entities")) {
    for (const e of loadFeed<EntityNode[]>("entities")) {
      docs.push({
        title: e.display,
        url: `/wiki/entities/${slugify(e.key)}/`,
        section: WIKI,
        text: blob(e.kind, e.classification, ...e.variants, ...Object.keys(e.roles ?? {})),
        kind: "Entity",
      });
    }
  }

  if (hasFeed("concepts")) {
    for (const c of loadFeed<ConceptItem[]>("concepts")) {
      docs.push({
        title: c.title,
        url: `/wiki/concepts/${c.slug}/`,
        section: WIKI,
        text: blob(c.summary, ...c.aliases, ...c.tags, c.body),
        kind: "Concept",
      });
    }
  }

  // Curated-entity + economics pages (Pages cutover #103) — one entry per page.
  if (hasFeed("candidates")) {
    const rows = loadFeed<CandidateItem[]>("candidates");
    docs.push({
      title: "Cloud-consumer candidates",
      url: "/wiki/candidates",
      section: WIKI,
      text: blob("cloud-consumer demand-fit candidates", ...rows.map((c) => c.name)),
      kind: "Wiki",
    });
  }
  if (hasFeed("defense-contractors")) {
    const dc = loadFeed<DefenseContractors>("defense-contractors");
    docs.push({
      title: "Defense contractors",
      url: "/wiki/defense-contractors",
      section: WIKI,
      text: blob("DoD prime contractor pattern matches", ...dc.contractors.map((c) => c.name)),
      kind: "Wiki",
    });
  }
  if (hasFeed("lei")) {
    const lei = loadFeed<LeiInventory>("lei");
    docs.push({
      title: "Entity LEIs (GLEIF)",
      url: "/wiki/lei",
      section: WIKI,
      text: blob("GLEIF legal entity identifiers", ...lei.records.map((r) => r.legal_name)),
      kind: "Wiki",
    });
  }
  if (hasFeed("economics-baseline")) {
    const eb = loadFeed<EconomicBaseline>("economics-baseline");
    docs.push({
      title: "Economics — localized baseline",
      url: siteUrl("/environment/economics-baseline"),
      // Economic ground, so it's filed under the economy section even though the route still
      // lives under /environment/ (#1323).
      section: getSection("economy").label,
      text: blob("BLS QCEW Census employment population baseline", eb.area_name, eb.note),
      kind: "Dataset",
    });
  }

  return docs;
}
