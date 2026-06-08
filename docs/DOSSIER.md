# Project BOSC — Research Dossier (v1)

> **What this is.** A synthesis of everything BOSC has deconstructed from the
> public-records corpus into structured data, assembled across documents via the
> cross-document layer (`bosc.pipeline.corpus` → `entities` + `timeline`). It is
> generated from, and cites, the committed artifacts under `data/extracted/**`.
>
> **Evidence discipline.** Claims are tagged `[verified]` (read from a committed
> extraction, cited) or `[inference]` (a reading of the assembled record, labelled
> as such). This is a synthesis of **public records** — registered-agent and
> organizer overlaps are *common-control plumbing*, **not** statements about
> beneficial ownership, and shell-adjacent signals are evidence, not verdicts.
>
> **Corpus as of this writing:** 48 extracted documents — 5 deeds, 9 NPDES, 3 SoS
> filings, 30 Ohio EPA/USACE permit actions, 1 site plan, 1 OPC roadwork summary →
> **36 resolved entities, 39 relationships, 44 dated events.**

---

## 1. Executive summary

A large, **hardened data-center campus** — the "American Industrial Park Site" on
the **North Cole Street corridor in Allen County (Lima), Ohio** — is being built
by a **Delaware shell entity, Bistrozzi LLC**, which assembled the land, is
driving the environmental and infrastructure permitting, and is the named
beneficiary of a privately-funded **$14.2M public roadwork** program routed
through the Allen County Port Authority. The same professional network (Vorys
counsel; EMH&T engineering) and the same registered-agent/organizer fingerprints
connect Bistrozzi to a cluster of sibling Delaware LLCs — **Bistrozzi Addition,
Magenta Capital, and Tilted Gate** — the last of which is running a parallel
project ("Project Dazzler") in Scioto County. County-operated wastewater capacity
on the same corridor (three WWTPs) forms the utility backdrop. `[inference]`

The data-center identity is not inferred from massing alone: an Ohio EPA air
permit names **"Bistrozzi LLC Data Center – Initial Installation"** and the site
plan shows **a substation, anti-ram barriers, security fencing, and containment
areas**. `[verified: data/extracted/permits/3987141.epa.yaml,
data/extracted/plans/LMA1A-95-SPS-2025-10-28.plan.yaml]`

**Why this dossier exists (the removal architecture).** The public record is
*designed* to be thin here: **ORC §9.66(D)** (Sub. H.B. 184, eff. 2026-03-20)
categorically excludes economic-development project information from disclosure,
layered atop NDA-by-default, a Delaware-shell counterparty, and permitting
segmented across agencies. The structured corpus below is the *reconstruction* —
each fact reassembled from a primary permit, deed, or filing the removal
architecture could not suppress. `[verified: statute]` / `[inference: framing]`

---

## 2. The entity at the center — Bistrozzi LLC

`BISTROZZI LLC` is the hub of the graph: **grantee on 4 deeds (11 parcels),
applicant on ~20 EPA permit actions**, a Delaware foreign LLC.
`[verified: entity graph; signals=['delaware']]`

### 2.1 The Delaware shell cluster

Three sibling LLCs file as **Delaware foreign LLCs** through overlapping
fingerprints `[verified: data/extracted/permits/sos-*.sos.yaml]`:

| LLC | Formation | Registered agent | Organizer | Signal |
|---|---|---|---|---|
| Bistrozzi Addition LLC | Delaware | C T Corporation | Scott J. Ziance | — |
| Magenta Capital LLC | Delaware | **Corporation Service Company** | **Michael Montfort** | `shared_agent` |
| Tilted Gate LLC | Delaware | **Corporation Service Company** | **Michael Montfort** | `shared_agent` |

Magenta Capital and Tilted Gate share **both** registered agent (CSC) and
organizer (Montfort); Bistrozzi LLC and Tilted Gate also share a **Wilmington, DE
mailing address** (2801 Centerville Rd — a private-mailbox/agent address).
`[verified: data/extracted/permits/3796349.epa.yaml,
data/extracted/permits/4081910.epa.yaml]` These are common-control signals across
the cluster, not beneficial-ownership findings. `[inference]`

---

## 3. Land assembly — the corridor block

Five conveyances, all recorded to **Bistrozzi LLC**, assemble a contiguous block.
`[verified: data/extracted/recorder/*.deed.yaml]`

| Recorded | Instrument | Grantor → Grantee | Parcels |
|---|---|---|---|
| 2025-08-13 | 202508130008300 | Brenneman Living Trusts (×2) → Bistrozzi LLC | 7 |
| 2025-08-13 | 202508130008312 | Neff Farms, Inc. → Bistrozzi LLC | 2 |
| 2025-08-13 | 202508130008316 | Pike Run Farms LLC → Bistrozzi LLC | 1 |
| 2026-03-04 | 202603040002064 | James & Suzanne Neighbors → Bistrozzi LLC | 1 |

Cross-check: BOSC's deed extractor independently reproduced Periplus's frozen
hand-curated parcel ledger **11/11** (`tests/test_periplus_crosscheck.py`).
`[verified]`

---

## 4. The data center — site plan & air permits

**Site plan** `LMA1A-95-SPS` (95% Site Plan Set, Grading & Storm, 1"=30',
2025-10-28): project **"American Industrial Park Site," Lima, OH 45801**, designed
by **EMH&T** (Civil), **CI Design Inc** (Architecture, Boston), **WSP USA
Buildings** (MEP/Structure, Troy NY). Legend features include a **substation,
transformer, anti-ram barriers, permanent + temporary security fence, fiber duct
bank, containment areas**, and "SSS/GPS buildings on piers."
`[verified: data/extracted/plans/LMA1A-95-SPS-2025-10-28.plan.yaml]`

**Air permitting** confirms scale: Ohio EPA Air Pollution Permit-to-Install
**P0138965** for the **"Bistrozzi LLC Data Center – Initial Installation"** —
the public notice references **~114–115 backup generators (~2,750 ekW)**.
`[verified: data/extracted/permits/3987141.epa.yaml,
data/extracted/permits/3866942.epa.yaml]`

**Zoning jurisdiction.** A parcel-by-parcel join against the City of Lima zoning
layer returns **0 of 48** cited corpus parcels inside city limits: the corridor sits
in **American/county townships**, so the project is **not subject to the City of Lima
zoning code**. Allen County GIS publishes no county/township zoning layer (only Tax
and School districts), so the controlling land-use authority is township/county — not
the city, and not GIS-mapped. `[verified: data/reference/lima-gis/parcels.zoning.yaml]`

---

## 5. Water — wetlands, sanitary sewer, county WWTPs

**Wetland / 401 permitting (Project Bosc):** a sustained Ohio EPA Division of
Surface Water thread runs **2025-07 → 2026-02** — a Level-1 Isolated Wetland
Permit (DSW401251760W: application → incomplete → approved), a mitigation-bank
credit purchase, then a Level-2 IWP (DSW401252260W: application → incomplete →
comments). `[verified: data/extracted/permits/*.epa.yaml]`

**Sanitary sewer:** Surface Water Permit-to-Install **DSWPTI-260294**, "BOSC-1A
Private Sanitary Sewer Improvement Plan," 4110 N Cole St — application 2026-03-17,
**approved 2026-04-07** (Turner Construction is GC). `[verified:
data/extracted/permits/4074527.epa.yaml, data/extracted/permits/4074551.epa.yaml]`

**County WWTP capacity (utility backdrop):** three Allen County plants on the
corridor `[verified: data/extracted/oepa/*.npdes.yaml]`:

| Facility | NPDES | Operator | Receiving water |
|---|---|---|---|
| American II WWTP | 2PH00006 | Allen County Commissioners | Dug Run |
| American Bath WWTP | 2PH00007 | Allen County Commissioners | Pike Run |
| Shawnee II WWTP | 2PK00002 | Allen County Sanitary Eng. Dept. | Ottawa River |

Note the resonance: **Pike Run Farms LLC** (a Bistrozzi grantor) shares its name
with **Pike Run**, the American Bath WWTP's receiving water. `[verified]`

**Downstream — the Maumee Nutrient TMDL.** All three plants discharge (Ottawa →
Auglaize → Maumee) into Lake Erie's largest tributary, under the US-EPA-approved
**2023 Maumee Watershed Nutrient TMDL**, which assigns each an individual
total-phosphorus wasteload allocation (spring-season metric tons: Shawnee No 2
**0.75**, American-Bath **0.37**, American No 2 **0.30**; the main Lima WWTP
**4.0**). So the same effluent the [low-flow screen](HYDROLOGY.md) shows is
effectively undiluted is also **capped at the basin scale** by a binding nutrient
budget — local dilution failure on top of a Lake-Erie phosphorus cap. `[verified:
data/reference/hydrology/maumee-tmdl-wla.yaml]`

**Atmospheric water budget (NASA POWER + FAO-56).** The corridor's climate normal is
**~997 mm/yr** precipitation against **~1,085 mm/yr** of reference ET0 (FAO-56
Penman-Monteith from the NASA POWER normals) — a **−88 mm/yr** net, with ET0
exceeding rainfall every month **May–Oct**. The growing-season water deficit lands in
exactly the months the Ottawa is at its low-flow floor, so peak evaporative demand and
any consumptive cooling draw coincide with minimum river supply (see the
[hydrology report §3–4](HYDROLOGY.md)). `[derived: FAO-56 Penman-Monteith over
data/reference/hydrology/nasa-power-climatology.yaml]`

**The seasonal pinch, quantified.** Screening the sourced data-center cooling draw
(**~4.85 cfs** net consumptive, central estimate) against the Ottawa's *cited
seasonal* low flow — not just the annual 7Q10 — sharpens the conclusion. Across the
**May–Oct** growing season (exactly the months reference ET exceeds precipitation),
the draw is **~3×** the cited **summer 30Q10 (1.6 cfs)**; the annual-7Q10 figure
(**~24×**, 0.2 cfs) understates the in-season constraint by reading against a floor
that does not apply in summer. And 30Q10 is the *generous* seasonal floor — the
Ottawa's absolute design low flow is **1Q10 = 0 cfs**, so in the driest growing-season
weeks there is no flow to draw against at all. The cooling draw peaks against supply
precisely when the atmosphere is also taking the most. `[derived: cooling basis vs
cited 30Q10/7Q10/1Q10, data/reference/hydrology/low-flow-7q10.yaml]`

**Floodplain.** The recorded campus parcels sit *just outside* the FEMA Special
Flood Hazard Area, but Zone AE (1%-annual-chance) floodplain and regulatory
**floodway** (FEMA DFIRM 39003C) come within **~50 m** of the footprint — a no-rise
corridor the post-development stormwater increase drains toward (see
[hydrology](HYDROLOGY.md)). `[verified: data/reference/hydrology/campus-floodzone.yaml]`

**Toxic-release baseline (EPA RSEI).** The corridor sits in a long-industrial county.
EPA's Risk-Screening Environmental Indicators set ranks **45** Allen County TRI
facilities by modeled, population-weighted Score; the top emitters are **INEOS USA**,
the **WHEMCO-Ohio foundry**, and — notably for the defense thread — the **JSMC /
General Dynamics Land Systems** plant at **#3** (~3.6 M Score, 99% cancer-weighted,
chiefly nickel compounds, reported 1988–1993). That is an independent federal dataset
naming **GDLS at the JSMC**, corroborating the
[defense-contractor scan](../data/reference/allen-gis/README.md)'s reading of the
Army-owned footprint — and the **GLEIF** registry independently records that
*General Dynamics Land Systems Inc.* (LEI `875500ULXB4CYQSJVA03`) reports its
**ultimate parent** as *General Dynamics Corporation*, confirming the ownership chain
`[verified: data/reference/gleif/lei-records.yaml]`. Several RSEI facilities also carry NPDES permits that join to
the [Maumee NPDES inventory](../data/reference/echo/README.md), and the per-facility
*water* release bucket ties into the dilution analysis above. `[verified:
data/reference/rsei/inventory.yaml]`

**Toxic load meets the lowest dilution (RSEI × 7Q10).** Extending the low-flow
assimilative screen from the three municipal WWTPs to the *industrial* dischargers
exposes a sharper coincidence: of the **12** county facilities that release toxics to
water, the **three** largest — **INEOS, Lima Refining, and PCS Nitrogen** — all cluster
on the **Ottawa River at Lima**, whose cited design low flow is **0.2 cfs (1Q10 = 0)**.
Their reported water releases screen at roughly **66 / 165 / 274 mg/L** if carried at
that 7Q10 — i.e. the county's heaviest toxic loads enter the one reach with essentially
no assimilative capacity, and that floor falls in the same **May–Oct** window the
atmospheric budget runs to deficit. Only Lima Refining's receiving water is
independently ECHO-cited (`OH0002623 → Ottawa River`); INEOS and PCS are corridor
inferences, flagged as such. The mg/L figures are a coarse `[inference: derived]`
order-of-magnitude screen, not measured concentrations. `[verified:
data/reference/rsei/toxic-discharge-screen.yaml]`

**Who owns the dischargers, and who benefits from federal dollars.** Two ownership
layers now sit on the [entity graph](entities.md). First, an **industrial-ownership**
layer folds each Allen County RSEI facility into its GLEIF-resolved corporate parent
(`owned_by`): the Ottawa-corridor toxic dischargers map to **INEOS USA LLC**, **Cenovus**
(via Husky, the Lima Refining parent), and **Shell** (Equilon), alongside Ford, Marathon,
Dana, Textron, and P&G — so the toxics screen above resolves to named, LEI-pinned
owners. `[verified: data/reference/gleif/lei-records.yaml + data/reference/rsei/inventory.yaml]`
Second, a **federal-award** layer stamps USASpending all-time prime-award obligations onto
the verified corridor parties: the corridor's federal defense nexus — **General Dynamics
Land Systems** (the JSMC operator, **~$33.6 B**) and its parent **General Dynamics Corp**
(**~$299 B**, which USASpending independently records as GDLS's parent, corroborating the
GLEIF chain). The data-center end-user attribution remains **open**; *Google LLC* (~$73.5 M
federal) ties only to the **separate Scioto-County Project Dazzler** (the `google.com`
applicant email), **not** the Lima campus — kept off-graph so the federal layer does not
overclaim. `[verified: data/reference/usaspending/awards.yaml]`

---

## 6. The public ledger — what the abatement costs vs. what it returns

The data center runs on a **15-year, 75% real-property tax abatement** (Allen County
CRA No. 1, Res #548-25 of 2025-07-10; CRA designation #003-99003-396), granted to
**Bistrozzi LLC** — a Delaware shell c/o Vorys (Scott Ziance) — whose CRA **§13(A)**
assurance is that its **parent is a publicly-traded Fortune 100 company**. `[verified:
data/extracted/legal/prr-mandamus/cra-agreement.cra.yaml]` The statutory school-district
notices were drafted and served not by the County clerk but by the **Allen Economic
Development Group (AEDG)** — **Cynthia Leis, President/CEO** — the entity coordinating the
abatement; both superintendents (Elida's Joel Mengerink, Apollo JVSD's Keith Horner)
acknowledged receipt on 2025-06-25. `[verified:
data/extracted/legal/prr-mandamus/school-district-notice-letters.notice.yaml]` Leis also
serves as **Executive Director of the Port Authority** (which has no employees and signed
the $14.5M roadwork deal) — one person directing both the econ-dev nonprofit and the public
body — and the PAAC's own minutes confirm the end user is **Google**. `[verified:
data/extracted/aedg/paac-records-policy.policy.yaml + paac-board-minutes.minutes.yaml]`

**What the public gives.** 75% of the property tax on the ~$500M improvement, 15 years
per building — a screening **~$84–129M in abated property tax**, i.e. roughly
**$1.7–2.6M of abatement per promised job** (the CRA estimates **~50** permanent jobs,
**~$4M** annual payroll, from a current **zero**). The dollar range is a stated
assumption (Ohio commercial effective-rate band on the 35% assessed value), **not** a
cited Allen County millage `[inference: assumption]` — yet even so it screens *worse*
than the relator's own Ohio comparable of ~$1M/job of revenue loss. Regenerate with
`bosc ledger`.

**What the public bears alongside** (already quantified by the other threads):

- **Toxics:** 3 of 12 county toxic water dischargers sit on the Ottawa at Lima, the
  reach with ~zero assimilative capacity (7Q10 0.2 cfs, 1Q10 0).
- **Water:** a ~4.85 cfs consumptive cooling draw — **3×** the Ottawa's summer 30Q10,
  **24×** the annual 7Q10, arriving in the May–Oct ET-deficit window.
- **Roadwork drainage:** $1.07M of roundabout drainage budgeted with only 1 of 6
  estimates itemized and no detention sized.
- **Federal nexus:** the corridor's defense anchor (JSMC operator GDLS, ~$34B all-time
  federal awards; parent GD Corp ~$299B).
- **Air:** 114 diesel emergency gensets (~313 MW backup), permitted **synthetic-minor**
  to stay just under major-source NSR review.
- **Roadwork:** a parallel **$14.5M** Roadwork Development Agreement (PAAC/Bistrozzi)
  builds 4 roundabouts + 2 road rehabs the County then maintains in perpetuity; RDA
  **§5.5** lets State 629 / ODOD grants *refund* the developer's "contribution" — so
  public money may fund the private share, while the actual award (Eagle Bridge
  **~$3.52M**) runs far under the $14.5M collected. `[verified:
  data/extracted/aedg/roadwork-development-agreement.rda.yaml + paac-board-minutes.minutes.yaml]`
- **Wastewater × TMDL:** a new data-center sanitary load enters a fully-allocated,
  reduction-bound Maumee watershed (point-source future-growth reserve only **~1.4–1.5
  mt P/spring** basin-wide) and, as a new/expanding discharger, must add secondary +
  tertiary treatment to hit a **0.5 mg/L** TP limit — a ratepayer cost the package
  omits. `[verified: data/reference/hydrology/maumee-tmdl-budget.yaml + maumee-tmdl-responsiveness.yaml]`
- **Land conversion (CAUV):** the assembled campus parcels were CAUV farmland;
  conversion triggers a one-time CAUV recoupment and pulls productive ag land from the
  Elida-LSD tax base — onto which the 75% abatement is then layered. `[verified:
  data/extracted/aedg/seller-land-packets.land.yaml]`

**What the public can't see — by the County's own choices.** The figures that would
actually answer *"is this a good deal?"* are withheld: the County's **cost-benefit
analysis** (PRR request item 4, withheld under R.C. 149.43 / 9.66 as "being reviewed by
legal counsel"); the **School District Compensation Agreement** dollar amounts
(non-public, only the 25% floor disclosed — though the PAAC minutes surface a *proposed*
**$200K→$250K/yr PILOT** to Elida, so the deciding figure demonstrably exists, and the
**Lima-Allen County Regional Planning Commission**'s own minutes independently restate it:
a DCC presentation on the project — named in the minutes as *"project BOSC (Google data
center)"* — recorded **$250,000 to Elida Schools** and **$1.5 billion invested if all
three phases proceed**); and the
**land-assembly purchase prices** — the recorded deeds state only "valuable
consideration" and the **DTE-100 transfer-tax forms were produced with the price fields
blank**, so what was paid to assemble the ~350-acre campus is opaque (only the Neighbors
parcel, **$600K / 5.0 ac**, is disclosed). And CRA **§22 indemnifies the County's
attorney fees** for defending exactly that kind of withholding — a private subsidy for
public secrecy. `[verified: cra-agreement.cra.yaml + seller-land-packets.land.yaml +
paac-board-minutes.minutes.yaml + bosc-prr-production-2026-06-05.response-index.yaml +
lacrpc/meetings/meeting-summaries.yaml]`

---

## 7. Roadwork — privately-funded public infrastructure

Six Tetra Tech Opinions of Probable Cost (~**$14.2M**) cover roundabouts and
corridor work at Cole/Diller, Cole/Bluelick, the Primary Access Entrance (Beery &
N. Cole), and Cole/West (SR 115). The OPC states the program is **privately funded
via a "BOSC Team" deposit to the Port Authority (PAAC), to be dedicated to the
County on completion** — i.e. a private developer financing public road capacity
through the port authority. `[verified: data/extracted/aedg/roundabouts.summary.opc.yaml]`

**The executed agreement.** The Roadwork Development Agreement (PAAC / Allen County /
Bistrozzi, effective **2025-09-15**; PAAC Res **O.729-25**, County Res **588-25**) sets
the deposit at a **$14,500,000** "Company's Contribution" (basis = the Tetra Tech OPC,
per Exhibit D), builds the 4 roundabouts + Cole/Bluelick rehabs, and **dedicates them to
the County for perpetual maintenance**. Three clauses matter: **§5.5** refunds any
"overpayment" — including State 629 / ODOD grant funds — back to the company, so public
grants can backfill the private contribution; **§9.17** exempts the company from any
competitive **procurement**; and **§9.13** is a *third* records-withholding lever (after
the NDA §6 and CRA §22), binding PAAC to **≥5 business days' notice to the developer**
before answering any records request and to redact all it lawfully can. The first real
construction award — **Eagle Bridge, ~$3.52M** (2026-04-23 PAAC minutes) — runs far below
the $14.5M collected, sharpening the §5.5 refund question. `[verified:
data/extracted/aedg/roadwork-development-agreement.rda.yaml + paac-board-minutes.minutes.yaml]`

**Drainage scope vs the design storm.** The six OPCs budget **$1,068,530** of
drainage, but the engineering basis is thin: only **one** of the six sub-estimates
carries an extracted line-item breakdown, and in that one (Cole/Diller) **83%** of
the drainage cost is a single lump-sum "Drainage improvements" line — the only sized
conveyance element is a 6-in *subsurface* underdrain. No estimate cites a design
storm or return period, even though the corridor's regulatory design rainfall is
fixed (NOAA Atlas-14: 25-yr 24-hr **4.25 in**, 100-yr 24-hr **5.39 in**
`[verified: connector]`), and neither the OPC nor the 95% SPS grading & storm plan
itemizes the **detention/retention** storage the post-development runoff requires
(`detention_shown: false`) — echoing the corpus's own extraction note asking whether
the lump-sum items even include a detention basin. So the drainage line reads as a
budget placeholder, not a design-basis quantity: a cost-completeness risk on
privately-financed public infrastructure. This is a scope/design-basis reading, not
a sizing of the roundabouts' hydraulics (the corpus carries no footprint area).
`[verified: data/reference/hydrology/atlas14-corridor-ddf.yaml + bosc drainage-audit]`

---

## 8. Project Dazzler — the parallel Tilted Gate thread

**Tilted Gate LLC** (Delaware; CSC agent; Montfort organizer; principals **Randy
Barrera** and **Timothy Chadwick**) is running a *separate* project, **"Project
Dazzler,"** with its own USACE Section 404 / 401 / wetland-mitigation track — and
in a **different county (Scioto)**. Same shell fingerprint and same engineer
(EMH&T), different geography. `[verified: data/extracted/permits/4081*.epa.yaml,
data/extracted/permits/sos-tilted-gate-llc-2025-09-29.sos.yaml]`

The Dazzler EPA application's applicant contact, **Randy Barrera, signed as
`randybarrera@google.com`** — a Google email address on the Tilted Gate / Project
Dazzler filing. `[verified: data/extracted/permits/4081890.epa.yaml]` This is a
direct Google↔**Dazzler** (Scioto) datapoint; it does **not**, by itself, attach
Google to the Lima/Bistrozzi campus, where the public Google attribution rests on
the AEDG release (not yet in the corpus). `[open]`

---

## 9. The professional network

A consistent advisory team sits behind the entities `[verified: entity graph]`:

- **Counsel — Vorys, Sater, Seymour and Pease:** Jill Tangeman (×11 contacts),
  Scott Ziance, Hannah Bragg (filer on the Bistrozzi Addition SoS registration).
- **Organizer — the Delaware shells:** Michael Montfort is the SoS
  **organizer/manager** of Magenta Capital & Tilted Gate — **not** Vorys counsel.
  A third-party investor profile ties this Montfort to Dallas–Fort Worth real
  estate and to **Platon Investments LLC** + **Dynamo Ventures LLC** (both TX, inc.
  2025-05-29), sharing the cluster's 2801 Centerville Rd, Wilmington PMB.
  `[inference: aggregator-sourced; identity-resolution uncertain]`
  *Name-collision caution:* a `wsgr-michael-j-montfort-bio.pdf` (Wilson Sonsini
  employee-benefits counsel, Washington D.C.) sits in the corpus but is **probably
  a different Michael Montfort** — it is **not** treated as the organizer or as
  campus counsel. `[open]`
- **Civil engineering — EMH&T:** Heather Dardinger, Melissa Queen Darby, et al.;
  also the site-plan engineer of record.
- **GC — Turner Construction** (Robert Zizzo) on the sanitary sewer.

---

## 10. Chronology (selected milestones)

`[verified: bosc timeline]`

| Date | Event |
|---|---|
| 2023-05 | Shawnee II WWTP NPDES public notice (utility backdrop) |
| 2023-09 | Maumee Watershed Nutrient TMDL approved (basin P caps incl. the corridor WWTPs) |
| 2025-07-02 | First Project Bosc 401 WQC application |
| 2025-07-11 | Tetra Tech OPC roadwork estimate (~$14.2M) |
| 2025-08-13 | Bistrozzi records 3 deeds (Brenneman, Neff, Pike Run) — 10 parcels |
| 2025-09-29 | Tilted Gate LLC formed (DE) |
| 2025-10-17 | Magenta Capital LLC formed (DE) |
| 2025-10-28 | American Industrial Park 95% Grading & Storm Plan |
| 2025-12-10 | Air PTI — "Bistrozzi LLC Data Center – Initial Installation" |
| 2026-03-04 | Neighbors → Bistrozzi (final parcel) |
| 2026-04-08 | Bistrozzi Addition LLC SoS filing (DE) |
| 2026-04-07 | BOSC-1A sanitary-sewer PTI approved |
| 2026-04-14 | Project Dazzler USACE 404 application (Scioto Co.) |

---

## 11. Open questions & gaps `[open]`

- **Beneficial ownership.** Public records give registered agents and organizers,
  never the human principal behind the Delaware shells. The cluster is *plumbing*.
- **The Bistrozzi Addition deed — resolved.** ✅ Now ingested: Limited Warranty
  Deed 202604210003890 (2026-04-21), **Timothy R. & RaeAnn Pieper → Bistrozzi
  Addition LLC**, parcel 36-1100-04-001.001 (7.215 ac), 1337 Beery Road. Carried
  in the timeline and entity graph. `[verified: data/extracted/recorder/202604210003890.deed.yaml]`
- **Roadwork funding instrument.** We have the cost estimate, not the agreement —
  who bears overruns, and the exact PAAC deposit mechanics, are unread.
- **Resolution noise.** A few contact entities remain coarse (the model
  occasionally merged two names or a name+firm into one field); see the graph.

---

## 12. Method & provenance

Every claim here derives from a committed artifact under `data/extracted/**`,
produced by the `ingest → extract → analyze` pipeline (hybrid OCR+vision or
text-first reads, Pydantic-validated, with self-reported confidence and warnings).
The cross-document entity graph and timeline are deterministic functions of those
artifacts (`bosc entities`, `bosc timeline`) — re-runnable and auditable. Figures
transcribed from degraded scans may carry a `~` approximate marker; permit and
instrument numbers are copied exactly. This dossier reflects the corpus **as
extracted so far** and should be regenerated as new documents are ingested.
