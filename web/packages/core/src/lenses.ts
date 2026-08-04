/**
 * The **Lens** model — the five standing ways to read a buildout (epic #1911, phase 1 · #1913).
 *
 * The directory asks one question — *what explains the data-center boom?* — and answers it with
 * three competing **hypotheses**. That is the wrong first question for somebody arriving at a
 * buildout in their own county: they want to know what it takes, what it costs, and who decided.
 * A lens is that second axis, ordered as the buildout's own causal chain — it takes **land**,
 * pulls **power**, consumes **water and air**, extracts **money**, through a **decision** the
 * public did not see.
 *
 * ## A lens never carries a verdict
 *
 * | | **Hypothesis** | **Lens** |
 * |---|---|---|
 * | Asks | *Why* is the buildout happening here? | *What does it do* to this place? |
 * | Scope | Network-wide, contested | Per-site, descriptive |
 * | Has a verdict? | **Yes** — confirmable or refutable | **Never** — a standing view |
 * | Backing data | `data/hypotheses/<id>/<site>.yaml` cells | existing feeds — no new store |
 * | Evidentiary weight | signal + tag + citation | inherits the underlying feed's tags |
 *
 * That fourth row is why this module is cheap: **a lens makes no claims**, so it has no signal,
 * no evidentiary tag, no citation, and no `(site × lens)` cell. There is nothing to commit under
 * `data/`, nothing to export, and nothing to version — no feed, no Python peer, no
 * `CONTRACT_VERSION` bump. Contrast `data/hypotheses/`, which exists precisely because a
 * hypothesis *does* assert something about a site and therefore owes provenance.
 *
 * **The tripwire: if a lens ever needs to assert something, it has become a hypothesis** and
 * belongs in `data/hypotheses/` with a cell store and citations. Do not grow an evidence store
 * here.
 *
 * ## Lens is a nav concept; section stays the gating concept
 *
 * They are allowed to be different granularities. `environment` and `economy` stay the gated
 * {@link ReadinessSection}s that map to manifest domains; a lens declares which of those sections
 * and which activation {@link Domain}s it stands on, and `readiness.ts` composes them in
 * `lensStatus()`. Nothing in the existing 14 readiness lines moves.
 *
 * Ids are deliberately the *existing* `ReadinessSection` / `StudyPart` / route vocabulary
 * (`environment`, `economy`), not fresh coinages — coining "Water & air" and "Money" for things
 * the codebase already calls the environment and the economy would repeat the exact mistake this
 * epic opens by fixing (#1912, which took "lens" back from the hypotheses).
 *
 * ## What a lens gathers
 *
 * `facets` are **existing leaf routes** — this is a view over them, not a new store, and no URL
 * moves. Two deliberate boundaries:
 *
 *  - **The long-form reports are not facets.** #1893 pulled `/reports/*` out of the Reference
 *    dropdown because they were already reachable from four places, and "a report is found at
 *    Reports" is the standing answer. Lenses gather the *data* leaves — the same set the
 *    Reference dropdown carries, plus the record facets. The menu question is phase 3's (#1915).
 *  - **Page boundaries do not align with lens boundaries, and the anchor is the honest seam.**
 *    `/economy/economics-baseline` renders the labor baseline (Economy) *and* the consumer-energy
 *    and household-burden reads (Power). Power gathers the anchor rather than the page, so a lens
 *    reaches only the part of a leaf it is actually a view over.
 *
 * A one-facet lens is a finding, not a defect: Power has exactly one data page today because, as
 * #1911 puts it, it "currently hides inside `economy`" — surfacing that thinness is the point.
 *
 * ## Presentation
 *
 * A lens's accent is one position on the **forest data ramp** (`--data-1` … `--data-5`), which is
 * what the ramp is for — it encodes position in the causal chain and nothing else. A lens takes
 * **no fill from the evidence palette** (`--ev-*`): that grammar encodes how well a figure is
 * sourced, and a lens has no evidentiary weight of its own to declare. The card sits on the
 * ordinary bone surface like any other panel.
 *
 * **Pure** — no bundle read, so it unit-tests offline (the discipline `directory.ts` holds). Its
 * only sibling import is `import type`, which erases; the bundle-backed gate lives in
 * `readiness.ts`.
 */
import type { Domain, ReadinessSection, RecordFacet } from "./readiness";

/** The five lenses. Ids reuse the existing section/route vocabulary — never a fresh coinage. */
export type LensId = "land" | "power" | "environment" | "economy" | "disclosure";

/**
 * Reading order — the buildout's own causal chain, not an alphabet and not a ranking. Land is
 * taken first and the decision that authorized it is disclosed last (often only in hindsight),
 * which is why `disclosure` closes rather than opens the set.
 */
export const LENS_ORDER: readonly LensId[] = ["land", "power", "environment", "economy", "disclosure"];

/** One existing leaf route a lens is a view over. Never a new destination. */
export interface LensFacet {
  /** The leaf's own name — the page's name, not the lens's framing of it. */
  label: string;
  /**
   * Route under `/network/<site>`, with NO deploy base and no site prefix (the caller applies
   * `siteBase(slug)` + `withBase`, exactly as the nav does). May carry an `#anchor` when the lens
   * is a view over one band of a shared page rather than the whole leaf.
   */
  route: string;
  blurb: string;
  /**
   * The declared {@link RecordFacet} this leaf IS, when it is one — so a caller can gate the leaf
   * with `facetStatus()` instead of re-deriving the rule. `lenses.test.ts` pins the route against
   * `RECORD_FACETS` so the two can't drift.
   */
  facet?: RecordFacet;
  /**
   * Feeds that gate whether the lens landing OFFERS this door at all (#1915): the door is shown
   * when the site's bundle carries **any** of them. Omitted where the leaf is unconditional —
   * either it renders its own honest absence (hydrology, RSEI, the labor baseline) or a
   * {@link facet} declaration already carries the gate.
   *
   * This is a *door* gate, not a page gate: the leaf route itself is unchanged and still handles
   * its own empty state. What it prevents is the landing advertising a door onto a lock.
   */
  requires?: readonly string[];
}

/** A lens's mark on the forest data ramp. No evidence-palette fill — see the module docstring. */
export interface LensAccent {
  /** The hex, for the inline-swatch call sites (`directory.ts`'s convention). */
  mark: string;
  /** The CSS custom property behind `mark` — prefer this in templates. */
  token: string;
}

export interface Lens {
  id: LensId;
  /** Front-matter numbering for the wayfinding line ("02 · Power"), zero-padded to the set. */
  number: string;
  name: string;
  /** The reader's question, in the reader's words. A question — never a claim. */
  question: string;
  blurb: string;
  /** The bundle feeds this reading rests on. Descriptive: nothing gates on the list. */
  feeds: readonly string[];
  /** The readiness SECTIONS whose gate this lens inherits (composed by `sectionStatus`). */
  sections: readonly ReadinessSection[];
  /**
   * Whose lock copy the lens borrows when it is locked on a site (#1915) — the peer of
   * `FacetDeclaration.section`. A lens has no `SECTION_META` of its own because it is a view, not
   * a gate; the heading still reads the LENS's name, so the borrowed part is only the "what lands
   * here once we have sources" line.
   */
  lockSection: ReadinessSection;
  /** The activation DOMAINS that must carry evidence here (composed by `domainPresent`). */
  domains: readonly Domain[];
  /** The existing leaf routes this lens gathers. */
  facets: readonly LensFacet[];
  accent: LensAccent;
}

export const LENSES: Record<LensId, Lens> = {
  land: {
    id: "land",
    number: "01",
    name: "Land",
    question: "What ground did this take, and how was it assembled?",
    blurb:
      "A campus is first a land transaction. The parcels, the assemblage, and the footprint on the ground — who held the land before, what it was zoned for, and how the pieces were put together. Deeds, plats, and dated aerials are where an assemblage becomes legible after the fact.",
    feeds: ["places", "geo", "enclave"],
    sections: [],
    lockSection: "places",
    domains: ["places"],
    facets: [
      {
        label: "Places & parcels",
        route: "/site/places/",
        blurb: "Per-parcel profiles drawn from this site's own record",
        facet: "places",
      },
      {
        label: "Watershed map",
        route: "/environment/map",
        blurb: "The assembled footprint against the drainage — typed GeoJSON on deck.gl",
      },
      {
        label: "Imagery",
        route: "/environment/imagery",
        blurb: "Dated aerials — the ground before and after",
        requires: ["geo/imagery"],
      },
      {
        label: "Federal enclave",
        route: "/environment/enclave",
        blurb: "Land held by the United States and off the county tax rolls (the DoD MIRTA register)",
        requires: ["enclave"],
      },
    ],
    accent: { mark: "#1f6f4a", token: "--data-1" },
  },
  power: {
    id: "power",
    number: "02",
    name: "Power",
    question: "Whose grid carries it, and who pays for the wires?",
    blurb:
      "Load sits upstream of both the environmental draw and the fiscal trade — the megawatts decide the water, and the transmission decides the bill. The balancing authority, the interconnection, the fuel mix behind the load, and what households on the same grid already pay.",
    feeds: ["grid", "consumer-energy", "energy-burden", "facility"],
    sections: ["economy"],
    lockSection: "economy",
    domains: ["facility"],
    facets: [
      {
        label: "The grid backdrop",
        route: "/economy/grid",
        blurb: "Whose grid, cited — the balancing authority, the queue, and the fuel mix",
        requires: ["grid"],
      },
      {
        label: "Consumer energy & burden",
        route: "/economy/economics-baseline#consumer-energy",
        blurb: "What households on this grid already pay, before the campus is added",
        requires: ["consumer-energy", "energy-burden"],
      },
    ],
    accent: { mark: "#3f8a63", token: "--data-2" },
  },
  environment: {
    id: "environment",
    number: "03",
    name: "Environment",
    question: "What does it take from and put into the ground, water, and air?",
    blurb:
      "Withdrawal, discharge, drawdown, runoff, heat, and toxics — the receiving water and air, screened against the criteria that actually govern them. Where the record brackets a figure rather than settling it, the bracket stands as the answer.",
    feeds: [
      "hydrology-scenarios",
      "drawdown",
      "dewatering",
      // Both halves of the flow read: the reach geometry the particles advect along, and the
      // routed peak that sets their density and speed.
      "reach-network",
      "routed-hydrograph",
      "water-seasonal-field",
      "thermal",
      "rsei",
      "air-dispersion-field",
      "greenops",
    ],
    sections: ["environment"],
    lockSection: "environment",
    domains: [],
    facets: [
      {
        label: "Hydrology",
        route: "/environment/hydrology",
        blurb: "Low-flow dilution against the 7Q10",
      },
      {
        label: "Groundwater",
        route: "/environment/groundwater",
        blurb: "Well drawdown and construction dewatering",
        requires: ["drawdown", "dewatering"],
      },
      {
        label: "Seasonal withdrawal",
        route: "/environment/seasonal",
        blurb: "Month-by-month climograph — the summer window, not the annual average",
        requires: ["water-seasonal-field"],
      },
      {
        label: "Water flow",
        route: "/environment/flow",
        blurb: "Animated reach-network flow through the routed hydrograph",
        requires: ["reach-network"],
      },
      {
        label: "Thermal / §316(a)",
        route: "/environment/thermal",
        blurb: "Discharge heat against the temperature criterion",
        requires: ["thermal"],
      },
      { label: "RSEI / toxics", route: "/environment/rsei", blurb: "EPA toxic-release inventory" },
      {
        label: "Air dispersion",
        route: "/environment/air",
        blurb: "AERMOD screening field",
        requires: ["air-dispersion-field"],
      },
    ],
    accent: { mark: "#5fa07f", token: "--data-3" },
  },
  economy: {
    id: "economy",
    number: "04",
    name: "Economy",
    question: "What did it cost the public, and what came back?",
    blurb:
      "Both sides of the ledger, each cited to the instrument that created it: the abatement and the PILOT on one side, and on the other the local employment baseline the jobs claim has to be measured against.",
    feeds: ["economics-baseline", "greenops"],
    sections: ["economy"],
    lockSection: "economy",
    domains: [],
    facets: [
      {
        label: "Localized labor baseline",
        route: "/economy/economics-baseline",
        blurb: "BLS QCEW · Census — the employment a jobs claim is measured against",
      },
    ],
    accent: { mark: "#8fbca0", token: "--data-4" },
  },
  disclosure: {
    id: "disclosure",
    number: "05",
    name: "Disclosure",
    question: "How was the decision made, and what was withheld?",
    blurb:
      "The documents, the meetings, the filings, and the records requests behind them — the decision's paper trail, and the gaps in it named as gaps. An absent record is a finding, not a blank.",
    feeds: ["documents", "records", "meetings", "exhibits", "people", "timeline"],
    sections: [],
    lockSection: "record",
    domains: ["record"],
    facets: [
      {
        label: "Documents",
        route: "/site/documents/",
        blurb: "The source-document catalog, as received",
        facet: "documents",
      },
      {
        label: "Records",
        route: "/site/records/",
        blurb: "Structured extractions from this site's own corpus",
        facet: "records",
      },
      {
        label: "Timeline",
        route: "/timeline",
        blurb: "Every dated event reconstructed from the record, ordered",
        facet: "timeline",
      },
      {
        label: "Exhibits",
        route: "/site/exhibits",
        blurb: "The documents that carry the keystone figures",
        facet: "exhibits",
      },
      {
        label: "People",
        route: "/site/people/",
        blurb: "The actors the record names, tied back to the pages that name them",
        facet: "people",
      },
      {
        label: "Legal history",
        route: "/site/legal/",
        blurb: "Filings, hearing transcripts, and records-access analyses out of this site's corpus",
        facet: "legal",
      },
      {
        label: "Reference data",
        route: "/site/reference/",
        blurb: "The external datasets this site owns",
        facet: "reference",
      },
    ],
    accent: { mark: "#bcd2c4", token: "--data-5" },
  },
};
