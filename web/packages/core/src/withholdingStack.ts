/**
 * The withholding stack (#224) — Project BOSC's layered records-withholding
 * architecture, the Opacity chapter's spine. Grounded layer-for-layer in
 * `data/extracted/legal/prr-mandamus/records-withholding-map.yaml` (`the_stack[]`):
 * seven lawful-looking layers along the records lifecycle, each with its operative
 * clause and the committed document it lives in.
 *
 * Discipline (held from the source): every clause / statute is `[verified]` from a
 * committed extraction; the **"engineered system" reading is argument**, and the
 * record labels it as such — `STACK_THESIS`/`STACK_CLOSE` keep that explicit.
 */
import { withSite } from "./site";

export interface WithholdingLayer {
  n: number;
  /** Short lifecycle title, e.g. "Front-end statutory shield". */
  title: string;
  /** The statute / clause that does the work, e.g. "R.C. 4582.58". */
  statute: string;
  /** The instrument it lives in (with the resolution / date locator). */
  instrument: string;
  /** Operative clause text — transcribed / paraphrased from the committed doc. */
  clause: string;
  /** Plain-language effect: what this layer keeps non-public. */
  effect: string;
  /** Source extraction the clause is read from (a committed YAML / doc). */
  source: string;
}

/** The seven layers, ordered along the records lifecycle (front-end → production). */
export const WITHHOLDING_STACK: WithholdingLayer[] = [
  {
    n: 1,
    title: "Front-end statutory shield",
    statute: "R.C. 4582.58",
    instrument: "Port Authority records policy · adopted 2022-07-28",
    clause:
      "“Financial and proprietary information, including trade secrets, submitted to the Authority is not a public record subject to R.C. 149.43 until that employer commits in writing to proceed.”",
    effect:
      "Developer information routed through AEDG / PAAC is a statutory non-record for the entire formative period — the deal's substance never enters “record” status while it is being decided.",
    source: "aedg/paac-records-policy.policy.yaml",
  },
  {
    n: 2,
    title: "Developer-notice — County",
    statute: "NDA §6(f)",
    instrument: "County–Bistrozzi Mutual NDA · Res #417-25 · executed 2025-07-01",
    clause:
      "Before responding to legal process, the County must give the Company prior written notice — “at least 10 business days” — disclose only “such information as is required by law,” and “request and seek confidential treatment.”",
    effect:
      "A tip-off-and-minimize protocol baked in before any public-records request is answered — requested by the County's own counsel.",
    source: "legal/prr-mandamus/mutual-nda-bistrozzi.nda.yaml",
  },
  {
    n: 3,
    title: "Developer-notice — Authority",
    statute: "RDA §9.13",
    instrument: "Roadwork Development Agreement · effective 2025-09-15",
    clause:
      "The Company acknowledges the Agreement is a public record, but the Authority agrees to give the Company written notice “at least five (5) business days prior” to disclosure.",
    effect: "A second, parallel developer-notice mechanism on the Authority side.",
    source: "aedg/roadwork-development-agreement.rda.yaml",
  },
  {
    n: 4,
    title: "Fee-shifting indemnity",
    statute: "CRA §22",
    instrument: "Community Reinvestment Area Agreement · Res #548-25 · 2025-07-10",
    clause:
      "The Agreement is a public record, but “the Company indemnifies the County and pays its attorney fees if, in a public-records action, the County withheld a record.”",
    effect:
      "The developer underwrites the defense of withholding — removing the usual financial deterrent to over-withholding.",
    source: "legal/prr-mandamus/cra-agreement.cra.yaml",
  },
  {
    n: 5,
    title: "Closed deliberation",
    statute: "ORC 121.22(G)(8)",
    instrument: "Board of Commissioners executive sessions",
    clause:
      "First invoked 2025-05-27 for the BOSC CRA, expressly citing the Bistrozzi NDA as the basis for confidential discussion; the exemption appears nowhere in the covered record before that date.",
    effect:
      "The deliberations themselves are held out of public view — the open-meetings counterpart to the records shield.",
    source: "commissioners/closed-deliberation-and-corridor.yaml",
  },
  {
    n: 6,
    title: "Non-production — the deciding figures",
    statute: "R.C. 149.43 / 9.66(D)",
    instrument: "County PRR production · cover 2026-06-05",
    clause:
      "Item 4 (the cost-benefit analysis) withheld as “being reviewed by legal counsel”; items 5–15 deferred though authorized in the Board's own minutes; the DTE-100 transfer-tax price fields produced blank.",
    effect:
      "What is produced omits the numbers that decide the public-interest question — the cost-benefit, the land prices, the school terms — by claim, deferral, or blank.",
    source: "legal/corpus-completeness-audit.md",
  },
  {
    n: 7,
    title: "A third agency, a new statutory basis",
    statute: "R.C. 149.433 + R.C. 1333.61",
    instrument: "Allen SWCD PRR response · 2026-06-12",
    clause:
      "The Soil & Water Conservation District withholds the data-center plan sets on two grounds at once: R.C. 149.433 “infrastructure records” (a 25-year exemption) and R.C. 1333.61(D) trade secret — “water and wastewater usage for a data center” — redacting even the plan-share links in the produced emails.",
    effect:
      "Extends the architecture to the site-level stormwater jurisdiction, under statutes the County's own productions never invoked — and reaches the very water/usage data the cooling and sanitary analyses turn on.",
    source: "legal/prr-mandamus/bosc-prr-production-2026-06-12-aswcd.response-index.yaml",
  },
];

/** The thesis (argument), kept explicit — the layers are document; the “system” is the read. */
export const STACK_THESIS =
  "No single refusal hides this deal. Each layer is individually lawful-looking; read together along the records lifecycle, they keep the deal's substance non-public. Calling the whole an engineered system is argument — every clause below is [verified] from a committed document; the characterization is the read.";

/** The close — the mandamus spine + the Select-Committee through-line (links are
 *  curated to legal pages that the build resolves; check-links guards them). */
export const STACK_CLOSE = {
  lead: "This is the spine of the records case: the County did not merely decline one request — it agreed in advance to notify and minimize (NDA §6, RDA §9.13), indemnified its own withholding (CRA §22), deliberated in closed session (G)(8), and produced the deciding records blank or not at all — all behind the R.C. 4582.58 shield.",
  tail: "It is why the same record went to the Ohio Select Committee on Data Centers — where the case against the very confidentiality regime behind layer 6, R.C. 9.66(D), is made on the record: communities asked to subsidize a developer the public is not allowed to name.",
  links: [
    {
      label: "the full withholding map",
      href: withSite("/site/legal/withholding-map"),
    },
    {
      label: "the mandamus production analysis",
      href: withSite("/site/legal/prr-production"),
    },
    {
      label: "the Select-Committee testimony",
      href: withSite("/site/legal/written-testimony"),
    },
  ],
};
