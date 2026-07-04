# Onboarding — Findlay (findlay)

Living record for the Findlay watershed point (basin: maumee), scaffolded by `watermark onboard findlay`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile
- [~] **Data-center activity** — self-research first pass run (#247); **affirmatively nothing documented** (no Findlay/Hancock permit, deed, record, or entity in the corpus; `facility=None` is deliberate). See self-research summary below.
- [x] **Per-jurisdiction GIS** — schema-driven (#237). Zoning-district catalog committed (`reference/findlay-gis/`); **parcels wired** via the OGRIP Ohio statewide layer scoped to Hancock (partial / owner-redacted — PR #406); floodzone = shared national FEMA NFHL (spatial — pending a site footprint)

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok¹ | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/findlay/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/findlay/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/findlay/nasa-power-climatology.yaml |
| basin-screen | ok² | 7/129 dischargers screened (1 violation, 2 tight) — superseded; see reconciliation below |
| econ-baseline | ok | reference/economics/findlay/baseline.yaml |
| rsei | ok | reference/rsei/findlay/inventory.yaml |
| consumer-energy | ok | reference/eia/findlay/consumer-energy.yaml |
| grid-profile | ok | reference/eia/findlay/grid-profile.yaml |

¹ `ok` means the step ran without error — **not** that it produced a Blanchard value. On the recorded run it emitted only the four Maumee-side mainstems (no Blanchard). The Blanchard River 7Q10 (**8.67 cfs**, LP3 over USGS 04189000) was added to `low-flow-7q10.derived.yaml` later, under #417.
² Superseded by the #416 reconciliation below (now 8/129, 2 violation/2 tight/4 ok). Neither the Findlay WPCC nor any other Blanchard mainstem POTW is in the screened set — see why.

## GIS pulls (manual; not part of `watermark onboard`)

| layer | status | output |
|---|---|---|
| zoning catalog | ok (2026-06-19) | reference/findlay-gis/zoning-districts.yaml — 15 districts (dissolved layer, 1 polygon each) |
| parcels | wired (PR #406) | Hancock County publishes no county REST (Beacon/Schneider only) → OGRIP Ohio statewide layer scoped to `County='Hancock'` (partial / owner-redacted: id+situs+land-use+acreage, no owner/value/sale). `reference/findlay-gis/` |
| floodzone | n/a | shared national FEMA NFHL — spatial query; needs an identified site footprint |

## Self-research (Phase 5; #247) — recorded 2026-06-21 (#353)

Automated-research pass (`watermark onboard findlay --research`, committed 2026-06-19) →
`data/research/onboard-findlay-findlay-data-center-activity-rec-2026-06-19/` (`findings.md` +
`manifest.yaml`). Recorded here per #353.

**Data-center activity — affirmatively nothing documented.** No Findlay/Hancock data-center permit,
deed, record, or entity exists in the corpus; `facility=None` is deliberate. A finding ("no disclosed
Findlay facility yet"), not a gap.

**Receiving-water screen — the shared Blanchard gap (denominator resolved; the WPCC is still
unscreened for a different reason).** The Blanchard River 7Q10 that both this site and its same-river
sibling Ottawa needed now exists — **8.67 cfs**, LP3 over USGS 04189000, committed to
`low-flow-7q10.derived.yaml` under #417 (closing #414). But deriving the denominator did **not** put
the Findlay WPCC into the basin screen: see the #416 reconciliation below. In short, `basin-screen`
keys on the receiving-water *name* in `maumee-wwtp.potw.yaml`, and that field is `null` for the WPCC,
so it never reaches the 7Q10 lookup. The 15 MGD Findlay↔Ottawa comparison against the 8.67 cfs
denominator is instead carried by the bespoke `data/reference/network/findlay-ottawa-comparison.yaml`
(#417), which asserts the Blanchard receiving water explicitly.

## basin-screen reconciliation (#416) — recorded 2026-07-03

Re-ran `watermark basin-screen` (maumee basin) after the Blanchard 7Q10 landed. Authoritative current
result: **8 of 129 basin POTWs screened** (2 violation, 2 tight, 4 ok); unscreenable and *reported, not
guessed*: 76 `no_receiving_water` (ECHO/inventory has no receiving-water name), 43 `no_7q10` (named
receiver on an ungaged tributary/ditch), 2 `no_design_flow`.

**The 8 screened dischargers** (NPDES id → receiving water → 7Q10 source):

| NPDES | discharger | receiving water | 7Q10 | flag |
|---|---|---|---|---|
| OH0023841 | American-Bath WWTP | Pike Run | 0.03 cfs (document) | violation |
| OH0027910 | Van Wert WWTP | Town Creek | 0.16 cfs (document) | violation |
| IN0039314 | Decatur WWTP | St Marys River | 15.65 cfs (derived) | tight |
| OH0024899 | Defiance WWTP | Maumee River | 114.15 cfs (derived) | tight |
| OH0022446 | Rockford STP | Saint Marys River | 15.65 cfs (derived) | ok |
| OH0078760 | Beverly Hills Subdiv | Auglaize River | 1.91 cfs (derived) | ok |
| OH0021164 | Edgerton WWTP | St. Joseph River | 29.69 cfs (derived) | ok |
| IN0058441 | St Joe–Spencerville RSD | St Joseph River | 29.69 cfs (derived) | ok |

**Was OH0026921 (Ottawa WWTP) — and by extension OH0025135 (Findlay WPCC) — excluded for want of a
Blanchard 7Q10 denominator? REFUTED.** The denominator now exists and the screen confirms it *works*:
the one Blanchard-mainstem POTW whose inventory record names `BLANCHARD RIVER` as its primary receiver
(Miller City HS WWTP, OH0126535) matches the 8.67 cfs and is held out only for `no_design_flow`. Both
anchor POTWs are instead excluded as **`no_receiving_water`** — `maumee-wwtp.potw.yaml` carries
`receiving_water: null` for OH0025135 and OH0026921 — so `screen_facility` short-circuits *before* the
7Q10 lookup. The blocker was never the denominator; it is the missing receiving-water name in the
inventory. (Filling it would require the OH0025135 / OH0026921 NPDES fact sheets — the same source #352
tracks for `plant_receiving`.)

**Unscreened Blanchard-mainstem dischargers (HUC-8 04100008) — explicit coverage gap:**

- `no_receiving_water` (null receiver in the inventory): **OH0025135 Findlay WPCC (15.0 MGD)**,
  **OH0026921 Ottawa WWTP (3.0 MGD)**, OH0020851 Bluffton WWTP (1.9), OH0047791 Rawson WWTP (0.2), and
  the smaller Blanchard-HUC POTWs (Arlington, Pandora, Dunkirk, Gilboa, Country Acres, …).
- `no_7q10` (named receiver, but an unnamed *tributary* to the Blanchard, not the gaged mainstem):
  OH0025151 Forest WWTP ("UT TO BLANCHARD RIVER"), OH0132951 Hardin-Northern Schools.
- `no_design_flow` (mainstem-matched but no flow to screen): OH0126535 Miller City HS.

Net: even with the Blanchard 7Q10 in place, **zero** Blanchard-mainstem POTWs are assimilatively
screened by `basin-screen` — the two material ones (Findlay 15 MGD, Ottawa 3 MGD) are blocked on a
`null` receiving-water name, not on the low flow.

**GIS — parcels now wired.** The zoning catalog is committed and the Hancock parcel `[open]` was
resolved by the OGRIP statewide-parcel wiring (#406, partial/owner-redacted). Floodzone = shared
national NFHL.

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.
- [x] basin-screen coverage is sane for this site's receiving waters. Reconciled under #416 (see section above): the Findlay WPCC is correctly **unscreened** — excluded as `no_receiving_water` (null receiver in `maumee-wwtp.potw.yaml`), not silently mis-screened. Filling it is gated on the OH0025135 NPDES fact sheet (#352).
- [x] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md). Schema-driven (#237); Findlay zoning field-map registered + catalog committed; parcels wired via the OGRIP statewide layer (PR #406).
- [x] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/) — see self-research summary above; the shared Blanchard 7Q10 gap is resolved (8.67 cfs, #414 closed via #417) and the basin-screen reconciliation is complete (#416 section above); parcels closed by #406.
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'findlay' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
