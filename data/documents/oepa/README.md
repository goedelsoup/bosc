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
