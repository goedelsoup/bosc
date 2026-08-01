# Thor Equities v. City of Urbana — litigation & zoning timeline

**Case**: *Thor Equities, LLC et al. v. City of Urbana, Ohio et al.*, No. **3:26-cv-00196-MJN-CHG**
(U.S. District Court, S.D. Ohio, Western Division), filed **2026-06-19**.
**Source**: [`data/documents/legal/thor-v-urbana/1.pdf`](../../documents/legal/thor-v-urbana/1.pdf) (Complaint, Doc #1, 37 pp).
**Structured record**: [`litigation-thor-v-urbana.yaml`](litigation-thor-v-urbana.yaml).
**Issue**: #1329 · sub-issue of #1263 · strengthens `record` + `story`. **As of**: 2026-07-10.

> **Tagging.** The complaint is a **filed primary court instrument**, but a party's pleading.
> What the case *is* (docket, parties, counts, relief) is `[verified]` — read from Doc #1. What
> Thor *alleges* (pretext, the dollar figures, wrongdoing) is `[reference]` — a party's
> averment, attributed and not adjudicated. The ordinance/moratorium record the complaint
> *recites* is `[reference]`; the underlying instruments (Exhibits 1–9) are **not** attached to
> Doc #1 and stay `[open]`.

## What this resolves for Urbana

This is the litigation the corpus had tracked only by reference (highland55-findings.md,
datacenter-facility.md, land-assembly.yaml all pointed at "Thor v. Urbana … tracked under
#1263"). The **federal case is now in corpus** as a primary instrument. It corroborates the land
assembly from a second source, adds a fifth entity, and — as a party's pleading — **alleges** the
**data-center end-use**:

- **Land assembly `[verified]` corroboration.** The four owned parcels and their owning SPEs in
  Doc #1 ¶¶10–13 match the Champaign County auditor CAMA record in
  [`land-assembly.yaml`](land-assembly.yaml) exactly — now confirmed by a filed federal
  instrument, not only the auditor layer + press. The **owned** holding is **~230.346 acres** (¶13,
  the four owned parcels). Doc #1 adds a **fifth entity, Urbana Owner LLC**, the contract purchaser
  of two *further* parcels (K48-25-11-01-36-001-00 and a portion of -37-001-00), **additional** to
  that 230.346 ac and not yet conveyed — their acreage is not stated in the complaint (`[open]`).
- **The mailing question — partly clarified, not fully resolved.** land-assembly.yaml flagged the
  mismatch between the auditor mailing (3040 Riverside Dr) and the §401 WQC address (720 E Broad
  St). Doc #1's **caption** lists all four Urbana Owner / Highland55 SPEs at **3040 Riverside
  Drive, Ste 122, Columbus** and Thor Equities LLC at **25 W 39th St, New York**. But the auditor
  CAMA agrees only for Highland55: it records **Urbana Owner I and II at 25 W 39th St, New York**
  (c/o Thor). Reconciling the caption vs auditor address for those two stays `[inference]/[open]`
  pending the Ohio SoS registered-agent pull.
- **The end-use.** Thor **alleges** the Project is a **data center** — as a party's pleading this
  is `[reference]`, not independent verification. The complaint also **recites** an ordinance record
  (`[reference]`): the City amended M-1 to permit "Computing Infrastructure Providers, Data
  Processing, Web Hosting, and Related Services" (Ord. 4621-25) specifically for this land, then
  moved to remove that use — which frames the entitlement *dispute* as over a data center. The
  underlying ordinances are **not attached** to Doc #1 (Exhibits 1–9 are separate ECF filings) and
  stay `[open]`; ingesting them is what takes this record `[reference]` → `[verified]` (#1359). It
  does **not** disclose the facility's MW load, cooling, tenant, or operator, which remain
  `[open]` (see [`datacenter-facility.md`](datacenter-facility.md) §4/§7).

## Zoning + litigation timeline

Dates are `[reference]` as recited by the complaint unless a corpus instrument corroborates
(noted). Paragraph cites are to Doc #1.

| Date | Event | Cite | Tag |
|---|---|---|---|
| Dec 2024 | Thor begins working with Urbana Planning & Zoning staff on the data-center project | ¶41 | ref |
| 2024-11-19 → 12-17 | **Ord. 4612-24** — the City authorises a **Pre-Annexation Agreement** with `Urbana0624C, LLC` (which the City identifies as "Highland"); passed **5-0**. Its §3(c) obliges the City to **de-annex on the developer's demand** if the rezoning disappoints. Not pleaded in Doc #1 (#1354) | Ord. 4612-24 Ex. A | verified |
| 2024-12-03 | Annexation petition filed (Expedited Type II, R.C. 709.023) by agent Andrew Wecker for the landowners — Organ Farms LLC, the County Commissioners, MCESC, Urbana Health Facilities | Ord. 4612-24 · minutes | verified |
| 2024-12-17 | **Ord. 4613-24** (statement of services) and **Ord. 4614-24** (land use / zoning buffers) for the 219.986 ac — both emergency, both **5-0** | minutes | verified |
| 2025-04-22 | Council unanimously adopts **Ord. 4619-25** (annexation, 9 parcels ~219.986 ac), **4625-25** (zoning map → M-1), **4620-25** (Ch. 1102 data-center definitions), **4621-25** (Ch. 1126 — data centers principally permitted in M-1) | ¶¶36–40 | ref |
| 2025-08-22 | Vance Brands parcel conveyed to Urbana Owner I LLC (OR601/4948) | land-assembly.yaml | verified |
| 2025-11-04 | Council adopts **Ord. 4631-25** — CRA #2. Instrument now in corpus (#1354): passed **5-2**; it designates an *area* with ceilings, names no project, and **excludes** Thor's two first-bought parcels | ¶46 · Ord. 4631-25 | verified |
| 2025-11-18 | Highland55 parcel conveyed (OR603/1927) | land-assembly.yaml | verified |
| 2026-02-13 | Thor submits its **site-plan application** (Zoning Code Ch. 1110) for a data center | ¶54 | ref |
| 2026-02-17 | Moratorium placed on the Council agenda, then removed without a vote | ¶60 | ref |
| 2026-02-20 | City (Dir. of Admin. Spencer Mitchell) rejects the application as "incomplete" (cites Ch. 1161 subdivision items + a traffic study) | ¶56 | ref |
| 2026-03-03 | Council enacts **Resolution 2727-26** — a 12-month emergency **Moratorium** on data centers, immediate effect | ¶61 | ref |
| 2026-03-10 → 03-18 | Thor's R.C. 149.43 records requests for the Moratorium stonewalled; produced only after a written violation demand | ¶¶68–70 | ref |
| 2026-03-20 | Thor hand-delivers its **BZA appeal**; City staff decline to mark it served but accept the fee | ¶72 | ref |
| 2026-04-13 | **BZA hearing** — continuance denied; only 4 of 5 members present (4 votes needed); appeal denied, "incomplete" affirmed | ¶¶81–84 | ref |
| 2026-05-05 | Council refers **Resolution 2731-26** to the Planning Commission — initiates permanent removal of data centers from M-1 | ¶87 | ref |
| 2026-05-18 | Planning Commission recommends approval of the permanent removal | ¶88 | ref |
| 2026-06-02 | First reading of **Ordinance 4635-26** (permanent removal of data-center use from M-1) | ¶89 | ref |
| **2026-06-16** | **Ord. 4635-26 PASSES 6-0** — Ch. 1126 reverts to its pre-4621-25 text; data centers are no longer permitted in M-1. Three days before filing; Doc #1 recites only the June-2 first reading (#1354) | 2026-06-16 minutes | verified |
| **2026-06-19** | **Federal complaint filed** (3:26-cv-00196-MJN-CHG) | ECF header | verified |

## The eight counts

1. **Procedural due process** (§ 1983 + Ohio Const.) — deprivation of the vested data-center use without lawful process.
2. **Substantive due process** (§ 1983 + Ohio Const.) — the moratorium/denial/appeal were arbitrary and capricious.
3–6. **Declaratory judgment — the Moratorium (Res. 2727-26) is void ab initio** on four independent grounds: Charter § 2.12 (no emergency zoning amendments); Charter § 2.11 (no genuine emergency / facts not stated); Ohio Const. Art. XVIII § 3 + R.C. 731.30; and Charter §§ 2.10/2.16 + Zoning Ch. 1113 (publication, referral, notice, three-reading failures).
7. **Declaratory judgment — vested rights.** Filing the Feb-13 application *froze* the zoning rules (Golf Vill. N. LLC v. City of Powell, 6th Cir.; Gibson v. Oberlin, Ohio 1960); the later moratorium cannot retroactively defeat the use.
8. **Declaratory judgment — the site-plan denial violated Zoning Ch. 1110** — the City imported Chapter 1161 (major-subdivision) requirements and a traffic study that site-plan review does not require (ultra vires).

**Relief**: compensatory damages (jury); declarations voiding the Moratorium on all grounds and
declaring the Application complete + the use vested; a Rule 65 preliminary + permanent
injunction barring enforcement of the Moratorium and the amended Zoning Code against the
Property and directing approval; interest; § 1988 fees.

## The two remedies (public-records-and-legal-strategy)

The dispute runs on **two distinct tracks**, and #1329 deliberately separates them from the
network-global Allen-County records-mandamus (`docs/legal/mandamus-analysis.md`):

- **Land-use / vested-rights track (the federal case).** A *takings / zoning-reversal* posture:
  Thor front-loads the §1983 due-process and vested-rights theory and seeks to void the
  moratorium and compel approval. This is **not** a records-mandamus.
- **Records track (woven through the facts, ¶¶67–75).** A separate R.C. 149.43 Ohio Public
  Records Act thread in which a *private developer* is the requester and the *City of Urbana* the
  stonewalling agency — the mirror image of BOSC's own posture against Allen County. Captured in
  the YAML `public_records_thread`; it is context and a documented pattern, not this corpus's
  mandamus.

## Open ingest targets

- **Exhibits 1–9 to Doc #1** — the four Apr-2025 ordinances, Res. 2727-26, the Apr-10 counsel
  letter, the BZA response, the motion for continuance, and Ord. 4635-26. They are separate ECF
  attachments; ingesting them takes the ordinance record `[reference]` → `[verified]`.
- **The Champaign County Common Pleas administrative appeal** (R.C. Ch. 2506) — the *second* case
  named in #1329, referenced in ¶¶71–72 but not in corpus; its case number is `[open]`.
- **Later docket entries** in 3:26-cv-00196 (answer, any TRO/PI motion + ruling) — the case is
  live as of 2026-07-10.
- **The City-side ordinance/minutes record** for Res. 2727-26 and Ord. 4635-26.
