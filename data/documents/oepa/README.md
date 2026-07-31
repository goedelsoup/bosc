# Ohio EPA NPDES permits & fact sheets (original records)

**Collection:** `oepa/` · immutable source evidence

Ohio EPA NPDES permit documents for the sanitary/wastewater facilities relevant to
the BOSC corridor. Raw bytes are never edited; structured reads live in the mirrored
[`data/extracted/oepa/`](../../extracted/oepa/) as `*.npdes.yaml`.

## Contents

### Site-specific NPDES permits

Three document types per permit number — the issued **permit**, its **fact sheet**,
and the **draft public notice** (`draft-pn`):

| Permit | Facility |
|---|---|
| `2PH00006` | American II |
| `2PH00007` | American / Bath |
| `2PK00002` | Shawnee II |

Filenames carry the permit number, facility slug, document type, and (where stated)
a date. Each PDF keeps its as-received name; provenance is recorded in the matching
extraction's `meta` block.

#### `2PE00000.pdf` — City of Lima WWTP (the un-requested municipal custodian)

**Ohio EPA NPDES Permit Renewal** — permit `2PE00000*OD` (application `OH0026069`),
the **City of Lima WWTP**, 1200 Fort Amanda Road, Lima, Allen County. Final outfall
`2PE00000001` discharges to the **Ottawa River at River Mile 37.6**; average design
flow **18.5 MGD**, peak wet-weather **70 MGD**. Effective 2023-07-01, expires
2028-06-30. Single PDF: issued permit (79 pp.) + Fact Sheet for NPDES Permit Renewal
(pp. 77-118); 119 pp. total. As-received DAM name kept (bare permit number, as with
`2DP00130.pdf`); provenance + content-verification in [`filename-map.yaml`](filename-map.yaml).

This is the **municipal receiving plant** whose own permit and design flow the corpus
previously lacked (greps returned American-Bath `2PH00007` / Shawnee II `2PK00002`,
never Lima's plant). Obtained from the Ohio EPA DAM as a **public record — no records
request** (issue #1536). The reported effluent record (DMRs) is a sibling artifact:
[`data/extracted/oepa/lima-wwtp-OH0026069.dmr.yaml`](../../extracted/oepa/lima-wwtp-OH0026069.dmr.yaml).

### Site sub-collections

Permits belonging to a non-Lima network site sit in a slug sub-directory with their own
`filename-map.yaml`: `sidney/`, `troy-piqua/`, `urbana/`, `van-wert/`, `wilmington/`, and —

#### `findlay/` — City of Findlay Water Pollution Control Center, `2PD00008` / `OH0025135`

The Blanchard subbasin's anchor POTW (15 MGD average design, 40 MGD peak) and the third-largest
grouped-load phosphorus discharger in the Maumee watershed. Three files:

- `2PD00008.fs.pdf` — Fact Sheet for NPDES Permit Renewal, 2024 (`2PD00008*UD`, Public Notice
  205259, noticed 2024-08-09), 33 pp. The anchor instrument: outfall `2PD00008001` to the
  **Blanchard River at River Mile 56.42**, HUC `04100008-03-04`; Table 12's annual **7Q10 of 0.21
  cfs** against a 23.208 cfs design flow, giving an **acute dilution ratio of 1.0**; the renewed
  mercury variance (3.3 ng/L monthly against a 1.3 ng/L WQBEL, annual condition ≤ 12 ng/L); WET
  limits removed to monitoring only; total phosphorus 1.0 mg/L / 56.8 kg/day on a technology basis;
  ten authorized CSOs and eight significant industrial users.
- `2PD00008.pdf` — the **`2PD00008*VD` modification package** (52 pp.): Director's transmittal
  letter 2025-11-07, the modified permit effective 2026-02-01 (expiring 2029-10-31), and the
  modification's own 8-page fact sheet from p. 45. Its whole substance is moving the Municipal CSO
  Schedule milestone (event 34099) and the LTCP Addendum to **2026-11-01**.
- `2PD00008.1abaf306.pdf` — the **draft public notice** of that modification (PN 216133, noticed
  2025-11-14), 55 pp. Ohio EPA serves it from `permits/DraftPN/` under the *same* basename as the
  issued permit, so the fetcher's non-destructive collision rule kept both bytes and suffixed this
  one with its own sha256 prefix. See [`findlay/filename-map.yaml`](findlay/filename-map.yaml).

⚠️ **The DAM's `permits/doc/` slot for this permit serves the MODIFIED package, not the 2024 `*UD`
renewal it modified.** The `*UD` permit as issued is not obtainable from that slot; its term
(effective 2024-11-01, expires 2029-10-31) is recorded instead from the January 2026 variance list
below. Structured reads: [`data/extracted/oepa/findlay/`](../../extracted/oepa/findlay/).

### Basin general permits

#### `OHP000001.pdf` / `OHP000001_FS.pdf`

**Maumee Watershed Total Phosphorus NPDES General Permit** — effective 2023-11-01, expires
2028-10-31, signed by Director Anne M. Vogel. The instrument that makes the Maumee Watershed
Nutrient TMDL's individual wasteload allocations enforceable across **39 facilities**, supplementing
each permittee's own NPDES permit rather than superseding it (Part IV.C.6). Part I.C.1 lists the
eligible facilities with their receiving streams; Part IV.A.1 lists each one's seasonal Individual
Load Limit in kg of total phosphorus for the March-July spring season.

Its compliance rule is the load-bearing clause (Part IV.C.3): a permittee is in violation of its
Individual Load Limit **only if** the 39-facility Cumulative Load *also* exceeds the Cumulative Load
Limit. Compliance is evaluated at the group first, so an individual plant over its own allocation is
in compliance while the bubble holds. Basin-wide, not site-specific — Lima (`2PE00000`, 4000 kg),
Van Wert (`2PD00006`, 1000 kg), Defiance, Bowling Green and Findlay (`2PD00008`, 3200 kg) are all
covered rows. Structured read of the Findlay row:
[`data/extracted/findlay/tmdl/maumee-tp-wla-2PD00008.epa.yaml`](../../extracted/findlay/tmdl/maumee-tp-wla-2PD00008.epa.yaml).

#### `Jan_2026_List_of_Variances.pdf`

Ohio EPA's **statewide list of water-quality-standards variances**, January 2026 — one row per
variance with the discharger, permit number, outfall, permit effective and expiration dates,
affected water body, pollutant, and Modified Allowable Ambient Concentration. Statewide, not
site-specific.

It is the only committed instrument that states the term of Findlay's `2PD00008*UD` permit
(`11/1/2024` – `10/31/2029`), because the DAM no longer serves that issuance; it also carries
Findlay's mercury MAAC of 3.29 ng/L and independently names the Blanchard River as the affected
water body.

### Indirect discharge permits (pretreatment)

#### `2DP00130.pdf`

**Ohio EPA Indirect Discharge Permit** — Permit No. 2DP00130\*AP (Public Notice No.
222503, July 1, 2026; Application No. OHP000437). A pretreatment permit to a POTW
that does **not** have a State Approved Pretreatment Program — the discharge goes to
the sewer, not to a surface water. Single combined PDF: public notice + draft permit
(24 pp.). Draft; issue/effective dates TBD, expiration December 31, 2028.

- **Applicant:** BISTROZZI LLC, 4110 N Cole St, Lima, OH 45801, Allen County.
- **Facility:** named **"Bosc"** on the discharge line — same address; a **data center**.
- **Discharge:** domestic waste + **non-contact cooling water**, through a private
  sanitary main to a temporary lift station, into the **American – Bath WWTP** (POTW,
  3226 N. Cole St, Lima).
- **Key parameters:** water temperature, pH, flow rate.

**Lima relevance:** unlike the closed-loop cooling seen elsewhere, this filing puts a
Lima data center's **cooling-water discharge on the sanitary side** to the American–Bath
POTW — a direct hook into the Lima water thesis and the Bistrozzi entity thread
([`permits/bistrozzi-permits/`](../permits/bistrozzi-permits/)). The as-filed facility
name "Bosc" is preserved as received.

The receiving POTW is the **same American–Bath WWTP** carried above as `2PH00007` — that
permit governs the plant's own surface discharge (to Pike Run). So the corpus now records
the full chain: the "Bosc" data center discharges **into** the American–Bath POTW
(`2DP00130`), which in turn discharges **out** under `2PH00007`. The entity graph builds
this automatically from the extraction (`Bistrozzi → operates → Bosc → discharges_to →
American – Bath`, edge ref `2DP00130*AP`).

### Statewide general permits

#### `OHD000001_Draft.pdf` / `OHD000001_Draft_PN.pdf` / `OHD000001_Draft.fs.pdf`

**Ohio EPA Draft General NPDES Permit for Data Center Facilities** — Permit No. OHD000001.
Ohio's first statewide general permit class specifically for data center discharges. All
three document types: draft permit (31 pp.), public notice (2 pp., No. 215991), and fact
sheet (7 pp.).

Issued: October 31, 2025. Public hearing: December 17, 2025.
Director: John Logue. Contact: Allison Cycyk [Allison.Cycyk at epa.ohio.gov], 330-963-1132.

**Scope:** Cooling water (once-through and recirculated), low-volume wastewaters (cooling
tower blowdown, boiler blowdown, air compressor condensate), stormwater. SIC code 7374.
Excludes: >2 MGD surface water intake, thermal limit exceedances, within 500 yards of a
public water supply intake, Outstanding State Waters, Ohio River direct discharge.

**Antidegradation:** OAC 3745-1-05(D)(1)(j) invoked — social/economic development
carve-out applied. No alternatives analysis required.

**Lima relevance:** The 500-yard-upstream-of-intake exclusion is the key eligibility gate
for any data center on the American Sugar Creek / Ottawa River corridor near Lima's water
supply intake.

⚠️ **This general permit was abandoned. It will never issue.** On **July 21, 2026** Ohio EPA
posted a Community Notice on its NPDES General Permits page: *"After carefully reviewing the
significant volume of public comments received on the draft National Pollutant Discharge
Elimination System (NPDES) general permit for data centers, Ohio EPA has decided not to move
forward with finalizing the general permit. The individual NPDES permit issuance process is
the most appropriate path forward at this time."* The three draft documents above stay in the
corpus as what they are — a **draft that died at comment**, evidence of what Ohio EPA proposed
and then withdrew, not a live eligibility screen. Every site record that treats OHD000001 as
the expected coverage path for a data-center discharge is now wrong on its face; the path is an
**individual** NPDES permit, facility by facility.

Captured page:
[`2026-07-21-ohio-epa-will-not-finalize-data-center-general-permit.npdes-general-permits.html`](2026-07-21-ohio-epa-will-not-finalize-data-center-general-permit.npdes-general-permits.html)
— the Ohio EPA page bytes as served on 2026-07-31, carrying the notice verbatim. Provenance in
[`filename-map.yaml`](filename-map.yaml).
