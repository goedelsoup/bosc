/**
 * The Record Block (design "Record Block") — the library's per-record unit, one
 * family with the Record Teardown at reference density. This module is the data
 * shape the `RecordBlock.astro` component renders, plus a mapper from a live
 * `records`-feed row so the library and the walk read the same feed.
 */
import type { TagKind } from "./teardown";
import { evidenceKind, slugify, type RecordItem } from "./feeds";
import { formatScalar, groupLabel, isApproximate, isStructured, withApproxMark } from "./records";
import { activeStoryAnchorFor } from "./walk";
import { withSite, withStory } from "./site";

export interface BlockField {
  label: string;
  value: string;
  warn?: boolean;
  tag?: TagKind;
}

/** A structured (object/array) field, rendered as a hierarchy by `FieldValue`. */
export interface NestedField {
  label: string;
  /** The raw value (object/array), rendered recursively. */
  value: unknown;
  /** Dotted base path (the field key) for approximate-marker lookup. */
  path: string;
}

export interface BlockSeenIn {
  ch: string;
  label: string;
  href: string;
}

/** A "where it connects" chip — the same affordance that closes the teardown
 *  (design "Record Block" ⑤). The records feed carries no entity/concept/timeline
 *  join yet, so today's derivable connects are the group and the walk chapter;
 *  richer cross-links wait on that join. */
export interface BlockConnect {
  /** Short uppercase eyebrow (e.g. "records", "walk"). */
  kind: string;
  label: string;
  href?: string;
}

export interface LibraryRecord {
  /** Anchor id (slug of the record `rel`) for deep links from the walk. */
  id: string;
  kind: string;
  title: string;
  recordId: string;
  evidence: TagKind;
  seenIn?: BlockSeenIn;
  /** Headline figure shown in compact density. */
  headlineValue?: string;
  headlineWarn?: boolean;
  /** Scalar fields — the flat label/value grid. */
  fields: BlockField[];
  /** Structured (object/array) fields — rendered as a hierarchy. */
  nested: NestedField[];
  /** The record's `~` approximate paths, for marking nested leaves. */
  approxPaths: string[];
  warnings: string[];
  source: { file: string; pages: string; collection: string };
  verify?: { label: string; href: string };
  correctHref?: string;
  /** Compact-density row link target. */
  href?: string;
  /** "Where it connects" chips (full density) — the affordance that closes the
   *  record, mirroring the teardown's ⑤. */
  connect: BlockConnect[];
}

/** The top-level collection of a `rel` (e.g. "permits/4132514.epa.yaml" → "permits"). */
function relCollection(rel: string): string {
  const i = rel.indexOf("/");
  return i > 0 ? rel.slice(0, i) : rel;
}

/** A short, human record id from the `rel` basename (without extensions). */
function relRecordId(rel: string): string {
  const base = rel.slice(rel.lastIndexOf("/") + 1);
  return base.replace(/\.[a-z0-9]+(\.[a-z0-9]+)?$/i, "");
}

/** Map a live `records`-feed row onto the Record Block shape. */
export function recordToBlock(r: RecordItem): LibraryRecord {
  // Scalars render as the flat grid; structured values become a hierarchy (a
  // bullet tree), never a `JSON.stringify` blob.
  const fields: BlockField[] = [];
  const nested: NestedField[] = [];
  for (const [k, v] of Object.entries(r.fields)) {
    if (isStructured(v)) {
      nested.push({ label: k, value: v, path: k });
    } else {
      const approx = isApproximate(r, k);
      fields.push({ label: k, value: withApproxMark(formatScalar(v), approx), warn: approx });
    }
  }
  // The record→chapter backlink resolves against the *active site's surfaced story* — none when
  // the site surfaces no story (a thin peer, or a site whose walk is held — `hidden` #1256 or
  // `comingSoon` #1526), so no walk chip.
  const anchor = activeStoryAnchorFor(r.rel);
  const c = r.citation;
  const groupName = groupLabel(r.group).replace(/ —.*$/, "");
  // The derivable connects: the record's group (its siblings) and, when it's a walk
  // anchor, the chapter that teaches it. Entity/concept/timeline/map chips await a
  // record↔graph join the records feed doesn't carry.
  const connect: BlockConnect[] = [
    {
      kind: "records",
      label: groupName,
      href: withSite(`/site/records/${r.group}/`),
    },
  ];
  if (anchor) {
    connect.push({
      kind: "walk",
      label: `Ch.${anchor.ch} · ${anchor.label}`,
      href: withStory(`/${anchor.slug}`),
    });
  }
  return {
    id: slugify(r.rel),
    kind: `Record · ${groupName}`,
    title: r.title,
    recordId: relRecordId(r.rel),
    evidence: evidenceKind(c),
    seenIn: anchor
      ? {
          ch: anchor.ch,
          label: anchor.label,
          href: withStory(`/${anchor.slug}`),
        }
      : undefined,
    fields,
    nested,
    approxPaths: r.approximate_paths,
    warnings: r.warnings,
    source: {
      file: c.source ?? r.rel,
      pages: c.page ? `p.${c.page}` : "—",
      collection: relCollection(r.rel),
    },
    // The record's own screen (/network/american-sugar-creek-allen-co/site/records/<group>/<id>) — the compact row links
    // here; the full block ignores it (it IS the screen).
    href: withSite(`/site/records/${r.group}/${slugify(r.rel)}`),
    correctHref: withSite(
      `/submit?ref_kind=record&ref_id=${encodeURIComponent(r.rel)}&ref_label=${encodeURIComponent(r.title)}`,
    ),
    connect,
  };
}
