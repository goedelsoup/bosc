# Onboarding — Bryan (bryan)

Living record for the Bryan watershed point (basin: maumee), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile (**municipal** — see grid note)
- [~] **Data-center activity** — self-research first pass run (#247); **no documented facility**, scoped honestly (no Williams County parcel/recorder layer in the corpus yet — the tripwire isn't installed, #410). See self-research summary below.
- [x] **Per-jurisdiction GIS** — parcels **wired** (#410) via the OGRIP Ohio statewide layer scoped to `County='Williams'` (the owner-redacted substitute, like Findlay — Williams Co OH has no county REST and its bhamaps host is cert-blocked, #421/#394). Flood = shared national NFHL (wired). Zoning stays `[open]`. **Correction:** the `ParcelsWeb`/`Zoning_OD` ArcGIS the 2026-06-19 pass flagged as "Williams County" is **North Dakota** (cross-state misidentification) — NOT wired; see GIS discovery below.

## Grid — the network's first MUNICIPAL utility (notable)

Bryan is served by **Bryan Municipal Utilities** (City of Bryan, EIA **#2439**), not an IOU — the
network's first municipal electric point. It files the **EIA-861 *short form* (861S)**, so it is
absent from the full Sales-to-Ultimate-Customers sheet the grid connector reads; this onboarding
added a **short-form fallback** + an **ownership-aware retail regulator** to `watermark.grid.eia861` /
`watermark.grid.utility`. The generated `grid-profile.yaml` correctly shows: ownership Municipal,
~160 GWh / 5,814 customers (861S 2024), avg price ~10.75¢/kWh; holding company = **American
Municipal Power (AMP)** member (no IOU parent); BA/RTO = PJM (AMP-scheduled); retail regulator =
**municipal home rule** (NOT PUCO rate-regulated). The PJM transmission **zone** is now pinned to
**AEP** (the City-of-Bryan `CTYBRYAN` load settles in the AEP zone per PJM Data Miner 2); LMP is
connector-sourced $45.81/MWh (#411, resolved 2026-06-21).

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/bryan/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/bryan/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/bryan/nasa-power-climatology.yaml |
| basin-screen | ok | 7/129 dischargers screened (1 violations, 2 tight) |
| econ-baseline | ok | reference/economics/bryan/baseline.yaml |
| rsei | ok | reference/rsei/bryan/inventory.yaml |
| consumer-energy | ok | reference/eia/bryan/consumer-energy.yaml |
| grid-profile | ok | reference/eia/bryan/grid-profile.yaml |

## GIS discovery (2026-06-19; revised 2026-06-21 — schema-driven GIS, #237 / #410)

> **Correction (2026-06-21).** The 2026-06-19 discovery below flagged a "full, valid-cert Williams
> County ArcGIS" at `services1.arcgis.com/D85sDZoJyameepNh` (`ParcelsWeb`/`Zoning_OD`) as the
> wire-ready lead. On wiring it (#410) the live data proved it is **Williams County, NORTH DAKOTA**,
> not Williams County, OHIO: its parcels are in Williston/Tioga/Grenora/Zahl/Epping (the Bakken),
> with owners like `HESS TIOGA GAS PLANT LLC` ($486M, Rockwall TX). This is a **same-named-county
> cross-state misidentification** — the discovery pass grabbed *a* "Williams County" GIS without
> verifying the state. It is **not wired**, and must never be (it would attach North Dakota oil-patch
> parcels to the Ohio Bryan site). The `KG1citvUsI75VegT` engineer org is the same ND county.
>
> **What was actually wired (#410):** Williams County, OHIO publishes **no** county parcel REST of
> its own (the Bruce Harris `bhamaps` PAT MapServer that would host one carries the same **expired
> TLS cert** as Van Wert/Defiance, #421/#394 — `*.bhamaps.com`, no weakening TLS). So, exactly like
> Findlay/Hancock, parcels come from the **OGRIP Ohio statewide parcels public view scoped to
> `County='Williams'`** (`OHIO_STATEWIDE_PARCEL_SCHEMA`, 26,260 Williams-OH parcels, 26,080 with
> situs; StateLUC `"<code>: <label>"`). It is the partial, **owner-redacted** substitute: id, situs,
> land-use, acreage, and the mailing label decode; owner/value/sale are honestly absent. Williams'
> stored `LocalParcelID` is the **dashed** `NN-NNN-NN-NNN.NNN` form (e.g. `062-350-02-013.001`), so
> the site overrides `id_normalize='verbatim'`. An offline fixture + decode test pin it.

| layer | endpoint | finding | status |
|---|---|---|---|
| floodzone | FEMA NFHL (national, layer 28) | wired in the profile (`gis_flood`) | wired |
| parcels | OGRIP statewide, scoped `County='Williams'` (`services2.arcgis.com/MlJ0G8iWUyC7jAmu/.../OhioStatewidePacels_full_view/FeatureServer/0`) | owner-redacted partial: `LocalParcelID` (dashed), `SitusAddressAll`, `StateLUC`, `LandArea`, `MailAddressAll` | **wired** (`gis_parcel`, #410) |
| ~~parcels (ND org)~~ | ~~`D85sDZoJyameepNh/ParcelsWeb/FeatureServer/0`~~ | **Williams County, NORTH DAKOTA — NOT this county.** Do not wire. | ❌ wrong state |
| ~~zoning (ND org)~~ | ~~`D85sDZoJyameepNh/Zoning_OD/FeatureServer/0`~~ | **North Dakota — NOT this county.** Do not wire. | ❌ wrong state |
| zoning (OH) | — | no real City of Bryan / Williams Co OH zoning REST found | `[open]` |

Follow-up: locate a *native* Williams County, OHIO parcel REST (re-probe the bhamaps host once its
cert renews, #421/#394 — it would give non-redacted owner+value); locate a real Bryan/Williams OH
zoning layer; commit reviewed reference *data* (a `watermark parcels --site bryan` pull).

## Self-research (Phase 5; #247) — 2026-06-21

First automated-research pass (`watermark research run`, 24 turns, $1.27, read-only over the corpus) →
`data/research/onboard-bryan-bryan-data-center-activity-receivi-2026-06-21/` (`findings.md` + `manifest.yaml`).

**Headline — the network's first municipal utility is the reason to onboard; the receiving-water
screen is unrun.** Bryan's distinction is the **grid**: Bryan Municipal Utilities (City of Bryan,
EIA #2439, an AMP member scheduled into PJM) is the network's first municipal / short-form /
home-rule electric point, exercising the EIA-861S fallback + ownership-aware regulator paths no IOU
site does (cf. PR #388). But the assimilative screen **cannot yet be computed**: Bryan WWTP
(OH0020532, 3.1 MGD ≈ 4.8 cfs — *larger* than Lima's Shawnee II) discharges to **Prairie Creek**
(Tiffin subbasin), which has **no 7Q10** in the corpus, so `watermark basin-network` records `no_7q10`,
dilution `null`. The pre-applied `effluent_dominated_tributary` label is an **`[inference]`**, not a
finding (proposals #408/#409).

**Data-center activity — no documented facility, scoped honestly.** No disclosed facility
(`facility=None`); information-sector LQ 0.19 corroborates the absence. **But scope it honestly:**
unlike Lima (recorder deeds + NPDES applications + site plans), Bryan has **no Williams County
parcel/recorder/permit layer in the corpus** — so "no activity" is *evidence not yet gathered*, not
land assembly ruled out. The parcel tripwire is now **partially installed** (#410): parcels are
wired via the OGRIP `County='Williams'` substitute — enough to query Bryan city-limits parcels by
situs/land-use/value-class, but **owner-redacted**, so an owner-name land-assembly scan still needs
a native Williams-OH parcel REST (bhamaps, cert-blocked #421/#394) or a recorder-deed feed. The
"best-equipped Williams County ArcGIS" the 2026-06-19 pass cited was **North Dakota** (see the GIS
correction above) — it does not exist for Williams Co OH.

**Serving utility — VERIFIED: Bryan IS the municipal (the site the "Bryan trap" is named for).** The
grid connector's EIA-861S short-form fallback correctly identifies City of Bryan #2439 as
**Municipal / home-rule** (NOT PUCO rate-regulated), AMP/PJM — the inverse of the IOU sites'
verification. **LMP resolved (#411, 2026-06-21):** the $35 placeholder is replaced with the
connector-sourced **AEP-zone** day-ahead annual mean (**$45.81/MWh**, PJM Data Miner 2). Despite the
AMP wholesale arrangement, the **City-of-Bryan load settles in the PJM AEP zone** — the live Data
Miner 2 pnode table lists `CTYBRYAN` (LOAD pnodes 32411011/32411013) in zone AEP — so Bryan's zonal
LMP is the AEP zone (pinned `lmp_pnode_id`, same fixture as the AEP OH sites), `source=connector`.

**Economy / toxics:** manufacturing LQ **4.54** (heavily industrial, declining population) against
info LQ 0.19 — the load-not-jobs shape again. **RSEI/toxics resolved (#412, 2026-06-21):**

- *Vintage:* the 2014 ceiling was the EPA RSEI **v234** data ceiling (`Settings.rsei_version`), uniform across all 7 network site inventories — not a Bryan truncation. The post-2014 refresh was a *global* `rsei_version` bump (filed as **#412**'s follow-on **#436**). **RESOLVED (#436):** the inventory is now **EPA RSEI v2.3.12** (TRI reporting years 1988–2022), pulled with the whole network off one archive — Williams County goes from 35 to **40** facilities (29 → **34** scored) and the county record now runs to **2022**. Critically, the vintage bump **does not** move NEW ERA OHIO: it still reads **1988–2010** and is still the county's **#1** cumulative Score (41,296,439). That is the closure of the reading below — the 2010 stop was never a v234 artifact, it is the facility's real record, and its dominant score is confirmed *legacy*.
- *Operating status (live EPA TRI / Envirofacts, 2026-06-21):* the top RSEI emitter **NEW ERA OHIO LLC is CLOSED** (`fac_closed_ind=1`, no TRI form after **2010** — matching its RSEI `last_year: 2010`), so its dominant cobalt/chromium/nickel score is **legacy**, *overstating* current Prairie Creek risk. **Titan Tire of Bryan is active** (`fac_closed_ind=0`, TRI forms through **2024**). So the county-wide legacy layer both over- and under-states the current corridor depending on the facility — the case for corridor-scoping.
- *`toxic_corridor_bbox` defined:* `(41.46, 41.49, -84.57, -84.52)` — the City-of-Bryan reach of Prairie Creek (captures NEW ERA OHIO, Titan Tire, Hayes-Albion, Ohio Art, A-Stamp, Bryan Metals; excludes the Montpelier/Edgerton/Stryker facilities on other drainages). This box **is** the Prairie-Creek-scoped subset: `toxics._in_corridor` scopes the inventory to it at screen time (**15 of 40** facilities, 3 water-releasers — re-confirmed unchanged at the v2.3.12 re-pull, #436: the box is vintage-independent and the in-box emitter set held at 15/3 across the bump), tagging in-box facilities `assumption` for Prairie Creek discharge.

**Proposals — 5 filed as sub-issues of #380:** #408 (Prairie Creek 7Q10 + the WWTP screen), #409
(ingest the OH0020532 NPDES fact sheet), #410 (the Williams County parcel/recorder tripwire),
~~#411 (pin the AMP/PJM zone + replace the placeholder LMP)~~ **— resolved 2026-06-21: CTYBRYAN
settles in the PJM AEP zone, LMP now connector-sourced $45.81/MWh**, #412 (corridor-scope the
RSEI/toxics to Prairie Creek). The GIS parcel lift is now done via the OGRIP `County='Williams'` substitute (#410,
owner-redacted); a native owner-bearing Williams-OH REST + a zoning layer remain follow-ups (see the
GIS correction above — the originally-cited `ParcelsWeb`/`Zoning_OD` org is North Dakota).

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.
- [ ] basin-screen coverage is sane for this site's receiving waters.
- [x] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md). Parcels wired via the OGRIP `County='Williams'` substitute (#410); zoning `[open]` (no real OH REST; the discovered one was North Dakota).
- [x] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/) — see self-research summary above; 5 proposals filed as sub-issues of #380 (#408–412).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'bryan' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
