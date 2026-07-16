/**
 * The Record Teardown — the guided walk's signature teaching component
 * (design handoff: "The Record Teardown"). A teardown is a *curated framing* of
 * one corpus record: pick a record, write three sentences. The structured
 * fields still come from the same feeds the library reads — the data never
 * forks. This module is the editorial shape the `<RecordTeardown>` component
 * renders; it mirrors the design's `RecordRow`.
 */

/** The canonical evidence-tag data vocabulary lives in `./evidence` (#579). Imported + re-exported
 *  here for the teardown/viz/profile consumers that already pull `TagKind` from this module. */
import type { TagKind } from "./evidence";

export type { TagKind };

export type TeardownLayout = "split" | "scroll" | "annotated";

/**
 * A committed scan crop of the real document region — a small raster (PNG under
 * `public/`, NOT the LFS source PDF) that retires the placeholder ghost. The
 * `redaction` overlay marks the blank / CBI box so "the blank is the evidence"
 * is *visible*; the interactive reveal on top of it is #220.
 */
export interface TeardownScanCrop {
  /** App-relative path to the committed PNG (the component wraps it in withBase),
   *  e.g. "/walk/crops/opc-summary.png". A raster, never the LFS source binary. */
  src: string;
  /** Accessible description of what the crop shows (the real region). */
  alt: string;
  /** Caption under the crop — typically the page/sheet locator. */
  caption?: string;
  /** Highlight box over the blank/CBI region, as percentages of the image box. */
  redaction?: { x: string; y: string; w: string; h: string; label?: string };
}

/**
 * The redaction-reveal (#220) — the corpus's signature move surfaced as a teaching
 * object: a deliberate blank / CBI lock IS the finding. Rendered as a native
 * `<details>` disclosure (no-JS: the box + label are SSR, the lock/clause cites in
 * the open content), it shows *why* a value is withheld — **never a fabricated
 * value behind the box**.
 */
export interface TeardownRedaction {
  /** The box label, e.g. "REDACTED · CBI" / "$ ______ · withheld". */
  label: string;
  /** The disclosure trigger, e.g. "Why won't the permit say?". */
  summary: string;
  /** The operative grant / clause / blank-fact that locks the value (cited). */
  lock: string;
  /** Where the lock lives — statute + document locator. */
  cite: string;
  /** Plain-language read: what's withheld and why it matters — NOT the value. */
  read: string;
  /** Optional deep link to the governing record / document. */
  href?: string;
  /** Optional committed crop of the actual blank/CBI region, shown in the reveal. */
  crop?: TeardownScanCrop;
}

export interface TeardownSource {
  /** Source filename, shown in the document chrome. */
  file: string;
  /** Page / clause locator, e.g. "pp. 317–328" or "§5.5 · §9.13". */
  pages: string;
  /** Collection the source lives in. */
  collection: string;
  /** Character of the source, e.g. "Scanned PDF · degraded OCR". */
  kind: string;
  /** One line on why the binary isn't shown (the cloud deploy skips LFS). */
  note: string;
  /** Top-right marker on the source card (default "SCAN"). */
  badge?: string;
  /** Optional real link to the materialized exhibit/source. */
  href?: string;
  /** Committed scan crop of the real region; when present the source viewer shows
   *  it instead of the real-extraction facsimile. */
  scanCrop?: TeardownScanCrop;
}

/** Presentation unit applied to a feed-sourced numeric figure. The digits come
 *  from the bundle (no fork); the unit/grouping is display only. */
export type TeardownUnit = "usd" | "pct" | "tpy" | "cfs" | "count" | "raw";

export interface TeardownRow {
  label: string;
  /** Curated display value — the fallback when no `path`, or when the record
   *  isn't in the bundle / the path doesn't resolve. */
  value: string;
  /** Render the value as a scope-gap / approximate flag (red). */
  warn?: boolean;
  /**
   * Dotted path into the anchor record's `fields` (e.g. "consideration",
   * "facility_wide_limits.nox_tpy"). When the teardown's `recordRel` is in the
   * bundle and this path resolves, the figure is read from the live `records`
   * feed (the same value the library renders) and formatted with `unit` — so a
   * load-bearing number can never fork from the source. Rows without a `path`
   * are editorial framing and always render their curated `value`.
   */
  path?: string;
  /** Presentation unit for a feed-sourced numeric `path` value (default "raw"). */
  unit?: TeardownUnit;
  /** Set by the resolver to true when `value` was sourced live from the feed. */
  live?: boolean;
}

export interface TeardownPin {
  n: number;
  label: string;
  value: string;
  /** Scope gap / redaction — renders red instead of forest. */
  danger?: boolean;
  /** CSS offset over the artifact, e.g. "44px". */
  x: string;
  y: string;
}

export interface TeardownReveal {
  /** Prose before the load-bearing figure. */
  lead: string;
  /** The highlighted load-bearing figure. */
  key: string;
  /** Prose after the figure. */
  tail: string;
}

export interface TeardownCheck {
  tag: TagKind;
  /** Short qualifier on the tag, e.g. "totals" / "executed text". */
  sub: string;
  verify: string;
  verifyHref?: string;
  method: string;
  methodHref?: string;
}

export interface TeardownConnect {
  /** Library door type, e.g. "entity" / "timeline" / "concept" / "map". */
  kind: string;
  label: string;
  href?: string;
}

export interface TeardownRecord {
  title: string;
  docName: string;
  source: TeardownSource;
  extraction: TeardownRow[];
  /** Numbered annotations for the `annotated` layout. */
  pins?: TeardownPin[];
  reveal: TeardownReveal;
  check: TeardownCheck;
  connect: TeardownConnect[];
  /** Renders a redaction bar on the artifact (the `annotated` layout). */
  redactionLabel?: string;
  /** The interactive redaction-reveal (#220): the deliberate blank / CBI lock as
   *  the finding. Rendered as a no-JS `<details>` below the source card. */
  redaction?: TeardownRedaction;
  /**
   * `rel` of the backing row in the live `records` feed (e.g.
   * "recorder/202508130008300.deed.yaml"). When that row is present in the bundle
   * being built, the teardown's `verify` deep-links to the exact record and the
   * source card confirms the bundle's own citation — the data never forks. Absent
   * from the bundle (e.g. the minimal CI fixture) → graceful fallback to the
   * curated link. See `resolveTeardown`.
   */
  recordRel?: string;
  /**
   * Slug of the backing page in the legal-history collection (`lib/legal.ts`),
   * for teardowns whose anchor is an agreement/analysis rather than a `records`
   * row. Deep-links `verify` to `/network/american-sugar-creek-allen-co/site/legal/<slug>` when that page exists.
   */
  legalSlug?: string;
}
