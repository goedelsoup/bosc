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

Five conveyances, all recorded to **Bistrozzi LLC**, assemble a contiguous block;
a sixth conveys adjacent port-authority land to **Amazon** (a distinct thread).
`[verified: data/extracted/recorder/*.deed.yaml]`

| Recorded | Instrument | Grantor → Grantee | Parcels |
|---|---|---|---|
| 2025-08-13 | 202508130008300 | Brenneman Living Trusts (×2) → Bistrozzi LLC | 7 |
| 2025-08-13 | 202508130008312 | Neff Farms, Inc. → Bistrozzi LLC | 2 |
| 2025-08-13 | 202508130008316 | Pike Run Farms LLC → Bistrozzi LLC | 1 |
| 2026-03-04 | 202603040002064 | James & Suzanne Neighbors → Bistrozzi LLC | 1 |
| 2025-11-18 | 202511180011830 | **Port Authority of Allen County → Amazon.com Services LLC** | 1 |

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
Army-owned footprint. Several RSEI facilities also carry NPDES permits that join to
the [Maumee NPDES inventory](../data/reference/echo/README.md), and the per-facility
*water* release bucket ties into the dilution analysis above. `[verified:
data/reference/rsei/inventory.yaml]`

---

## 6. Roadwork — privately-funded public infrastructure

Six Tetra Tech Opinions of Probable Cost (~**$14.2M**) cover roundabouts and
corridor work at Cole/Diller, Cole/Bluelick, the Primary Access Entrance (Beery &
N. Cole), and Cole/West (SR 115). The OPC states the program is **privately funded
via a "BOSC Team" deposit to the Port Authority (PAAC), to be dedicated to the
County on completion** — i.e. a private developer financing public road capacity
through the port authority. `[verified: data/extracted/aedg/roundabouts.summary.opc.yaml]`

---

## 7. Project Dazzler — the parallel Tilted Gate thread

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

## 8. The professional network

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

## 9. Chronology (selected milestones)

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
| 2025-11-18 | Port Authority → Amazon conveyance |
| 2025-12-10 | Air PTI — "Bistrozzi LLC Data Center – Initial Installation" |
| 2026-03-04 | Neighbors → Bistrozzi (final parcel) |
| 2026-04-08 | Bistrozzi Addition LLC SoS filing (DE) |
| 2026-04-07 | BOSC-1A sanitary-sewer PTI approved |
| 2026-04-14 | Project Dazzler USACE 404 application (Scioto Co.) |

---

## 10. Open questions & gaps `[open]`

- **Beneficial ownership.** Public records give registered agents and organizers,
  never the human principal behind the Delaware shells. The cluster is *plumbing*.
- **The Bistrozzi Addition deed — resolved.** ✅ Now ingested: Limited Warranty
  Deed 202604210003890 (2026-04-21), **Timothy R. & RaeAnn Pieper → Bistrozzi
  Addition LLC**, parcel 36-1100-04-001.001 (7.215 ac), 1337 Beery Road. Carried
  in the timeline and entity graph. `[verified: data/extracted/recorder/202604210003890.deed.yaml]`
- **Roadwork funding instrument.** We have the cost estimate, not the agreement —
  who bears overruns, and the exact PAAC deposit mechanics, are unread.
- **Amazon — a second hyperscale consumer, not a loose end.** The
  port-authority→Amazon conveyance (202511180011830) places a *second* cloud
  consumer on the same corridor. Read through the regional cloud-consumer lens, the
  material question is the **aggregate** demand and basin/grid burden of two
  hyperscale loads — not whether the two developments are corporately linked, which
  remains unestablished. `[open]`
- **Resolution noise.** A few contact entities remain coarse (the model
  occasionally merged two names or a name+firm into one field); see the graph.

---

## 11. Method & provenance

Every claim here derives from a committed artifact under `data/extracted/**`,
produced by the `ingest → extract → analyze` pipeline (hybrid OCR+vision or
text-first reads, Pydantic-validated, with self-reported confidence and warnings).
The cross-document entity graph and timeline are deterministic functions of those
artifacts (`bosc entities`, `bosc timeline`) — re-runnable and auditable. Figures
transcribed from degraded scans may carry a `~` approximate marker; permit and
instrument numbers are copied exactly. This dossier reflects the corpus **as
extracted so far** and should be regenerated as new documents are ingested.
