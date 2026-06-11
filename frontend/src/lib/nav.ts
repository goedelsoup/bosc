/**
 * The redesigned site's information architecture: four header sections, each
 * with a minimal table of contents (Epic #54 / issue #64). This is the single
 * source of truth — the header tabs, the per-section TOC rail, and the
 * build-time search index all read it.
 *
 * Each TOC `anchor` is an `id` the section's landing page renders, so the rail
 * links, the on-page scroll-spy, and search deep-links all resolve to a real
 * heading. The full per-item pages land in #65–#68.
 */

export type SectionId = "home" | "site" | "watershed" | "wiki";

export interface TocEntry {
  /** Visible label in the per-section TOC. */
  label: string;
  /** The `id` of the heading on the section page this entry points to. */
  anchor: string;
}

export interface Section {
  id: SectionId;
  /** Full label (header tab + section H1). */
  label: string;
  /** Root-absolute path to the section landing (pre-base). */
  href: string;
  /** One-line description (used on the landing and in search). */
  blurb: string;
  toc: TocEntry[];
}

export const SECTIONS: Section[] = [
  {
    id: "home",
    label: "Home / About",
    href: "/",
    blurb: "Landing, disclaimer, corpus at a glance, methodology, and the bigger picture.",
    toc: [
      { label: "Disclaimer", anchor: "disclaimer" },
      { label: "Corpus at a glance", anchor: "corpus" },
      { label: "Methodology", anchor: "methodology" },
      { label: "The bigger picture", anchor: "bigger-picture" },
    ],
  },
  {
    id: "site",
    label: "The BOSC site",
    href: "/site/",
    blurb: "Documents, records, timeline, exhibits, people & places, and legal history.",
    toc: [
      { label: "Documents", anchor: "documents" },
      { label: "Records", anchor: "records" },
      { label: "Timeline", anchor: "timeline" },
      { label: "Exhibits", anchor: "exhibits" },
      { label: "People & places", anchor: "people" },
      { label: "Legal history", anchor: "legal" },
    ],
  },
  {
    id: "watershed",
    label: "The Maumee watershed",
    href: "/watershed/",
    blurb: "Hydrology dashboards, the watershed map, imagery before/during/after, and RSEI toxics.",
    toc: [
      { label: "Hydrology", anchor: "hydrology" },
      { label: "Watershed map", anchor: "map" },
      { label: "Imagery", anchor: "imagery" },
      { label: "RSEI / toxics", anchor: "rsei" },
    ],
  },
  {
    id: "wiki",
    label: "Wiki",
    href: "/wiki/",
    blurb: "Entity & concept pages with backlinks and a graph neighborhood.",
    toc: [
      { label: "Entities", anchor: "entities" },
      { label: "People", anchor: "people" },
      { label: "Concepts", anchor: "concepts" },
      { label: "Curated entities", anchor: "curated" },
    ],
  },
];

export function getSection(id: SectionId): Section {
  const section = SECTIONS.find((s) => s.id === id);
  if (!section) throw new Error(`Unknown section "${id}"`);
  return section;
}
