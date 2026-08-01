# Ottawa (ottawa) — extractions

Per-site tree for the Ottawa watershed point (basin: maumee). Two kinds of artifact live here:
**onboarding seeds** scaffolded by `watermark onboard ottawa` (#326) from the portable reach
connectors, and **reviewed reads of primary instruments** transcribed from documents committed
under [`data/documents/ottawa/`](../../documents/ottawa/) and
[`data/documents/oepa/ottawa/`](../../documents/oepa/ottawa/). Nothing here is fabricated;
connector output is regenerated, not hand-edited.

## The standing water watch (#1422)

[`water-watch.yaml`](water-watch.yaml) — the site's standing regulatory watch on **both sides of
the Blanchard River**. Ottawa draws its drinking water from the river and returns its treated
sewage to it about a mile and a half downstream, and both sides went into violation in the same
twelve months.

| Side | Instrument | Status at 2026-07-31 |
|---|---|---|
| Discharge — NPDES OH0026921 / `2PD00028*PD` | mercury monthly average cut 6.8 → **4.5 ng/L** at the 2025-03-01 renewal | 3 exceedances (Sep 2025 **113%**, Dec 2025 **716%**, Feb 2026 23%); Category-I SNC; one warning letter; **no formal enforcement, $0 penalties** |
| Intake — PWS OH6900711 | Stage 2 DBPR total trihalomethanes, 80 ppb MCL | **two consecutive** MCL violations, 0.083 then **0.086 mg/L**; EPA "Enforcement Priority"; 12 of 12 quarters in noncompliance |

Two findings the watch exists to carry:

- The 4.5 ng/L limit **is the plant's own average**. Fact-sheet Table 8 gives its projected
  effluent quality over 63 mercury samples, 2019-2024: PEQ average 4.5 ng/L. A limit set at a
  plant's demonstrated mean converts ordinary upward variance into a permit violation. Two of the
  three exceedances would still have violated the old 6.8 ng/L limit; only February 2026 is new.
- **December 2025 discharged more mercury than it received** — 36.70 ng/L effluent against 20.3
  ng/L influent, on an ordinary influent month. The two *highest* influent months (74.9 and 118
  ng/L) removed 97.8% and 95.3%. The exceedances do not track the influent, and no committed
  source explains why.

The watch also records what the same record says on the other side of the ledger: Ohio EPA's own
conclusion that "the river section downstream of the WWTP is in full attainment for aquatic life"
and the 2009 TMDL finding of no apparent impact on fish and macroinvertebrate assemblages — both
carried with their vintage stated.

Cadence is **quarterly**, keyed to the ICIS-NPDES and SDWIS extract cycles. The next check's
questions and thirteen open leads are in the file's own `watch_schedule` and `open_leads` blocks.

## The anchor place (#1420)

[`bosc-site-footprint.yaml`](bosc-site-footprint.yaml) — the **former Sylvania / GTE / Philips
Display Components (LG.Philips Displays USA) CRT plant campus** at 700 and 804 North Pratt Street,
the site's anchor place and the geometry that activates the `places` readiness domain. The
boundary is the recorded ownership holding: the **two contiguous parcels** the works was
subdivided into and sold as in the 2006 Chapter 11, **38.234 ac deeded / 38.293 ac planar**,
committed as [`../../reference/ottawa/parcel-assemblage.geojson`](../../reference/ottawa/parcel-assemblage.geojson).

**It is not a data-center campus** — it is a closed industrial works, the county's largest employer
until 2002-12-31, now a **$4,571,596** three-round Ohio Brownfield Remediation Program remediation.
Ottawa's `SiteProfile` carries `facilities=()`. Three findings the record carries:

- **A named stream runs through the contaminated campus.** Tawa Run crosses **325.8 m** of the
  boundary — 305.2 m through 804 N Pratt and **20.5 m through the 22-ac remediation property
  itself** — and discharges directly into the Blanchard River, 525.9 m away. **4.505 ac (11.8%)**
  of the campus is Special Flood Hazard Area and **1.221 ac (3.2%)** is regulatory **floodway**.
  Whether the remediated contamination has any pathway to that stream is `[open]`: no analytical
  data, monitoring-well record or work plan is in the corpus. The geometry raises the question;
  it does not answer it.
- **The soil group was wrong, in both halves.** SSURGO over the committed boundary returns the
  dual group **C/D**, not the profile's prior `[inference]` flat **D**, and the soils under it are
  **Toledo/Fulton/Lucas** — none of the Hoytville/Latty/Paulding the inference named. The general
  reasoning (Great Black Swamp lake plain) survives; the specifics did not. And **61% of the grid
  is Urban land**, unrated — the group describes the campus's unbuilt remainder.
- **Ownership is not the brownfield grantee.** The awards went to the Port Authority of
  Northwestern Ohio (Rounds 1, 11) and the Putnam County Land Reutilization Corp (Round 5);
  the parcels stand in the names of OTTAWA OH LLC (mail c/o APTM INC, Long Beach CA) and VERHOFF
  PROPERTIES LLC. No instrument in the corpus connects the two, and the grantor chain is `[open]`
  (#1421).

## The facility posture (#1423) — a documented negative

[`data-centers.md`](data-centers.md) — the site's data-center activity register, and the one
register in the network whose **finding is that there is nothing to find**. No data-center,
AI-campus, hyperscale or large-load project is announced, rumored, rezoned, land-optioned,
permitted or queued in Putnam County or the Village of Ottawa, 2024–2026. The `SiteProfile` carries
`facilities=()` and the `facility` readiness domain stays **locked** — because the sweep ran and
came back empty, not because it was never run.

The 2026-06-21 self-research pass could only say the *corpus* was empty. This register queries six
record systems that would carry a project whether or not BOSC had heard of it:

| Check | Result at 2026-07-31 |
|---|---|
| PJM interconnection queue (9,263 projects) | 9 Putnam entries, all **generation**, all wind/solar, nothing above 138 kV — and the queue carries **no load-interconnection type at all** |
| ODJFS WARN, 2024 + 2025 + 2026 (241 notices) | **One** Putnam hit — and it is a **closure**, not an arrival (below) |
| EPA ECHO ICIS-Air (33 facilities) | 3 majors — POET and PRO-TEC at Leipsic, plus the **closed** Philips CRT works; **zero NAICS 518210** |
| EPA ECHO CWA (48 permits, 14 active construction NOIs) | Every NOI is a road, utility, municipal or small-commercial job; no campus grading |
| EPA RSEI v234 (14 TRI reporters) | No 518210; the county's top scorer is the closed CRT works |
| BLS QCEW 2023 | Information (NAICS 51) **LQ 0.21** on 50 jobs; Manufacturing **LQ 3.72** |

Three findings the register exists to carry:

- **The closure negative does not close clean.** ODJFS WARN notice **007-24-042**: *RK Industries,
  Inc.*, 725 N Locust St, Ottawa — automotive stamping and robotic welding — noticed **2024-05-16**,
  operations expected to cease **2024-07-14**, **~80 employees**, none union. The village noticed
  the loss of an 80-job plant twenty-two years after it lost the CRT works. **Now committed**:
  [`warn/rk-industries-ottawa-2024.warn.yaml`](warn/rk-industries-ottawa-2024.warn.yaml). The
  closure is *expected*, not confirmed — the letter conditions the cease date on no intervening
  sale or merger, and what actually happened is `[open]`.
- **The county exports to the build-out it does not host.** Putnam's SB 52 blanket restriction
  (Sept 2023) capped its renewables pipeline at two grandfathered projects, and PJM's own queue
  confirms both reached service — Powell Creek (150 MW, 2025-04-30) and **Blue Harvest** (49.9 MW,
  2023-11-22), whose output is contracted to **Amazon/AWS**. The land use lands here; the load, the
  abatement, the jobs and the water draw land somewhere else.
- **The disambiguation trap is load-bearing.** **Putnam County, *West Virginia*** has a live
  multibillion-dollar Google campus (~1,700 ac at Buffalo, announced March 2026) and owns the
  obvious search terms. It has nothing to do with FIPS 39137.

One check stays **`[open]`**: the paywalled Toledo Blade article of 2025-12-13, "Where will the next
northwest Ohio data centers be built?" — the Internet Archive holds only the paywall shell.

## Primary instruments

- [`drinking-water/oh6900711-2025-ccr.epa.yaml`](drinking-water/oh6900711-2025-ccr.epa.yaml) — the
  Village's 2025 Consumer Confidence Report (distributed 2026-07-01), with the bound TTHM and lead
  service-line public notices. ⚠️ Served under a URL slug reading `2024-CCR`; it is the 2025 report.
- [`../oepa/ottawa/2PD00028.fs.npdes.yaml`](../oepa/ottawa/2PD00028.fs.npdes.yaml) — the NPDES fact
  sheet. The anchor water record: 7Q10 **7.78 cfs**, the mercury variance derivation, the reach's
  use designations (which do **not** include Public Water Supply), the 2009 aquatic-life finding.
- [`../oepa/ottawa/2PD00028.npdes.yaml`](../oepa/ottawa/2PD00028.npdes.yaml) — the permit as
  issued, including Part II Item X.3, the clause that excuses the annual mercury ceiling where the
  mercury came from "the permittee's intake water."
- [`warn/rk-industries-ottawa-2024.warn.yaml`](warn/rk-industries-ottawa-2024.warn.yaml) — the
  RK Industries WARN notice (#1423), the only one filed from Putnam County in 2024–2026. Publishes
  under the `labor` record group. ⚠️ A **scan**: the read is a 300 DPI vision transcription, and
  all three of its headcounts are handwritten.

## Onboarding seeds

Values from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites`
(NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER). See [`ONBOARDING.md`](ONBOARDING.md).

## Known gaps & caveats

- Onboarding seeds are **not** reviewed instruments — check every value against a cited source
  before promotion (`web/packages/core/src/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable
  reach connectors — see `docs/onboarding.md`.

## Regenerate

`watermark onboard ottawa` regenerates the connector seeds only. The instrument reads and the
water watch are reviewed transcriptions and are **not** regenerable; refresh the watch by re-running
its recorded routes (see `water-watch.yaml` `meta.method`) and appending, not overwriting.
