# Onboarding — Findlay (findlay)

Living record for the Findlay watershed point (basin: maumee), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile
- [~] **Data-center activity** — self-research first pass run (#247); **affirmatively nothing documented** (no Findlay/Hancock permit, deed, record, or entity in the corpus; `facility=None` is deliberate). See self-research summary below.
- [x] **Per-jurisdiction GIS** — schema-driven (#237). Zoning-district catalog committed (`reference/findlay-gis/`); **parcels wired** via the OGRIP Ohio statewide layer scoped to Hancock (partial / owner-redacted — PR #406); floodzone = shared national FEMA NFHL (spatial — pending a site footprint)

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/findlay/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/findlay/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/findlay/nasa-power-climatology.yaml |
| basin-screen | ok | 7/129 dischargers screened (1 violations, 2 tight) |
| econ-baseline | ok | reference/economics/findlay/baseline.yaml |
| rsei | ok | reference/rsei/findlay/inventory.yaml |
| consumer-energy | ok | reference/eia/findlay/consumer-energy.yaml |
| grid-profile | ok | reference/eia/findlay/grid-profile.yaml |

## GIS pulls (manual; not part of `watermark onboard`)

| layer | status | output |
|---|---|---|
| zoning catalog | ok (2026-06-19) | reference/findlay-gis/zoning-districts.yaml — 15 districts (dissolved layer, 1 polygon each) |
| parcels | wired (PR #406) | Hancock County publishes no county REST (Beacon/Schneider only) → OGRIP Ohio statewide layer scoped to `County='Hancock'` (partial / owner-redacted: id+situs+land-use+acreage, no owner/value/sale). `reference/findlay-gis/` |
| floodzone | n/a | shared national FEMA NFHL — spatial query; needs an identified site footprint |

## Self-research (Phase 5; #247) — recorded 2026-06-21 (#353)

Automated-research pass (`watermark onboard --research`, committed 2026-06-19) →
`data/research/onboard-findlay-findlay-data-center-activity-rec-2026-06-19/` (`findings.md` +
`manifest.yaml`). Recorded here per #353.

**Data-center activity — affirmatively nothing documented.** No Findlay/Hancock data-center permit,
deed, record, or entity exists in the corpus; `facility=None` is deliberate. A finding ("no disclosed
Findlay facility yet"), not a gap.

**Receiving-water screen — the shared Blanchard gap.** No Blanchard River 7Q10 exists in the corpus
(only the 2009 TMDL row + the Atlas-14 corridor label), so the Findlay WPCC (OH0025135, 15 MGD) is
unscreened and the onboard `basin-screen` "7/129" almost certainly excludes it. This is the *same* gap
as Ottawa, the same-river sibling ~40 mi downstream — one Blanchard 7Q10 derivation unblocks both
(tracked by #414, with the 7/129 reconciliation by #416).

**GIS — parcels now wired.** The zoning catalog is committed and the Hancock parcel `[open]` was
resolved by the OGRIP statewide-parcel wiring (#406, partial/owner-redacted). Floodzone = shared
national NFHL.

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.
- [ ] basin-screen coverage is sane for this site's receiving waters.
- [x] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md). Schema-driven (#237); Findlay zoning field-map registered + catalog committed; parcels wired via the OGRIP statewide layer (PR #406).
- [x] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/) — see self-research summary above; the shared Blanchard 7Q10 gap + reconciliation are tracked by #414/#416, parcels closed by #406.
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'findlay' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
