/**
 * The **cross-site scorecard** — the shared row/cell/group grammar behind every "whole network on
 * one dimension" table (#1914, epic #1911 phase 2).
 *
 * `buildHypothesisView` grew this vocabulary for `/research/hypotheses`: grouped rows, typed cells,
 * a chip tail for the sites that carry no row, and an axis summary beside the framing panel. The
 * lens pages need exactly that shape over a different dimension, so the grammar is lifted here and
 * both surfaces consume it. The alternative — a second copy — would drift on the first change to
 * either, and the two are supposed to *look like the same table* precisely because they are the
 * same network read two ways.
 *
 * ## The one honest difference, carried by the primitive
 *
 * A hypothesis row may say *"not yet assessed under this thesis"*. That is a real evidentiary
 * position: the thesis has a verdict to reach at that site and has not reached it. **A lens row may
 * not.** A lens carries no verdict (epic #1911), so a site with no data for it reads *"not on the
 * record here"* — a statement about the corpus, never about the site. Leaving that to a caller-
 * supplied string would make it a copy-editing accident; {@link TailClaim} makes it a declaration.
 *
 * ## Measured, unmeasured, and never fabricated
 *
 * Inherited verbatim from the network baseline (#1220/#1861), and the reason {@link figure} exists
 * rather than a bare `String(n)`:
 *
 *  - a real `0` is a **measurement** and renders as `0`
 *  - `null` means **nothing was measured** (no committed bundle) and renders as a muted dash
 *  - the two are different claims and neither may be collapsed into the other — a fabricated zero
 *    reads as a cleared verdict, and a dash over a real zero understates the assembled record
 *
 * Pure (no bundle read), like `directory.ts`: callers thread bundle-backed lookups in as resolvers.
 *
 * What deliberately did NOT move here is `SIGNAL_META` — the anchor/strong/moderate/watch swatches.
 * That is a *verdict* vocabulary, and keeping it in `directory.ts` is what stops a lens surface
 * from reaching for it: this module can render a lens table, and nothing in it can render a signal.
 */
import type { SiteTier } from "./bundle";
import { type NetworkSite, siteBadge, type SiteStatus } from "./sites";

/** A pill's four colors: ink, fill, and the dot that leads it. */
export interface Swatch {
  label: string;
  color: string;
  bg: string;
  dot: string;
}

/** Build-phase pill swatches (the hex peer of `SITE_STATUS_META`'s CSS classes — the scorecard
 *  renders pills inline, like the facility pill, rather than through the switcher's class set). */
export const PHASE_PILL: Record<SiteStatus, Swatch> = {
  live: { label: "Live", color: "#1f6f4a", bg: "#e4ece4", dot: "#1f6f4a" },
  building: { label: "Building", color: "#1f6f4a", bg: "#e4ece4", dot: "#1f6f4a" },
  queued: { label: "Queued", color: "#9a6a14", bg: "#efe6d0", dot: "#9a6a14" },
  tracking: { label: "Tracking", color: "#566159", bg: "#e8e4d8", dot: "#8c9389" },
};

/** Readiness-tier pill swatches (#1861) — the manifest `readiness.tier`, a THIRD clock beside the
 *  build phase (our progress on the website) and the facility status (the plant in the ground).
 *  This one is neither: it is how much record the site's own export has actually assembled, and
 *  unlike the other two it is computed at every export rather than hand-maintained. */
export const TIER_PILL: Record<SiteTier, Swatch> = {
  reference: { label: "Reference", color: "#1f6f4a", bg: "#e4ece4", dot: "#1f6f4a" },
  case: { label: "Case", color: "#1f6f4a", bg: "#e4ece4", dot: "#3f8a63" },
  backdrop: { label: "Backdrop", color: "#566159", bg: "#e8e4d8", dot: "#8c9389" },
  stub: { label: "Stub", color: "#8c9389", bg: "#faf8f1", dot: "#cdc8b8" },
};

/** The readiness tiers deepest-first — the one place that order is written down, so the home
 *  ledger's tier bar, `featuredSites`'s ranking, and the lens scorecard's grouping can't drift
 *  apart (or from the tier vocabulary) the way three hand-kept literals would. */
export const TIER_DEPTH_ORDER: readonly SiteTier[] = ["reference", "case", "backdrop", "stub"];

/** A three-letter group tag for each tier — the scorecard's `abbr`, kept beside the order. */
export const TIER_ABBR: Record<SiteTier, string> = {
  reference: "REF",
  case: "CAS",
  backdrop: "BCK",
  stub: "STB",
};

// --- the rendered view model --------------------------------------------------------------

/** One chip in the framing panel's axis summary. */
export interface AxisGroup {
  label?: string;
  chips: { name: string; count: number }[];
}

export type CellKind = "site" | "text" | "num" | "pill";

export interface Cell {
  kind: CellKind;
  // site
  badge?: string;
  place?: string;
  badgeBg?: string;
  badgeColor?: string;
  // text / num
  text?: string;
  muted?: boolean;
  // pill
  pill?: Swatch;
}

export interface Row {
  slug: string;
  /**
   * Where the row goes: the site's OWN page (#1862). The registry href — Lima → `SITE_BASE`,
   * every other site → `/network/<slug>` — carried through **without** the deploy base, which
   * the page applies at render with `withBase`, exactly as the switcher does. Every registered
   * site has a real destination (`[site].astro` renders the non-selectable ones), so a `queued`
   * or `tracking` row lands on its watch page rather than a dead end.
   */
  href: string;
  live: boolean;
  cells: Cell[];
}

/**
 * What a chip tail CLAIMS about the sites in it — the one place the two surfaces genuinely differ,
 * declared rather than left to whichever label a template happened to type.
 *
 *  - `unassessed` — a **hypothesis** state, and the only one that is an evidentiary position: the
 *    thesis has a verdict to reach at this site and has not reached it. Not the same as cleared.
 *  - `unrecorded` — the only thing a **lens** may say. A lens carries no verdict, so this is a
 *    statement about the corpus ("nothing on this dimension is on the record here"), never about
 *    the site, and never about whether anything is happening there.
 *  - `unmeasured` — no committed bundle at all, so nothing has been measured. Distinct from a
 *    measured zero and never collapsed into one (#1861).
 */
export type TailClaim = "unassessed" | "unrecorded" | "unmeasured";

export const TAIL_META: Record<TailClaim, { label: string; note: string }> = {
  unassessed: {
    label: "Not yet assessed under this thesis",
    note: "Sites without an entry are not yet assessed under this thesis — that is not the same as cleared.",
  },
  unrecorded: {
    label: "Not on the record here",
    note:
      "A statement about the corpus, not about the site: nothing on this dimension has been " +
      "assembled here yet. A lens reaches no verdict, so this is never a finding about the place.",
  },
  unmeasured: {
    label: "No bundle committed yet",
    note: "Registered, but nothing has been exported for it — nothing measured, which is not a zero.",
  },
};

export interface Group {
  kind: "rows" | "chips";
  abbr: string;
  label: string;
  count: number;
  /** Set on the first group of a super-group — the banner rendered above it (H1's divides). */
  banner?: { label: string; note: string };
  rows: Row[];
  /** A site carrying no row. It routes like a row (#1862) — having nothing to say about a site
   *  under one reading is not a reason to strand it. */
  chips: { place: string; dot: string; href: string }[];
  /** Required on a `chips` group: what the tail claims about the sites in it. */
  claim?: TailClaim;
}

/** A column header. */
export interface ColumnSpec {
  label: string;
  align?: "right";
}

/** The scorecard's full view model — what a template renders, with no further decisions in it. */
export interface ScorecardView {
  axisTitle: string;
  axisGroups: AxisGroup[];
  cols: { label: string; align: "left" | "right" }[];
  gridCols: string;
  groups: Group[];
}

// --- cell constructors ---------------------------------------------------------------------

export const siteCell = (s: NetworkSite): Cell => {
  const live = s.status === "live";
  const codename = Boolean(s.codename);
  return {
    kind: "site",
    badge: siteBadge(s),
    place: s.place,
    badgeBg: live ? "#1f6f4a" : codename ? "#ece8dc" : "#e8e4d8",
    badgeColor: live ? "#f5f2ea" : codename ? "#1f6f4a" : "#566159",
  };
};

export const textCell = (t: string, muted = false): Cell => {
  const empty = !t || t === "—";
  return { kind: "text", text: t || "—", muted: muted || empty };
};

export const numCell = (t: string): Cell => ({ kind: "num", text: t, muted: t === "—" });

export const pillCell = (s: Swatch): Cell => ({ kind: "pill", pill: s });

/**
 * A rolled-up figure for the scorecard: thousands-separated, or "—" when nothing was measured
 * (`null` = no committed bundle). A real 0 renders as "0" — it is a measurement, not a gap.
 */
export const figure = (n: number | null): string => (n === null ? "—" : n.toLocaleString("en-US"));

/** Column headers with their alignment defaulted — the shape a template iterates. */
export const columnHeads = (cols: readonly ColumnSpec[]): ScorecardView["cols"] =>
  cols.map((c) => ({ label: c.label, align: c.align ?? ("left" as const) }));
