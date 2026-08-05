# Onboarding — Defiance (defiance)

Living record for the Defiance watershed point (basin: maumee), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile (Toledo Edison / ATSI, #236)
- [~] **Data-center activity** — self-research first pass run (`watermark research run`); see research summary + proposals below (#247)
- [~] **Per-jurisdiction GIS** — flood = shared national NFHL (wired). County parcels/zoning `[open]` — Defiance County GIS is on **bhamaps with an expired TLS cert** (same host/case as Van Wert); no AGOL opendata hub; City of Defiance zoning is map-only. See GIS discovery below.

## GIS discovery (2026-06-19; schema-driven GIS, #237)

Unlike Williams (rich AGOL) and Putnam (self-hosted valid ArcGIS), **Defiance County is the
bhamaps / expired-cert case — identical to Van Wert**: parcels are served through Bruce Harris &
Associates at `ags.bhamaps.com` (folder `DefianceOH`), whose **TLS certificate is expired**
(`curl: (60) SSL certificate problem: certificate has expired`; `ssl_verify=10`), so
`cached_get`/httpx cannot consume it without disabling verification (not done — won't weaken TLS
for an external host). No Defiance County ArcGIS Online opendata hub was found, and the City of
Defiance publishes zoning as map/PDF (`cityofdefiance.com/167/Districts-Zones-Maps`), not a REST
service.

| layer | endpoint | finding | status |
|---|---|---|---|
| floodzone | FEMA NFHL (national, layer 28) | wired in the profile (`gis_flood`) | wired |
| parcels (county) | `ags.bhamaps.com/.../DefianceOH/...` (Bruce Harris & Assoc); auditor Beacon at `auditor.defiance-county.com` | **TLS cert expired** — not consumable by the connector; parcels otherwise via the auditor Beacon viewer + Engineer's-office line work | `[open]` |
| zoning | City of Defiance "Districts, Zones & Maps" | map/PDF only; no zoning REST catalog found | `[open]` |

Follow-up (a research/issue lead): re-probe the Defiance County bhamaps PAT MapServer once its TLS
cert is renewed (then register a `GisParcelSchema` from the live field list) — this is the **same
fix as Van Wert's** (shared `ags.bhamaps.com` host), so renewal would unblock both at once; or fall
back to the Engineer's-office parcel shapefile. Accept City zoning as map-only here.

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/defiance/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/defiance/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/defiance/nasa-power-climatology.yaml |
| basin-screen | ok | 7/129 dischargers screened (1 violations, 2 tight) |
| econ-baseline | ok | reference/economics/defiance/baseline.yaml |
| rsei | ok | reference/rsei/defiance/inventory.yaml |
| consumer-energy | ok | reference/eia/defiance/consumer-energy.yaml |
| grid-profile | ok | reference/eia/defiance/grid-profile.yaml |

## Self-research (Phase 5; #247) — 2026-06-19

First automated-research pass (`watermark research run`, 21 turns, $1.58, read-only over the corpus) →
`data/research/onboard-defiance-maumee-mainstem-2026-06-19/` (`findings.md` + `manifest.yaml`).

**Headline — the mainstem thesis confirmed.** Defiance WWTP (OH0024899, 12 MGD ≈ 18.6 cfs — *superseded
by the permit's own 6.0 MGD, see the #392 note below*) → Maumee
mainstem, reach-specific dilution ≈ **7.5:1** (*superseded: 10.14:1 on the permit's own terms*)
("tight," not a violation) vs. Lima's tributary plants
at **0.01–0.42:1 (violations)** on the same screen. Same model, same basin, comparable plant size — the
only variable is the receiving water. **Lima's effluent-dominance is driven by receiving-water *choice*,
not plant size; Defiance is the clean confirmation** (cf. `docs/bigger-picture.md` §2).

**Reach-specific 7Q10 — RESOLVED (#391, 2026-07-03).** The earlier 6.2:1 used the Waterville gage
(04193500, DA 6330 mi²) ~50 river-miles downstream as the mainstem proxy. The honest at-reach
denominator is now derived: **USGS 04192500 (Maumee River near Defiance), LP3 7Q10 = 139.24 cfs**
(44 climatic years 1980–2024) → **7.5:1** (139.24 / 18.56 cfs). The a-priori expectation was that the
reach number would be *tighter* than 6.2:1 (Waterville drains more area) — the data **refutes** it:
the near-Defiance gage sits just downstream of the city and, per NWIS drainage areas (5545 mi²),
**already includes the Auglaize** (it is the mainstem *below* the confluence, not above), and its LP3
7Q10 comes out **higher** than Waterville's 114.15 cfs — so the reach-specific dilution is slightly
**looser (7.5:1), not tighter**. The Auglaize arm just above the junction is also derived (04191500,
18.62 cfs) for completeness. Net effect: the clean-confirmation thesis is **reinforced**, not
threatened — well above the 4:1 re-evaluation flag. Both values live in
`data/reference/hydrology/low-flow-7q10.derived.yaml` (source=derived, confidence medium: gage-value
proxies for the discharge reach; the exact outfall position relative to 04192500 and the OH0024899
permit-cited 7Q10 remain the open refinements — proposal #2). NB: `watermark basin-screen` still
reports 6.2:1 for Defiance because ECHO's bare "maumee river" receiving water aliases to the basin-wide
Waterville proxy by design; 7.5:1 is the documented site-level reach characterization, not an
auto-applied screen value (same convention as the Sidney/WPAFB/Fort Wayne reach entries).

**Permit-cited 7Q10 — RESOLVED (#392, 2026-08-05). Both terms of the ratio were wrong, in opposite
directions.** Ohio EPA NPDES fact sheet **2PD00013\*VD** is now in the corpus
(`data/documents/oepa/defiance/2PD00013.fs.pdf`, structured at
`data/extracted/oepa/defiance/2PD00013.fs.npdes.yaml`), retrieved through the Ohio EPA eDocument
public portal. It settles the outfall, the denominator **and** the numerator — and the numerator is
the surprise.

| term | corpus before #392 | permit 2PD00013\*VD | source of the corpus value |
|---|---|---|---|
| outfall | *unknown* | **Maumee River RM 62.05** | — |
| 7Q10 (cfs) | 114.15 (screen) / 139.24 (#391) | **94.1** | Waterville proxy / LP3 at 04192500 |
| design flow (MGD) | 12.0 | **6.0** | ECHO `CWPTotalDesignFlowNmbr` |
| design flow (cfs) | 18.5668 | **9.2834** | derived from the above |
| dilution | 6.2:1 (screen), 7.5:1 (#391) | **10.14:1** | — |

*The 7Q10 discrepancy is methodological, not a disagreement about the river.* Table 15 (printed
p. 31) states the basis for every stream-flow row as **USGS 04183500, 04191500, 04185000** — Maumee
at Antwerp (2129 mi²), Auglaize near Defiance (2318 mi²), Tiffin at Stryker (410 mi²): the three
arms **above** the city, drainage **4857 mi²** in total. #391 derived its 139.24 cfs at
**04192500**, the mainstem gage
just **below** the city, drainage **5545 mi²**. The permit therefore denominates on 87.6% of the
drainage the derived value sees, and its number lands **32% lower** (94.1 vs 139.24) and **18%
below** the Waterville proxy (114.15). Both are correct about different sections of river; only
94.1 cfs is the number the regulator allocates on.

*The design-flow discrepancy is a straight contradiction, and it is the larger error.* The permit
prints its average design flow three times — fact sheet printed p. 7, fact sheet Table 15 (sourced
to "NPDES Application Form 2A", converted to 9.2834 cfs), and issued permit Part II.H printed p. 30
— as **6.0 MGD**, with peak hydraulic capacities of 8.0 MGD (secondary) and 14.0 MGD (primary +
disinfection). ECHO's ICIS-NPDES `CWPTotalDesignFlowNmbr` for OH0024899 is **12 MGD**, which matches
none of the three, and the live ECHO read of 2026-08-05 still returns it. Everything the corpus has
said about Defiance — "12 MGD ≈ 18.6 cfs", 6.2:1, 7.5:1 — carries that doubled denominator.

*Net effect: the reach is looser than the corpus says, not tighter.* The two corrections push
opposite ways (numerator −18%, denominator −50%) and the denominator wins: **10.14:1**, against
6.2:1 on the record. The clean-confirmation thesis of §2 is **reinforced again** — Defiance is
further from the 4:1 re-evaluation flag than either earlier figure suggested, and further still from
Lima's 0.01–0.42:1. Two cautions travel with the number, both from the fact sheet's own face:

- This is a **three-way shared WLA segment**. Ohio EPA divides the allocation between Defiance WPC,
  GM Casting Operations (2IN00004) and GM's remediation discharge (2IN00202001); total permitted
  discharger flow is **11.225 cfs**, giving **8.38:1** across the segment.
- The fact sheet applies a **25% average mixing assumption**, so the flow actually available to the
  chronic WLA is 23.525 cfs — **2.10:1** against the segment's 11.225 cfs. That is not a dilution
  ratio in the basin screen's sense and is not comparable to one, but a reader who takes 10.14:1 as
  "headroom" is off by ~5× against what the regulator allocates on.

*Where the value lives, and why the screen did not move.* The cited reach is committed to
`data/reference/hydrology/low-flow-7q10.yaml` as `maumee river (defiance wpc outfall, rm 62.05)` and
to the profile's `plant_receiving`. It is **deliberately not `permits:`-bound**: `screen_facility`
takes its numerator from a `permits:` entry but its denominator from ECHO regardless, so binding it
today would print "94.10 cfs (cited AT THIS OUTFALL) vs discharge 18.57 cfs → 5.07:1" — a
permit-cited numerator over a denominator that same permit contradicts, under a label asserting the
whole line is cited. `watermark basin-screen` therefore still reports **6.15:1 / derived** for
Defiance, honestly labelled, and 10.14:1 is the documented site-level characterization — the same
convention #391 set. **Add the binding in the same commit that reconciles the ECHO design flow, and
not before.** The reconciliation belongs in a curation overlay
(`data/reference/echo/curation/`, #1698) rather than a hand edit to the regenerated inventory, and
today's overlay carries `ReceivingWaterCorrection` only — extending it to a design-flow correction
is a schema change and is filed as follow-up work, not done here.

**Enforcement actions — CHARACTERIZED (#392, 2026-08-05).** The `informal_enf_count: 1` /
`formal_enf_count: 1` that #392 flagged as uncharacterized are now
`data/extracted/defiance/wwtp-enforcement.yaml`, from ECHO's CWA services (DFR + case report, read
2026-08-05 against the ICIS-NPDES extract of 2026-07-31) plus the state document itself.

- **Formal — federal.** EPA Region 5 administrative order for compliance, CWA §309(a), case
  **05-2024-0328** "Defiance WWTP_AOC", issued **2024-07-26**, **closed 2026-05-06**, outcome *Final
  Order No Penalty*: $0 federal, $0 state, $0 collected, **$21,801 compliance-action cost**. Issued
  over four DMR-level violations (a 2020-05-31 total-residual-chlorine effluent violation and a
  2023-03-07 cluster — unrepresentative sample, numeric effluent violation, failure to submit DMRs).
  EPA scores the remedy at **35,602 lb/yr ammonia**, 1,826 lb/yr CBOD₅ and 1,035 lb/yr phosphorus.
  Its single milestone was **missed**: final compliance due 2025-12-31, recorded "unachieved and not
  reported", achieved **2026-03-04**, 63 days late.
- **Informal — state.** Ohio EPA NWDO **Notice of Violation / Resolution of Violation, 2026-04-21**
  (ECHO `OH-I00108252`; `data/documents/oepa/defiance/2PD00013.nov-rov-2026-04-21.pdf`) over the
  **Kingsbury force-main break**: SSOs to Preston Run, the Maumee and the Auglaize from 2026-03-31
  through 2026-04-10, repair blocked until April 9 because Preston Run's stage height kept the break
  flooded. **Resolved** 2026-04-15; ORC 6111.09 penalties expressly reserved. This confirms the
  epic's `[inference]`-linked April 2026 force-main LOV as `[verified]`.
- **Neither is counted by the biggest instrument on this plant.** ECHO's enforcement window opens
  2021-08-01, so the **State of Ohio Second Amended Consent Order, Case No. 10-CB-40433** (filed
  2020-02-28; IWIP + Long-Term Control Plan; CSOs to six events/typical year; **$40.7M by 2043**)
  appears in *neither* integer. Reading "1 informal + 1 formal" as this plant's enforcement history
  misses a 23-year consent decree.
- **What this does to the thesis: nothing, and that is the finding.** Neither action is a
  receiving-water failure. The formal one is about a failing secondary process and unfiled DMRs —
  the fact sheet names the cause outright, a mid-2022 filamentous bulking event, and ammonia is 49
  of the plant's 92 five-year violations. The informal one is about a cracked pipe in a flooded
  creek bed. **"Well-diluted" and "compliant" are independent properties of a plant**; the honest
  claim is that dilution headroom never was the variable these actions turn on, not that it was
  undermined. Standing record is worse than "tight but not violating" reads, though: **12 quarters
  in noncompliance, 4 in significant noncompliance**, current ECHO status *Violation Identified*,
  $0 in penalties.

**Data-center activity:** nothing on the BOSC record today (no permits / deeds / entity-graph parties
/ land assembly) — a finding, but **provisional** pending the GIS + `--research` discovery the
connector can't yet run (proposal #4). Adjacent energy-corridor lead noted: ANR Pipeline Defiance
Compressor Station (NPDES OH0079294).

**Serving utility — VERIFIED this pass (the "Bryan trap" checked & cleared).** Defiance is **not** a
municipal: the City of Defiance is absent from the EIA-861S short form, and the EIA-861 service-
territory file + utility sources confirm **The Toledo Edison Co (#18997, FirstEnergy / PJM ATSI)**
distributes to the city (the county's other IOU is AEP Ohio #14006; two rural co-ops also serve the
county). The profile's `eia861_utility_number=18997` and the PUCO/ATSI grid path are **correct** — so
the distilled "verify serving utility" proposal is **resolved here and not filed** as an open issue.

**Proposals filed as sub-issues of #238** (4 of the 5 distilled; the utility proposal is resolved above):

1. **Derive reach-specific Defiance 7Q10** (USGS 04192500 + 04191500) — replace the Waterville proxy; the reach dilution is likely tighter than 6.2:1. — **RESOLVED (#391, 2026-07-03):** both gages derived (04192500 = 139.24 cfs, 04191500 = 18.62 cfs; LP3, 44 yr); the mainstem reach 7Q10 (04192500, below the Auglaize confluence) is **higher** than the Waterville proxy, so the reach dilution is **7.5:1 — looser, not tighter**. See the "Reach-specific 7Q10" note above.
2. **Pull the OH0024899 NPDES fact sheet** — characterize the 1 informal + 1 formal enforcement action, anchor the permit-cited 7Q10, populate `plant_receiving`. — **RESOLVED (#392, 2026-08-05):** fact sheet 2PD00013\*VD and the issued permit are committed under `data/documents/oepa/defiance/`; the outfall is Maumee RM 62.05, the permit-cited annual 7Q10 is **94.1 cfs** and the average design flow **6.0 MGD**, giving **10.14:1** at the outfall; `plant_receiving` is populated; both enforcement actions are characterized in `data/extracted/defiance/wwtp-enforcement.yaml`. See the "Permit-cited 7Q10" and "Enforcement actions" notes above — including the **ECHO 12 MGD vs permit 6.0 MGD** contradiction the pull turned up, which is documented and left for a curation overlay rather than hand-applied.
3. **Audit RSEI currency** (all 19 facilities cap at `last_year: 2014`) + define a non-zero `toxic_corridor_bbox`. — **RESOLVED (#393, 2026-06-21):**
   - *Currency was the RSEI v234 vintage ceiling, NOT a Defiance truncation.* Every one of the network's 7 committed site inventories (Lima/Findlay/Ottawa/Van Wert/Fort Wayne/Toledo/Bryan) capped at `last_year: 2014` — that was the data ceiling of EPA RSEI **v234** (`Settings.rsei_version`), not a partial pull. The post-2014 refresh was a *global* `rsei_version` bump (all sites + the network), filed as **#436** — **not** a per-site re-pull.
   - *Operating status (live EPA TRI / Envirofacts, 2026-06-21 — a post-2014 source):* **GM Defiance Casting is active** — now "GENERAL MOTORS LLC GLOBAL PROPULSION SYSTEMS," `fac_closed_ind=0`, TRI forms through **2024**; the three **Johns Manville** plants are all `fac_closed_ind=0` (Plants 2 & 8 reporting through 2014, Plant 3 last 2003). So the RSEI picture (frozen ≤2014) **understated** current Maumee-corridor risk where this heavy industry remains active — exactly the failure mode the issue flagged.
   - **VINTAGE RESOLVED (#436):** the inventory is now **EPA RSEI v2.3.12** (TRI reporting years 1988–2022), pulled with the whole network off one archive. The live-TRI reading above is now *in the committed data*: **GENERAL MOTORS LLC GLOBAL PROPULSION SYSTEMS -DEFIANCE** reports **1988–2022** and is the county's **#1** Score (1,959,619); **Johns Manville Plants 2 and 8** also run to **2022** (1,151,249 / 945,828), Plant 3 ends 1988–2003 as recorded. The county holds 19 facilities (12 now carry a modeled Score, up from 11). The understatement is closed — the corridor's active heavy industry is scored on its real record, not a 2014 freeze.
   - *`toxic_corridor_bbox` defined:* `(41.26, 41.31, -84.40, -84.28)` — the Defiance industrial cluster on the Maumee/Auglaize from the Auglaize/Tiffin confluence downstream (captures GM Defiance Casting + all three Johns Manville plants + GT Technologies; excludes the far-west Hicksville cluster). The box is the screen-time scoping instrument (`toxics._in_corridor`), tagged `assumption` for any facility without an independently-cited receiving water. Re-confirmed unchanged at the v2.3.12 re-pull (#436): the box is vintage-independent and the in-box set held at **14 facilities / 4 water-releasers** across the bump — GM's row is the same facility under its current name.
4. **Register the Defiance County GIS connector + run `--research`** to populate the data-center dimension — `--research` **done** (Phase-5, 2026-06-19); the GIS half is the **bhamaps / expired-cert** case (#394, shared host with Van Wert #421 — blocked until renewal).

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.
- [ ] basin-screen coverage is sane for this site's receiving waters.
- [ ] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md).
- [x] Self-research first pass reviewed (Phase 5, 2026-06-19; serving-utility verified, 4 proposals filed as sub-issues of #238; triage data/research/onboard-defiance-maumee-mainstem-2026-06-19/).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'defiance' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
