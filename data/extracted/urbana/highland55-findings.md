# Highland55 — investigative findings

**Corpus**: `data/documents/permits/highland55/` (10 instruments, PR #803)
**Issue**: #447 (**resolved 2026-07-09**, #1328) · sub-issue of #1263
**As of**: 2026-07-09

> **Resolution (#1328).** The `[open]` data-center end-use is resolved and lead #447 is
> closed. The land assembly is sourced to the Champaign County auditor CAMA record — four
> parcels, three Thor single-purpose entities, deed Official-Record book/page for each — in
> [`land-assembly.yaml`](land-assembly.yaml); the geometry is `parcel-assemblage.geojson`
> (#1326). The end-use is now **data center campus ("Urbana Technology Hub")**, tagged
> `[reference]` on the public disclosure (Urbana Daily Citizen, 2026-02-18 "Data center plans
> revealed at city meeting"; 2026-06-14) + the Thor v. Urbana litigation tracked under #1263 —
> no longer `[open]`. A facility-naming primary instrument (air/building permit, interconnection)
> would take the end-use itself to `[verified]`; the land assembly, developer, and considerations
> already are. See the **Land assembly** section below.

## Verified facts from primary instruments

| Fact | Source | Tag |
|---|---|---|
| Developer: **Highland Realty Development LLC / Urbana Owner I LLC**, 720 E Broad St Suite 200, Columbus OH 43215 | Prelim JD cover (3938251) | `[verified]` |
| Contact: **Brian Hughes-Cromwick, VP Acquisitions, Thor Equities** (bhcromwick at thorequities.com) | 401 WQC application (3938244) | `[verified]` |
| Location: west of S U.S. Highway 68, **Urbana Township, Champaign County, OH** | Approved JD cover (3938271) | `[verified]` |
| Vance Brands parcel coordinates: **40.0887°N, -83.7611°W** | Approved JD (3938271) | `[verified]` |
| Vance Brands parcel ID: Champaign Co **K48-25-11-01-30-001-00**, current owner **Brand Investments LTD** | Approved JD (3938271) | `[verified]` |
| Vance Brands parcel area: **~47.6 acres** (agricultural field + wooded fringe) | Approved JD (3938271) | `[verified]` |
| Vance Brands parcel: **no wetlands, no streams** — one non-jurisdictional erosional feature (1,206 LF) | Approved JD (3938271) | `[verified]` |
| Commerce Park AOI: **~40.0812–40.0851°N, -83.7637–83.7645°W** | Prelim JD (3938251) | `[verified]` |
| Commerce Park wetlands: Wetland A (1.31 ac, Cat 1 non-jurisd.) + Wetland B (0.06 ac, Cat 1 non-jurisd.) | Prelim JD (3938251) | `[verified]` |
| Project name in 401 WQC: **"Urbana Brand I"** | 401 WQC (3938244) | `[verified]` |
| 401 WQC project description: "commercial retail buildings, **an industrial warehouse**, **a electrical substation**, roads, parking, stormwater" | 401 WQC (3938244) | `[verified]` |
| 401 WQC project purpose: **"build-to-suit commercial development for future tenants"** | 401 WQC (3938244) | `[verified]` |
| Construction timeline: **06/01/2026 – 06/01/2027** | 401 WQC (3938244) | `[verified]` |
| Wetland impact: **0.07 acres** across three Category 1 non-forested wetlands | 401 WQC (3938244) | `[verified]` |
| Corps district: **Huntington WV** (Teresa Spagna, contact) | Prelim + Approved JD covers | `[verified]` |
| Engineer: **Civil & Environmental Consultants, Inc. (CEC)**, Columbus OH | All instruments | `[verified]` |
| CEC sub-projects: 344-735 (Commerce Park prelim JD), 352-387 (Vance Brands approved JD), 354-449 / 355-192 (third parcel, wetland photos) | 401 WQC (3938244), photo report (3938260) | `[verified]` |
| Photo dates for wetland documentation: **June 26 & July 28, 2025** | Photo report (3938260) | `[verified]` |
| SSURGO (Vance Brands, 352-387): 7 units — BsA (hydric), CnB, CrA, FnA, MIB, MIC2, WsA | Approved JD (3938271) | `[verified]` |
| FEMA flood status: AOI **not in 100-year floodplain** (both parcels) | Both JDs | `[verified]` |

## Land assembly (#1328)

The recorded ownership assemblage behind the Urbana Technology Hub, sourced to the Champaign
County auditor CAMA (`parcel_joined` FeatureServer 0) — full register in
[`land-assembly.yaml`](land-assembly.yaml). Grantee, deed OR book/page, date, and consideration
are `[verified]` from the auditor; grantors are `[reference]` (Urbana Daily Citizen) corroborated
`[inference]` by the parcel-acreage/price triangulation.

| Grantor | Grantee (Thor SPE) | Parcels | Acres | Consideration | Date | Deed (OR) |
|---|---|---|---|---|---|---|
| Brand Investments LTD `[ref]` | **Urbana Owner I LLC** | K48-25-11-01-30-001-00 | 47.637 | $2,143,665 | 2025-08-22 | OR601/4948 |
| Brand Investments LTD `[ref]` | **Highland55 Investments LLC** | K48-25-11-01-32-005-00 | 85.619 | $3,210,712.50 | 2025-11-18 | OR603/1927 |
| Organ Farms LLC `[ref]` | **Urbana Owner II LLC** | K48-25-11-01-30-005-00 + -006-00 | 97.09 | $3,398,150 | 2026-06-12 | OR606/3352 |

- **Brand disposition**: the two Brand parcels sum to **133.256 ac** and **$5,354,377.50** —
  reconciling the reported "133 acres … more than $5.5M in H2 2025" `[reference]` (the news ">$5.5M"
  is approximate). `[inference]`
- **Organ Farms**: 7.09 + 90.0 = **97.09 ac** — an exact match to the reported figure; the auditor
  records both parcels on **one deed (OR606/3352)**, $3,398,150 ≈ "nearly $3.4M". `[inference]`
- **Excluded seller-residual**: Brand Investments LTD retains K48-25-11-01-32-021-00 (OR601/4518,
  ~22.5 ac) — not transferred. `[verified]`
- **Champaign County** holds an **unexercised** land-purchase option with Thor in the same area
  (commissioners reportedly signed before learning of the data-center plan). `[reference]`
- **Open**: the recorder's sequential instrument numbers and the Ohio SoS registered agents
  (incl. the "Form8tion" Thor unit) — the SoS was not reachable from this environment; see the
  `limitations` block in `land-assembly.yaml`.

**Kept strictly separate** from the Allen-County / Lima Bistrozzi land-assembly graph — no
cross-reference; no filed instrument bridges them.

## Signal analysis

**Data-center indicators:**

- **Electrical substation** — the 401 WQC explicitly includes a dedicated substation in the
  project description. Standard warehouse/retail development uses the utility's padmount transformer;
  a dedicated substation indicates high-voltage service (typically 69 kV or 115 kV stepped down
  on-site) for a load >5–10 MW. This is the strongest data-center signal in the corpus. `[inference]`
- **Build-to-suit for future tenants** — developer language common in data center site acquisition,
  preserving tenant anonymity during permitting. `[inference]`
- **"Vance Brands" as named end user** — the name appears in Corps JD filings but is not identified
  in public business records available to the corpus. May be a project codename or SPE name.
  `[open]`
- **47.6+ acre greenfield site** — consistent with a campus-scale facility but also with
  large-format logistics/manufacturing. `[inference]`
- **Thor Equities as developer** — primarily a commercial real estate developer (retail, office,
  industrial); history includes large-format industrial build-to-suit projects. Not a specialist
  data center developer, which is a mild counter-signal. `[inference]`

**Counter-indicators / open questions:**

- Project description includes "commercial retail buildings" — atypical for a pure data center
  campus; could indicate a mixed-use development or placeholder language. `[open]`
- NPDES General Permit scheduled for 03/31/2026 — likely a construction stormwater general
  permit (OHC000002), which all large construction projects require. Not specific to data centers.
- No power spec, cooling system type, or floor plan density visible in available instruments
  (exhibits are image-only, no text layer).

## What the instruments do NOT tell us

- Total project acreage (the full assembly — Commerce Park + Vance Brands + 354-449/355-192
  parcels combined; only the 47.6-acre Vance Brands parcel is measured)
- Any power or load specification
- Cooling system type (once-through, evaporative tower, dry)
- Whether "Vance Brands" is a data center operator or another industrial tenant

## Assessment

Highland55 is a **real, active development project** — not a rumor. Thor Equities has
assembled **~230 ac** (four parcels, three single-purpose entities) west of US-68 / SR-55 in
Urbana Township, with a dedicated electrical substation; construction is planned for mid-2026.
The end use is **resolved** to the **Urbana Technology Hub data-center campus** (#1328).

**Current evidentiary state** (updated 2026-07-09, #1328):

- **Land assembly, developer, considerations, deed references** — `[verified]` from the
  Champaign County auditor CAMA (see the Land-assembly table and `land-assembly.yaml`).
- **Data-center end-use** — `[reference]`, resolved from `[open]`: the project is explicitly and
  repeatedly named a data center in public reporting (Urbana Daily Citizen) and was disclosed at a
  public City of Urbana meeting; the Thor v. Urbana litigation is tracked under #1263.

To take the **end-use itself** from `[reference]` to `[verified]`, a facility-naming primary
instrument is still wanted — any of:

- A utility interconnection application showing the expected load (MW)
- An air permit or building permit that names the facility type
- An ODOD/JobsOhio or CRA/PILOT record identifying the tenant

These are tracked in the sibling #1263 catch-up issues, not lead #447 (now closed).
