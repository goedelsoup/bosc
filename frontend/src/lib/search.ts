/**
 * Build-time assembly of the client search index over the content bundle.
 *
 * One entry per searchable thing: a section page, or a bundle row (record,
 * timeline event, person, entity, concept, meeting, place, document collection).
 * Each entry deep-links to the page that thing lives on. The emitted JSON is
 * consumed by the dependency-free client matcher in `scripts/search.ts` — no
 * lunr, no CDN.
 */
import { hasFeed, loadFeed } from "./bundle";
import {
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
import { getSection, SECTIONS } from "./nav";
import { NARRATIVE } from "./narrative";

export interface SearchDoc {
  title: string;
  url: string;
  section: string;
  text: string;
}

/** Join defined, non-empty string-ish bits into one searchable blob. */
function blob(...parts: (string | null | undefined)[]): string {
  return parts
    .filter((p): p is string => typeof p === "string" && p.trim().length > 0)
    .join(" · ");
}

export function buildSearchIndex(): SearchDoc[] {
  const docs: SearchDoc[] = [];

  // Section landings + their TOC areas — always present, bundle or not.
  for (const s of SECTIONS) {
    docs.push({ title: s.label, url: s.href, section: s.label, text: s.blurb });
    for (const t of s.toc) {
      docs.push({
        title: `${t.label} — ${s.label}`,
        url: `${s.href}#${t.anchor}`,
        section: s.label,
        text: `${t.label} ${s.blurb}`,
      });
    }
  }

  // Migrated narrative prose (#69) — by title + blurb.
  for (const d of NARRATIVE) {
    docs.push({
      title: d.title,
      url: `/docs/${d.slug}`,
      section: getSection(d.section).label,
      text: d.blurb,
    });
  }

  const SITE = "The BOSC site";
  const WIKI = "Wiki";

  if (hasFeed("records")) {
    for (const r of loadFeed<RecordItem[]>("records")) {
      docs.push({
        title: r.title,
        url: `/site/records/${r.group}/`,
        section: SITE,
        text: blob(r.group, r.confidence, ...r.warnings, String(r.fields?.instrument_no ?? "")),
      });
    }
  }

  if (hasFeed("timeline")) {
    for (const e of loadFeed<TimelineEntry[]>("timeline")) {
      docs.push({
        title: `${e.date} — ${e.title}`,
        url: "/site/timeline",
        section: SITE,
        text: blob(e.category, e.detail, e.source, ...e.parties),
      });
    }
  }

  if (hasFeed("documents")) {
    for (const c of loadFeed<DocumentCollectionItem[]>("documents")) {
      docs.push({
        title: c.title,
        url: `/site/documents/#doc-${c.slug}`,
        section: SITE,
        text: blob(c.description, ...c.entries.slice(0, 12).map((e) => e.name)),
      });
    }
  }

  if (hasFeed("meetings")) {
    for (const m of loadFeed<MeetingItem[]>("meetings")) {
      docs.push({
        title: `${m.date} — ${m.kind} (${m.slug})`,
        url: "/site/legal#meetings",
        section: SITE,
        text: blob(m.summary),
      });
    }
  }

  if (hasFeed("places")) {
    for (const p of loadFeed<PlaceItem[]>("places")) {
      docs.push({
        title: p.name,
        url: `/site/places/${p.slug}/`,
        section: SITE,
        text: blob(p.kind, ...p.aliases, ...p.tags, p.body),
      });
    }
  }

  if (hasFeed("people")) {
    for (const p of loadFeed<PersonItem[]>("people")) {
      docs.push({
        title: p.name,
        url: `/site/people/${p.slug}/`,
        section: SITE,
        text: blob(...p.aliases, ...p.roles, ...p.affiliations, p.summary),
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
    });
  }
  if (hasFeed("defense-contractors")) {
    const dc = loadFeed<DefenseContractors>("defense-contractors");
    docs.push({
      title: "Defense contractors",
      url: "/wiki/defense-contractors",
      section: WIKI,
      text: blob("DoD prime contractor pattern matches", ...dc.contractors.map((c) => c.name)),
    });
  }
  if (hasFeed("lei")) {
    const lei = loadFeed<LeiInventory>("lei");
    docs.push({
      title: "Entity LEIs (GLEIF)",
      url: "/wiki/lei",
      section: WIKI,
      text: blob("GLEIF legal entity identifiers", ...lei.records.map((r) => r.legal_name)),
    });
  }
  if (hasFeed("economics-baseline")) {
    const eb = loadFeed<EconomicBaseline>("economics-baseline");
    docs.push({
      title: "Economics — localized baseline",
      url: "/watershed/economics-baseline",
      section: getSection("watershed").label,
      text: blob("BLS QCEW Census employment population baseline", eb.area_name, eb.note),
    });
  }

  return docs;
}
