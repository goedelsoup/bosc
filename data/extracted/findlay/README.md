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

## Governance watch — the data-center siting regime (`governance/` + `governance-watch.md`)

Hand-curated primary-source evidence (issue 1463), **not** connector output. Three governments
in this county have something to say about where a data center may be built, and none of them
has an adopted rule that reaches the 150 MW already contracted inside their borders: the county's
SB 52 restricted area bars large wind and solar and is silent on load; the City of Findlay's
Ordinance 2026-42 moratorium stops at the corporation line; and Allen Township — where the
Megawatt Hub actually sits — had no zoning at all until **2026-05-11** and its adopted resolution
does not contain the phrase "data center" once in 77 pages. On **2026-07-28** its zoning
commission moved a Section 1521 that would conditionally permit data centers in I-1 and I-2
capped at **10 MW Total Facility Load**, heard **2026-08-19**.

`governance/governance-timeline.yaml` is the four-jurisdiction chronology, every entry carrying
its own tag and a corpus path or an explicit `[not in corpus]`.
`governance/litigation-one-energy-v-allen-twp.yaml` is the structured read of **2026-Ohio-405**
and the one `RecordItem` in this set (a `case:` block → the `litigation` group); its instrument
lives at [`data/documents/legal/one-energy-v-allen-twp/`](../../documents/legal/one-energy-v-allen-twp/),
filed by case rather than by site on the `legal/thor-v-urbana` precedent. Everything else here is
**corpus, not records** — there is no zoning `RecordGroup` and inventing one to publish a
proposal that is not yet law would cost a contract bump and a 26-bundle regeneration (the same
call issue 1464 made for the grid artifacts).

**Evidentiary asymmetry, stated once:** the township, court and election material is nearly all
`[verified]` from a `.gov` site, a slip opinion and a certified canvass. The city material is
almost entirely `[reference]` — `findlayohio.gov` and American Legal both return HTTP 403 to
automated fetches and there is no Legistar tenant, so **Ordinance 2026-42 is held only as
newspapers describe it**. That is an *access failure, not a denial*; the response is a drafted,
**unsent** R.C. 149.43 request at `governance/records-requests/`. Narrative:
[`governance-watch.md`](governance-watch.md); open threads in
[`data/site/findlay/leads.yaml`](../../site/findlay/leads.yaml); catalogued as `findlay-governance`.

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`watermark onboard findlay`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
