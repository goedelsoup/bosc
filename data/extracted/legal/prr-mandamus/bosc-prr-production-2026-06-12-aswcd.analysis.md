# BOSC PRR — Allen Soil & Water Conservation District production (2026-06-12)

**As-received:** two PDFs — `Mr. Parent Records request.pdf` (4-pp response letter) and `Parent Records Request.pdf` (54-pp records bundle). Structured index: [`bosc-prr-production-2026-06-12-aswcd.response-index.yaml`](bosc-prr-production-2026-06-12-aswcd.response-index.yaml). Source binaries at [`data/documents/legal/prr-mandamus/prr-production-2026-06-12-aswcd/`](../../../documents/legal/prr-mandamus/prr-production-2026-06-12-aswcd/) (verbatim names; sha256 in the index `meta`).

> Analysis, not legal advice. Inspection dates, dollar figures, acreages, and permit numbers are transcribed from the produced PDFs (high confidence). Verify against the originals before quoting in a filing.

## What it is

A **separate producing agency** from the County's two batches. This is **Allen Soil & Water Conservation District** (Lydia Archambo, Stormwater Coordinator) answering the relator's **own 11-item request** (Parts A–E) about the SWCD's stormwater/erosion jurisdiction over the **4110 N. Cole St.** data-center site (Ohio EPA Facility ID **0302022054**). It arrived the **same day** as the Commissioners' batch 2 — hence the `-aswcd` suffix to keep the two productions distinct. The SWCD "considers your records request fulfilled."

It is the first window into the **site-level stormwater regime**: monthly erosion-&-sediment-control (ESC) inspections of the active earth-disturbance, the County Engineer's mass-grading approval and **SW1225** stormwater permit, and the plan-review email chain. The data-center **plan sets themselves are withheld** on a new ground.

## The three things that matter

1. **NPDES coverage number is still "TBD."** Every one of the four produced ESC inspections — **2025-12-08, 2026-02-18, 2026-03-18, 2026-06-05** — lists *Site NPDES Number: **TBD***. A **~335-acre** parcel (~195 ac to be developed, ~115 ac permanently impervious) has been under mass grading since clearing/grubbing in December 2025, yet the **Construction General Permit coverage number is unrecorded** on the jurisdiction's own forms. Responsive to item 1 — and the SWCD produces no number, pointing the relator to Ohio EPA. (Permit-application item 53 assigns NPDES responsibility to **Turner Construction**.)

2. **Two "no records" answers that produced records contradict.** The SWCD answered **item 3** (wetland determinations) and **item 4** (tile drainage) with *"no responsive records."* But the inspection forms it **did** produce say otherwise:
   - **Wetland (item 3):** *"the existing wetland was mitigated"* appears from the **2025-12-08** inspection onward (pp 5, 8, 11). The on-site isolated wetland's 401 permit **DSW401251760W** (issued 2025-08-12) and its **2025-08-18 Mitigation Purchase Agreement** are already in-corpus ([`permits/3788677`](../../permits/3788677.epa.yaml), [`/3796349`](../../permits/3796349.epa.yaml)).
   - **Farm tile (item 4):** the **2026-06-05** inspection documents an **east farm-tile diversion swale** failing — *"the tile is no longer exposed and only bubbling up through soil"* — with a labeled photo (*"East farm tile bypass,"* p 9).

   Each is a produced record sitting on the exact subject the matching "no records" answer disclaims. Worth flagging in any adequacy/completeness challenge.

3. **A new withholding ground — a third agency, a new statute.** The County withheld behind the NDA/CRA/RDA/4582.58 architecture. The SWCD adds a **different** layer: the plan sets are withheld as **R.C. 149.433 infrastructure records** (25-year exemption; the plans carry the statutory *"express statement"*) **and** as **R.C. 1333.61 trade secrets** (via the 149.43(A)(1)(v) state-law exemption; *State ex rel. Besser v. Ohio State Univ.*). The asserted secret is stated plainly: *"Construction and water and wastewater usage for a data center."* The SWCD also **redacted the plan-share links** in the produced emails (black boxes on pp 41, 42, 43, 45, 46, 50) and one quoted line of plan text. Folded into [`records-withholding-map.yaml`](records-withholding-map.yaml) as **layer 7**.

## Also in the record

- **The 60-inch storm outfall** is the load-bearing element of the stormwater design. It is *"a bypass storm sewer"* under construction by **Feb 2026** (p 30), and Mass-Ex **Revision 1** (Mar–Apr 2026) explicitly notes the changes are *"background content only — the 60″ storm outfall has **not** been adjusted"* (p 21–25). It ties to the *"creek west of the site"* discharge pathway the 06-05 inspection flags.
- **Discrete cost / footprint figures:** SW1225 permit fee **$5,800** (check #637852, 2025-11-10); water install/inspection **ROM $69,103** (utilities kickoff, 4/02); **~335-ac** parcel / **~195 ac** developed / **~115 ac** permanently impervious; **9-month** mass-grading window. The ~115 ac of new impervious is a real stormwater-runoff driver for the hydrology axis.
- **The AHJ map + a governance handoff.** Stormwater plan review was run by the **Allen County Engineer (Joe Gearing)** — mass-grading approval 2025-11-14, SW1225, HUB plans approved-for-stamping 2026-05-27 — with **EMH&T** as engineer of record and **Mannik & Smith Group** as third-party storm reviewer. Private-development plan review **transfers to the SWCD on 2026-07-01** (Gearing, 2026-06-03).

## Item 6–11: "no responsive records" (deferred)

| Items | Subject | SWCD answer |
|---|---|---|
| **6–7** | BOSC-1A pump station & forcemain corridor (SWPTI-260294 / DSW-6756) | No records → *Ohio EPA / Sanitary Engineer / townships* |
| **8** | Shawnee II Phase 2 (3640 Spencerville Rd) | No records → *Ohio EPA / Sanitary Engineer* |
| **9** | Hume/Shawnee Rd forcemain incl. **design capacity (MGD)** | No records → *Ohio EPA / Sanitary Engineer* |
| **10** | ASWCD ⇄ **MS Consultants** comms | No records |
| **11** | **Commissioner Beth Seibert** comms (former SWCD staff / now Commissioner) | No records |

Two notes. **Item 11** is pointed: Seibert is **former ASWCD staff** *and* a sitting **Allen County Commissioner / Board President** ([`commissioners/closed-deliberation-and-corridor.yaml`](../../commissioners/closed-deliberation-and-corridor.yaml)) — the SWCD reports zero records either way. And **item 10's** "MS Consultants" (ms consultants inc., the County's wastewater engineer) is **not** the "Mannik & Smith Group" that appears as the HUB storm reviewer in the produced emails — *do not conflate the two firms.*

## Why it matters

The County's productions gave us the **wastewater-works** universe (pump station, forcemains, WWTP upgrades). This SWCD production gives us the **stormwater/erosion** universe at ground level: who inspects, what they found, what was permitted, what it cost — and, in the same breath, two "no records" answers that the produced inspections undercut and a third statutory shield (149.433 + trade secret) thrown over the plans. The site's **NPDES coverage number remains "TBD"** half a year into a 335-acre disturbance, the on-site wetland is already **mitigated**, an **agricultural tile** is breached, and dewatering runs toward a **creek west of the site** — all corroborated by the jurisdiction's own forms.

## Cross-refs
- [`bosc-prr-production-2026-06-05.response-index.yaml`](bosc-prr-production-2026-06-05.response-index.yaml) · [`bosc-prr-production-2026-06-12.response-index.yaml`](bosc-prr-production-2026-06-12.response-index.yaml) — the County batches (different request/custodian)
- [`records-withholding-map.yaml`](records-withholding-map.yaml) — layer 7 (the SWCD §149.433 + §1333.61 ground)
- [`../corpus-completeness-audit.md`](../corpus-completeness-audit.md) — production registered; item 3/4 tensions
- [`../../permits/3788677.epa.yaml`](../../permits/3788677.epa.yaml) · [`../../permits/3796349.epa.yaml`](../../permits/3796349.epa.yaml) — the wetland 401 permit + mitigation agreement (corroborate "mitigated")
- [`../../plans/lma1a.storm-inventory.yaml`](../../plans/lma1a.storm-inventory.yaml) — the storm system (60-inch outfall context)
- [`../../commissioners/sanitary-economics.yaml`](../../commissioners/sanitary-economics.yaml) — data-center blowdown → WWTP (item 7 receiving)
