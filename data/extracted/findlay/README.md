# Findlay (findlay) — extractions

Per-site onboarding tree for the Findlay watershed point (basin: maumee), scaffolded by `watermark onboard findlay` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard findlay` over the Findlay `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Flood-mitigation instrument chain (`flood/` + `flood-mitigation.md`)

Hand-curated primary-source evidence (issue #1465), **not** connector output — `watermark onboard`
does not produce or regenerate it, so re-onboarding must not clobber it. `flood/` holds the two
structured `permits-epa` record rows (the FEMA Flood Mitigation Assistance $24M obligation and the
USACE Blanchard-watershed feasibility Review Plan) that lift Findlay's `record` domain to `live`
(tier `backdrop → case`), plus the Eagle Creek basin + benching footprint descriptor handed to the
places sub-issue (#1462). `flood-mitigation.md` is the narrative record; open threads are in
`data/site/findlay/leads.yaml`; the set is catalogued as `findlay-flood`. Several primary pages 403'd
and are search-rendered — see the per-file `warnings` and the `flood-mitigation.md` sourcing note.

## Discharge record — NPDES `2PD00008` + the TMDL chain (`tmdl/` + `discharge-record.md`)

Hand-curated primary-source evidence (issue 1460), **not** connector output. The plant's own
instruments answer the two questions the site's water axis had left open: where the City of Findlay
WPCC discharges (Blanchard River at **River Mile 56.42**, outfall `2PD00008001`) and against what
low flow (Table 12's annual **7Q10 of 0.21 cfs**, an acute dilution ratio of **1.0** — no dilution
at design flow). That closes issue 352 and populates `_FINDLAY.plant_receiving`; it also supplies
the cited side of the derived-vs-cited low-flow conflict that issue 1458 owns, without resolving it.

`tmdl/maumee-tp-wla-2PD00008.epa.yaml` holds the phosphorus allocation chain across three
instruments — the TMDL's 3.2 MT spring wasteload, general permit `OHP000001`'s restatement of it as
a 3,200 kg individual limit, and the group-bubble compliance rule that keeps a plant discharging
4.8-5.5 MT every reported year from being in violation. The NPDES reads themselves live in
[`data/extracted/oepa/findlay/`](../oepa/findlay/) (the permit collection mirrors its source), and
the ECHO receiving-water null for `OH0025135` is corrected through the committed curation overlay,
not by hand-editing connector output.

## Dislocation record — the WARN pair + Brownfield Round 11 (`warn/`, `brownfield/`)

Hand-curated primary-source evidence (issue 1460). Two ODJFS WARN notices — Goodyear's permanent
closing of the Tall Timbers Mold facility (85 jobs, 2026-01-30) and Michigan Sugar's courtesy filing
for its Greenwood Street warehouse (4 jobs, 2025-12-11, naming a **severed rail spur** as a reason)
— publish under the `labor` record group added for this ingest (contract 1.47.0). `brownfield/`
holds the three Hancock County Round 11 awards totalling $999,998, two of them petroleum UST
assessments. Narrative: `dislocation-and-brownfields.md`.

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`watermark onboard findlay`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
