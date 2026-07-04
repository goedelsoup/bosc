/**
 * Curated Record Teardowns for the guided walk — the editorial framings of the
 * corpus's anchor records (the deed, the SoS cluster, the air permit, the Tetra
 * Tech OPC, the NPDES fact sheet, the RDA, the withholding stack). The framing
 * (reveal/tag/pins/connect) is curated; the **load-bearing figures are bound to
 * the live `records` feed** via a row's `path` (#218), so a checkable number can
 * never fork from the source — `resolveTeardown` reads the value from the bundle
 * at build time and the curated `value` is only the fallback (no `recordRel`, not
 * in the bundle, or the path absent — the CI fixture path). The `① source` panel
 * likewise shows the record's real extraction, not a placeholder. `connect` chips
 * and `verify`/`method` links are library doors into the reference indexes.
 */

import type { TeardownRecord } from "./teardown";
import { withBase, withSite } from "./site";

/**
 * The withholding stack — Ch. 5 anchor ("Why you had to dig for this"), the
 * close. Grounded in `data/extracted/legal/prr-mandamus/records-withholding-map.yaml`:
 * seven lawful-looking layers (R.C. 4582.58 shield, NDA §6(f) / RDA §9.13
 * developer-notice, CRA §22 indemnity, ORC 121.22(G)(8) closed sessions, the
 * withheld cost-benefit item 4, blank-figure production, the SWCD 149.433 /
 * 1333.61 branch). The clauses and statutes are [verified] from committed
 * extractions; the "engineered system" reading is argument, flagged as such by
 * the record itself. Uses the `annotated` layout (statutes as pins on a withheld
 * production).
 */
export const OPACITY_TEARDOWN: TeardownRecord = {
  title: "The withholding stack",
  docName: "Project BOSC · the layered records-withholding architecture",
  source: {
    file: "records-withholding-map.yaml",
    pages: "7 layers · NDA / RDA / CRA + statutes",
    collection: "Legal · PRR / mandamus",
    kind: "Consolidated from committed extractions",
    badge: "PRR",
    note: "Each clause and statute is transcribed from a committed extraction; the 'engineered system' reading is argument, and the record labels it as such.",
  },
  extraction: [
    { label: "Front-end shield", value: "R.C. 4582.58 non-record" },
    { label: "Developer-notice (County)", value: "NDA §6(f) · ≥10 days" },
    { label: "Developer-notice (Authority)", value: "RDA §9.13 · ≥5 days" },
    { label: "Fee-shift indemnity", value: "CRA §22" },
    { label: "Closed deliberation", value: "ORC 121.22(G)(8) · 2025-05-27" },
    { label: "Cost-benefit analysis", value: "~ withheld · item 4", warn: true },
    { label: "Land prices / school terms", value: "~ blank in production", warn: true },
  ],
  pins: [
    {
      n: 1,
      label: "Deliberated in closed session — first used for this very CRA",
      value: "ORC 121.22(G)(8) · 2025-05-27",
      x: "40px",
      y: "52px",
    },
    {
      n: 2,
      label: "Three developer-notice / indemnity clauses: tip off, minimize, insulate",
      value: "NDA §6(f) · RDA §9.13 · CRA §22",
      x: "158px",
      y: "150px",
    },
    {
      n: 3,
      label: "The deciding analysis — withheld",
      value: "cost-benefit · item 4",
      danger: true,
      x: "78px",
      y: "224px",
    },
  ],
  redactionLabel: "WITHHELD · item 4",
  redaction: {
    label: "item 4 · WITHHELD",
    summary: "Where's the cost-benefit analysis?",
    lock: 'PRR item 4 — the cost-benefit analysis, projected tax-revenue impact, and public-ROI inputs — was withheld: "being reviewed by our legal counsel for compliance with R.C. 149.43 and R.C. 9.66." Held under R.C. 9.66(D).',
    cite: "PRR item 4 · corpus-completeness-audit.md · R.C. 9.66(D) economic-development trade-secret exemption",
    read: "The single analysis that would weigh the 75% / 15-year abatement against the public return was not produced. Items 5–15 came in a later batch; item 4 — the one that scores whether the deal pays — is the one still withheld. The deciding number is the one the record won't show.",
  },
  reveal: {
    lead: "No single refusal hides this deal — a stack of seven lawful-looking layers does, from a statutory non-record shield to closed sessions to a production that returns the deciding figures ",
    key: "blank or not at all",
    tail: ". Each layer stands on its own; the audit can call the whole an engineered system only as argument, not as record. And yet — read together, the thin record still reassembles the project. That reassembly is the point of the story.",
  },
  check: {
    tag: "verified",
    sub: "clauses cited · the “system” is argument",
    verify: "Open the withholding map & PRR analysis",
    verifyHref: withSite("/site/legal/"),
    method: "How to read a statutory exemption",
    methodHref: withBase("/methodology"),
  },
  connect: [
    { kind: "concept", label: "[[public-records-mandamus]]", href: withBase("/wiki/concepts/") },
    {
      kind: "legal",
      label: "the PRR production analysis",
      href: withSite("/site/legal/"),
    },
    { kind: "entity", label: "Cynthia Leis", href: withBase("/wiki/entities/") },
    {
      kind: "timeline",
      label: "2025-05-27 · first closed session",
      href: withSite("/timeline"),
    },
  ],
  legalSlug: "withholding-map",
};

/**
 * Recorded deed — Ch. 1 anchor part 1 ("Who is actually building this?").
 * Grounded in `data/extracted/recorder/202508130008300.deed.yaml`: Brenneman
 * Living Trusts → BISTROZZI LLC (Delaware), 7 parcels, consideration NOT stated
 * ("valuable consideration paid"), grantee mailing a Wilmington PMB, instrument
 * prepared by Jill Tangeman of Vorys. All [verified] from the recorded instrument.
 */
export const DEED_TEARDOWN: TeardownRecord = {
  title: "Limited Warranty Deed 202508130008300",
  docName: "Brenneman Living Trusts → Bistrozzi LLC · recorded 2025-08-13",
  source: {
    file: "202508130008300.pdf",
    pages: "8 pp. + Exhibits A–E",
    collection: "Allen County Recorder · Bistrozzi deeds",
    kind: "Recorded deed · scanned (200 DPI)",
    badge: "DEED",
    note: "The recorded instrument is public; the scan is committed as provenance and available on request.",
  },
  extraction: [
    { label: "Instrument", value: "Limited Warranty Deed", path: "instrument_type" },
    { label: "Recorded", value: "2025-08-13", path: "recording_date" },
    { label: "Grantor", value: "Brenneman Living Trusts ×2" },
    { label: "Grantee", value: "BISTROZZI LLC · Delaware" },
    { label: "Parcels", value: "7 · §12 American Twp" },
    { label: "Grantee address", value: "PMB 811, Wilmington DE" },
    { label: "Consideration", value: "~ none stated", warn: true },
  ],
  reveal: {
    lead: "Seven adjoining parcels pass from two family trusts to a Delaware LLC for ",
    key: "no stated price",
    tail: " — the deed records only “valuable consideration paid.” The grantee's mailing address is a Wilmington mailbox, and the instrument was drawn by the same Columbus firm that represents the project. The land is assembled; who's behind the buyer is the next question.",
  },
  check: {
    tag: "verified",
    sub: "recorded instrument",
    verify: "Open the deed · instrument 202508130008300",
    verifyHref: withSite("/site/records/"),
    method: "How we read a deed",
    methodHref: withBase("/methodology"),
  },
  connect: [
    { kind: "entity", label: "Bistrozzi LLC", href: withBase("/wiki/entities/") },
    { kind: "entity", label: "Vorys (Tangeman)", href: withBase("/wiki/entities/") },
    {
      kind: "timeline",
      label: "2025-08-13 · deed recorded",
      href: withSite("/timeline"),
    },
    { kind: "graph", label: "land assembly", href: withBase("/wiki/graph") },
  ],
  redaction: {
    label: "$ ______ · blank",
    summary: "What did they pay for the land?",
    lock: 'The DTE-100 conveyance-fee statement — the one form that records a sale price — was produced with its value lines (1–9) left blank; the recorded deed recites only "valuable consideration paid."',
    cite: "DTE-100 · PRR-01-bundle p.158 (Brenneman packet) · deed 202508130008300 · DTE-102 CAUV recoupment p.159",
    read: "Across both instruments that would carry the figure — the deed and the conveyance-fee statement — the price is absent, not unknown to the parties. The land was CAUV farmland, so converting it triggers tax recoupment; yet only the Neighbors parcel's price is disclosed anywhere. What the public's development authority paid to assemble this campus is the blank.",
    crop: {
      src: "/walk/crops/dte100-blank.png",
      alt: "Brenneman DTE-100 Real Property Conveyance Fee Statement of Value — the numbered value lines 1 through 9 with the dollar column produced blank.",
      caption: "DTE-100 value lines · produced blank",
      redaction: { x: "68%", y: "5%", w: "19%", h: "88%", label: "$ blank" },
    },
  },
  recordRel: "recorder/202508130008300.deed.yaml",
};

/**
 * Delaware shell cluster — Ch. 1 anchor part 2. Grounded in the three Ohio SoS
 * foreign-LLC registrations in the corpus (`sos-tilted-gate-llc`,
 * `sos-magenta-capital-llc`, `sos-bistrozzi-addition-llc`): Tilted Gate and
 * Magenta share the same registered agent (CSC) AND organizer (Michael
 * Montfort); all are Delaware; Bistrozzi/Bistrozzi Addition tie in through Vorys
 * and the Wilmington PMB. The overlaps are SIGNALS of common-control plumbing —
 * the check is honestly tagged [inference], not a verdict on ownership.
 */
export const SHELL_TEARDOWN: TeardownRecord = {
  title: "Delaware shell cluster — SoS filings",
  docName: "Ohio Secretary of State · foreign-LLC registrations · 2025–2026",
  source: {
    file: "sos-tilted-gate-llc-2025-09-29.pdf",
    pages: "Form 617 · read with Magenta + Bistrozzi Addition",
    collection: "Ohio Secretary of State · foreign-LLC filings",
    kind: "State filings · text-native",
    badge: "SoS",
    note: "Three public SoS registrations read together; committed as provenance and available on request.",
  },
  extraction: [
    { label: "Bistrozzi LLC", value: "Delaware · Wilmington PMB" },
    { label: "Bistrozzi Addition LLC", value: "DE · CT Corp · Ziance" },
    { label: "Tilted Gate LLC", value: "DE · CSC · Montfort" },
    { label: "Magenta Capital LLC", value: "DE · CSC · Montfort" },
    { label: "Shared agent + organizer", value: "Tilted Gate = Magenta" },
    { label: "Common counsel", value: "Vorys · Ziance / Tangeman" },
  ],
  reveal: {
    lead: "Four Delaware LLCs orbit the project, and two of them — Tilted Gate and Magenta Capital — share both the ",
    key: "same agent and organizer",
    tail: ". That is a signal of common-control plumbing, not proof of beneficial ownership: it shows coordination, and it marks exactly where to look next. The story's entity graph draws the overlaps so you can see them at once.",
  },
  check: {
    tag: "inference",
    sub: "signals, not a verdict",
    verify: "Open the SoS filings",
    verifyHref: withSite("/site/records/"),
    method: "Signals vs. verdicts",
    methodHref: withBase("/methodology"),
  },
  connect: [
    { kind: "entity", label: "Tilted Gate LLC", href: withBase("/wiki/entities/") },
    { kind: "entity", label: "Michael Montfort", href: withBase("/wiki/entities/") },
    { kind: "concept", label: "[[common-control-plumbing]]", href: withBase("/wiki/concepts/") },
    { kind: "graph", label: "the cluster", href: withBase("/wiki/graph") },
  ],
  recordRel: "permits/sos-tilted-gate-llc-2025-09-29.sos.yaml",
};

/** Tetra Tech Opinion of Probable Cost — Ch. 4 anchor ("What it costs the public"). */
export const OPC_TEARDOWN: TeardownRecord = {
  title: "Opinion of Probable Cost",
  docName: "Tetra Tech · BOSC Roadwork · filed 2025-07-11",
  source: {
    file: "PRR-01-bundle.pdf",
    pages: "pp. 317–328",
    collection: "Public Records Request 01",
    kind: "Scanned PDF · degraded OCR",
    badge: "SCAN",
    note: "The summary sheet is shown as a committed crop of the source scan (regenerated by scripts/render_walk_crops.py); the full 11-sheet exhibit is available on request.",
    scanCrop: {
      src: "/walk/crops/opc-summary.png",
      alt: "Tetra Tech Opinion of Probable Project Cost — summary sheet: six corridor roundabout line items with a CONSTRUCTION TOTAL of $14,223,081.",
      caption: "summary sheet · sheet 1 of 11",
    },
  },
  extraction: [
    { label: "Program total", value: "$14,223,081", path: "meta.summary_construction_total", unit: "usd" },
    { label: "Sub-estimates", value: "6 corridors" },
    { label: "Contingency", value: "25%", path: "meta.contingency_and_inflation_pct", unit: "pct" },
    { label: "Largest — Cole St", value: "$3,899,800" },
    { label: "Drainage line", value: "$1,068,530 · 7.5%" },
    { label: "Design-storm basis", value: "~ not cited", warn: true },
    { label: "Detention shown", value: "~ none", warn: true },
  ],
  pins: [
    { n: 1, label: "Program total, priced to the dollar", value: "$14,223,081", x: "44px", y: "56px" },
    {
      n: 2,
      label: "Drainage — only 1 of 6 items itemized",
      value: "$1,068,530 · 7.5%",
      x: "150px",
      y: "150px",
    },
    {
      n: 3,
      label: "No design-storm basis · no detention",
      value: "scope gap",
      danger: true,
      x: "78px",
      y: "224px",
    },
  ],
  redactionLabel: "REDACTED · CBI",
  reveal: {
    lead: "The public's road package is priced to the dollar — ",
    key: "$14,223,081",
    tail: " — yet drainage is just 7.5% of it, the only one of six items detailed, with no design-storm basis and no detention shown. A number that precise on a scope that thin is the tell.",
  },
  check: {
    tag: "verified",
    sub: "totals",
    verify: "Open exhibit · pp. 317–328",
    verifyHref: withSite("/site/records/"),
    method: "Read the extraction method",
    methodHref: withBase("/methodology"),
  },
  connect: [
    { kind: "entity", label: "Tetra Tech", href: withBase("/wiki/entities/") },
    {
      kind: "timeline",
      label: "2025 · OPC filed",
      href: withSite("/timeline"),
    },
    { kind: "concept", label: "[[roadwork-development-agreement]]", href: withBase("/wiki/concepts/") },
    {
      kind: "map",
      label: "roundabout layer",
      href: withSite("/watershed/map"),
    },
  ],
  recordRel: "aedg/roundabouts.summary.opc.yaml",
};

/**
 * Ohio EPA Air Permit-to-Install P0138965 — Ch. 2 anchor ("How big is it — and
 * what won't they tell you?"). Grounded in the FINAL permit
 * (`data/extracted/permits/4132514.epa.yaml`, eDoc 4132514, issued 2026-05-28):
 * the unit counts and the NOx/CO caps are printed in the issued permit
 * [verified]; the per-engine ekW — and so the ~313 MW backup total — is redacted
 * as trade secret (Comments 16/19), which is why the chapter's check is [open].
 * Uses the `annotated` layout to show the redaction.
 */
export const AIR_TEARDOWN: TeardownRecord = {
  title: "Air Permit-to-Install P0138965",
  docName: "Ohio EPA · Division of Air Pollution Control · FINAL, issued 2026-05-28",
  source: {
    file: "4132514.pdf",
    pages: "issued PTI + 64-item Response to Comments",
    collection: "Ohio EPA · Air permits (eDoc 4132514)",
    kind: "Issued permit · text-native",
    badge: "PERMIT",
    note: "The 66-page issued eDocument is committed as provenance; engine make/model/size is redacted in the source itself as trade secret.",
  },
  extraction: [
    { label: "Emissions units", value: "115 · P001–P115" },
    { label: "Data-hall gensets", value: "114 · 3 groups of 38" },
    { label: "Cooling towers", value: "36 · 3 groups of 12" },
    { label: "NOx cap", value: "235.62 tpy", path: "facility_wide_limits.nox_tpy", unit: "tpy" },
    { label: "CO cap", value: "96.06 tpy", path: "facility_wide_limits.co_tpy", unit: "tpy" },
    { label: "Per-engine power (ekW)", value: "~ redacted · CBI", warn: true },
    { label: "Backup total", value: "~313 MW · draft only", warn: true },
  ],
  pins: [
    {
      n: 1,
      label: "Synthetic-minor caps, printed in the permit",
      value: "NOx 235.62 · CO 96.06 tpy",
      x: "40px",
      y: "52px",
    },
    {
      n: 2,
      label: "Three matched groups → three data halls",
      value: "114 gensets · 36 towers",
      x: "162px",
      y: "150px",
    },
    {
      n: 3,
      label: "Per-engine power withheld as trade secret",
      value: "ekW = REDACTED",
      danger: true,
      x: "78px",
      y: "224px",
    },
  ],
  redactionLabel: "REDACTED · CBI",
  reveal: {
    lead: "The permit fixes the plant's shape exactly — three matched groups of generators and cooling towers, ",
    key: "114 data-hall gensets",
    tail: " — yet locks the one number that sets its true scale, per-engine power, as a trade secret. The ~313 MW everyone cites is the draft public-notice figure; the issued permit will not confirm it.",
  },
  check: {
    tag: "open",
    sub: "per-engine ekW · trade secret",
    verify: "Open the permit · eDoc 4132514",
    verifyHref: withSite("/site/records/"),
    method: "How a CBI redaction works",
    methodHref: withBase("/methodology"),
  },
  connect: [
    { kind: "entity", label: "Bistrozzi LLC", href: withBase("/wiki/entities/") },
    {
      kind: "timeline",
      label: "2026-05-28 · permit issued",
      href: withSite("/timeline"),
    },
    { kind: "concept", label: "[[hyperscale-data-center]]", href: withBase("/wiki/concepts/") },
    {
      kind: "doc",
      label: "the bigger picture",
      href: withSite("/docs/bigger-picture"),
    },
  ],
  redaction: {
    label: "ekW · REDACTED · CBI",
    summary: "Why won't the permit say how big it is?",
    lock: "Engine make / model / size — and so the per-engine ekW that sets the plant's true electrical scale — is claimed as a trade secret and withheld from the issued permit.",
    cite: "Air PTI eDoc 4132514 · Response to Comments 16 & 19 · trade-secret / CBI under ORC 3704.08 (rule OAC 3745-49)",
    read: "The permit fixes the plant's shape exactly — 114 data-hall gensets and 36 cooling towers in three matched groups — yet locks the one number that would let you compute its real backup capacity. The ~313 MW everyone cites is the draft public-notice figure; the issued permit will not confirm it. The scale is set; the proof is withheld.",
  },
  recordRel: "permits/4132514.epa.yaml",
};

/**
 * NPDES 7Q10 dilution screen — Ch. 3 anchor ("What it does to the water").
 * Grounded in the cited receiving-stream low flows
 * (`data/reference/hydrology/low-flow-7q10.yaml`), every value read from an Ohio
 * EPA NPDES fact sheet in the corpus (American II 2PH00006 / Dug Run; Ottawa
 * mainstem 2IG00001, USGS gage 04187100). These are document-sourced [verified].
 * The cooling-draw "many-times-the-7Q10" comparison is a worst-case bound (the
 * supply is reservoir-buffered) and is carried in the chapter prose as
 * [inference], NOT as a record read.
 */
export const NPDES_TEARDOWN: TeardownRecord = {
  title: "NPDES fact sheet — the 7Q10 screen",
  docName: "Ohio EPA · American II WWTP · permit 2PH00006 (Dug Run)",
  source: {
    file: "2PH00006 — American II fact sheet",
    pages: "Stream Flows table",
    collection: "Ohio EPA · NPDES fact sheets",
    kind: "Permit fact sheet · text-native",
    badge: "FACT SHEET",
    note: "7Q10 values are read from the Ohio EPA fact sheets committed in the corpus; the fact-sheet PDFs are available on request.",
  },
  extraction: [
    { label: "Receiving water", value: "Dug Run · impaired" },
    { label: "7Q10 design low flow", value: "0.78 cfs" },
    { label: "1Q10 (driest week)", value: "0.6 cfs" },
    { label: "Summer 30Q10", value: "0.96 cfs" },
    { label: "Stated acute dilution", value: "1.3 : 1" },
    { label: "Ottawa mainstem 7Q10", value: "0.2 cfs" },
    { label: "Ottawa 1Q10 (driest week)", value: "0 cfs · nearly dry", warn: true },
  ],
  reveal: {
    lead: "Ohio EPA sizes every discharge against the stream's design low flow — and the Ottawa this project discharges into runs at just ",
    key: "0.2 cfs",
    tail: ", dropping to zero in the driest weeks. The tributaries are worse: American II's own fact sheet states a dilution of barely 1.3 to 1. The receiving water is near-undiluted before this project adds a drop.",
  },
  check: {
    tag: "verified",
    sub: "fact-sheet 7Q10",
    verify: "Open the fact sheet · permit 2PH00006",
    verifyHref: withSite("/site/records/"),
    method: "How the 7Q10 screen works",
    methodHref: withSite("/docs/hydrology"),
  },
  connect: [
    { kind: "concept", label: "[[7q10]]", href: withBase("/wiki/concepts/") },
    { kind: "concept", label: "[[assimilative-capacity]]", href: withBase("/wiki/concepts/") },
    {
      kind: "map",
      label: "watershed + WWTP layers",
      href: withSite("/watershed/map"),
    },
    {
      kind: "dashboard",
      label: "live hydrology",
      href: withSite("/watershed/hydrology"),
    },
  ],
  recordRel: "oepa/oepa-2PH00006-american-ii-fact-sheet.npdes.yaml",
};

/** Roadwork Development Agreement — the paired second record in the 2-up. */
export const RDA_TEARDOWN: TeardownRecord = {
  title: "Roadwork Development Agreement",
  docName: "American Township ↔ Bistrozzi · effective 2025-09-15",
  source: {
    file: "RDA_executed_2025-09-15.pdf",
    pages: "§5.5 · §9.13 · §9.17",
    collection: "Legal · agreements",
    kind: "Executed contract · text-native",
    badge: "CONTRACT",
    note: "Clause text is committed in the bundle; the signed PDF is available on request.",
  },
  extraction: [
    { label: "“Company Contribution”", value: "$14,500,000" },
    { label: "§5.5 grant-refund", value: "developer refundable", warn: true },
    { label: "§9.13 records-notice", value: "5-day pre-release", warn: true },
    { label: "§9.17 procurement", value: "competitive bid waived", warn: true },
    { label: "Abatement (CRA #548-25)", value: "15 yr · 75%" },
    { label: "Public return", value: "~50 jobs" },
  ],
  reveal: {
    lead: "A public roundabout package is booked as a private gift of ",
    key: "$14,500,000",
    tail: " — but §5.5 lets public grants refund the developer, §9.13 demands notice before any record is released, and §9.17 waives competitive bidding. The label says “private”; the clauses say otherwise.",
  },
  check: {
    tag: "verified",
    sub: "executed text",
    verify: "Open RDA · §5.5, §9.13, §9.17",
    verifyHref: withSite("/site/legal/"),
    method: "Read the clause analysis",
    methodHref: withSite("/docs/economics"),
  },
  connect: [
    { kind: "entity", label: "Bistrozzi LLC", href: withBase("/wiki/entities/") },
    {
      kind: "timeline",
      label: "2025-09-15 · RDA effective",
      href: withSite("/timeline"),
    },
    { kind: "concept", label: "[[grant-refund-clause]]", href: withBase("/wiki/concepts/") },
    {
      kind: "doc",
      label: "ECONOMICS.md",
      href: withSite("/docs/economics"),
    },
  ],
  legalSlug: "withholding-map",
};

/**
 * The land-assembly packet — Ch. 2 anchor ("How it was assembled & hidden").
 * Grounded in `data/extracted/aedg/seller-land-packets.land.yaml`: the Port
 * Authority took 3-year options on the farms (2023–24), then assigned them to
 * Bistrozzi (2025-07-03, Vorys/Tangeman) under each option's §21 "unrestricted
 * right to assign," closing ~2025-07-14. The DTE-100 conveyance-fee price fields
 * were produced BLANK (p.158); only the Neighbors parcel (~$600k/5ac) is
 * disclosed; CAUV farmland → conversion recoupment (DTE-102, Elida LSD). The
 * dates are [verified]; the blank price is the redaction-reveal (reusing the
 * committed DTE-100 crop). Uses the `annotated` layout.
 */
export const ASSEMBLY_TEARDOWN: TeardownRecord = {
  title: "The land-assembly packet",
  docName: "Port Authority options → Bistrozzi assignment · 2023–2025",
  source: {
    file: "seller-land-packets.land.yaml",
    pages: "PRR-01-bundle pp. 91–295 (option packets)",
    collection: "AEDG · land assembly (PAAC production)",
    kind: "Option agreements + DTE-100s · scanned",
    badge: "PRR",
    note: "Option terms and assignment dates are transcribed from the PAAC production; the DTE-100 price fields were produced blank in the source itself.",
  },
  extraction: [
    { label: "Mechanism", value: "3-yr PAAC options → assigned" },
    { label: "Options taken", value: "2023–2024 · $1,000 each" },
    { label: "Assigned to Bistrozzi", value: "2025-07-03 · Vorys / Tangeman" },
    { label: "Closed", value: "~2025-07-14" },
    { label: "Brenneman tract", value: "81.03 ac · 7 parcels" },
    { label: "Price (DTE-100)", value: "~ blank", warn: true },
    { label: "Only disclosed price", value: "Neighbors ~$600k / 5 ac" },
  ],
  pins: [
    {
      n: 1,
      label: "A public body's options assigned to a nominee — §21 “unrestricted right to assign”",
      value: "2025-07-03 assignment",
      x: "40px",
      y: "52px",
    },
    {
      n: 2,
      label: "CAUV farmland → conversion triggers tax recoupment (Elida LSD)",
      value: "DTE-102 filed",
      x: "160px",
      y: "150px",
    },
    {
      n: 3,
      label: "Conveyance-fee price fields produced blank",
      value: "DTE-100 · $ blank",
      danger: true,
      x: "78px",
      y: "224px",
    },
  ],
  redactionLabel: "$ ______ · blank",
  reveal: {
    lead: "The public's development authority optioned the farms for $1,000 apiece, assigned the options to a Delaware LLC, and closed — and the one form that records what was paid, the DTE-100, was produced ",
    key: "with the price blank",
    tail: ". Only the Neighbors parcel's ~$600k for 5 acres is disclosed anywhere. The land was assembled through a public body and handed off; what it cost to convert CAUV farmland into a data-center campus is the blank.",
  },
  check: {
    tag: "verified",
    sub: "options + assignment dates",
    verify: "Open the deeds & land records",
    verifyHref: withSite("/site/records/"),
    method: "How an option-to-assignment chain works",
    methodHref: withBase("/methodology"),
  },
  connect: [
    { kind: "entity", label: "Port Authority of Allen County", href: withBase("/wiki/entities/") },
    { kind: "entity", label: "Bistrozzi LLC", href: withBase("/wiki/entities/") },
    {
      kind: "timeline",
      label: "2025-07-03 · option assignment",
      href: withSite("/timeline"),
    },
    { kind: "graph", label: "the land assembly", href: withBase("/wiki/graph") },
  ],
  redaction: {
    label: "$ ______ · blank",
    summary: "What did the public pay to assemble it?",
    lock: "The DTE-100 conveyance-fee value fields were produced blank across the option / closing packets; only the Neighbors parcel (~$600k / 5 ac, ~2× appraisal) is disclosed anywhere.",
    cite: "DTE-100 · PRR-01-bundle p.158 (Brenneman) · seller-land-packets.land.yaml · DTE-102 CAUV recoupment p.159",
    read: "The Port Authority — a public body — took the options and assigned them to Bistrozzi; the price across the assembled tracts is absent from the one form built to record it. CAUV farmland converting to a data center triggers tax recoupment, but the figure that would size the public's exposure is the blank.",
    crop: {
      src: "/walk/crops/dte100-blank.png",
      alt: "Brenneman DTE-100 Real Property Conveyance Fee Statement of Value — the numbered value lines with the dollar column produced blank.",
      caption: "DTE-100 value lines · produced blank",
      redaction: { x: "68%", y: "5%", w: "19%", h: "88%", label: "$ blank" },
    },
  },
};

/** All curated teardowns, for lookup by the record they anchor. */
export const ALL_TEARDOWNS: TeardownRecord[] = [
  OPACITY_TEARDOWN,
  DEED_TEARDOWN,
  SHELL_TEARDOWN,
  ASSEMBLY_TEARDOWN,
  OPC_TEARDOWN,
  AIR_TEARDOWN,
  NPDES_TEARDOWN,
  RDA_TEARDOWN,
];

/** The curated teardown anchored to a record `rel`, if one exists. */
export function teardownForRel(rel: string): TeardownRecord | undefined {
  return ALL_TEARDOWNS.find((t) => t.recordRel === rel);
}
