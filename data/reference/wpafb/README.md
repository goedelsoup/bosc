# Wright-Patterson AFB (wpafb) — reference data

Per-site onboarding tree for the Wright-Patterson AFB watershed point (basin: great-miami), scaffolded by `watermark onboard wpafb` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard wpafb` over the Wright-Patterson AFB `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## The federal-enclave datasets (#1664)

Wright-Patterson AFB is a **federal enclave**, and the two files below exist because the
county-scoped instruments the rest of the platform runs on cannot see one. Both are written by
`watermark --site wpafb enclave`.

- **`federal-land.geojson`** — the installation boundary from the **DoD MIRTA** site register
  (Military Installations, Ranges, and Training Areas; published via Esri US Federal Data). This
  is the land path a county parcel layer will *never* provide: the base is off the tax rolls, so
  `SiteProfile.gis_parcel` is honestly `None` and always will be. **Planning-grade, not a legal
  survey.** The polygon measures **5,230 acres** across 4 mapped parts, against the **~8,200
  acres** the 1991 CERCLA agreement states for Areas A/C and B — a **36% shortfall**, carried as a
  coverage caveat on the enclave profile rather than reconciled. Treat it as a partial footprint;
  the record, not the register, is the instrument for the enclave's extent.
- **`enclave.yaml`** — the assembled enclave profile: land, water, wastewater, power, toxics. The
  documented figures (17 supply wells, 3 well fields, 5 air-stripping units, ≥58 waste-disposal
  sites, the NPL listing) are **projected from** `data/extracted/wpafb/cercla-ffa-1991.epa.yaml`,
  not restated here, so they cannot drift from the record. The registers supply the rest:
  **EPA SDWIS** for the base's two community water systems (OH2903412 Area A / OH2903312 Area B,
  both groundwater, 27,585 people served), **EPA ECHO** for its two NPDES permits (OH0010243 and
  OH0105422, both Effective, 1.152 MGD reported average flow), and **EPA RSEI/TRI** for its own
  release row.

### Why the enclave's toxics row is not in `data/reference/rsei/wpafb/inventory.yaml`

The base reports TRI as `45433SDDSFDEPAR` from **Greene County (39057)**. This site's RSEI and
economic unit is **Montgomery County (39113)** — chosen deliberately for the well-field / plume /
Dayton-metro context (see the profile's `econ_unit_note`). So the county inventory does not contain
the installation: it is **out of scope by construction, not missing**. The reconciliation is the
one-facility reduction at `data/reference/rsei/wpafb/enclave.yaml`; the county unit is unchanged.

Even that row is not the base's contaminant footprint. RSEI tracks TRI *reporting*, which began in
1987 — the landfills, burial sites and fire-training areas the FFA dates to "the 1920s to at least
1973", and the VOC plume they produced, are not releases under it. The Superfund record is the
instrument for that mass, and the two are complements.

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`). For this site it is also **structurally unavailable** for the enclave itself, which is why the MIRTA path above exists.
- The installation's **electrical load** and **raw-water withdrawal** are `[open]`. A base is unmistakably a large power and water user; no instrument in the corpus discloses either figure, and none is inferred from acreage or population served.

## Regenerate

`watermark onboard wpafb`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)

`watermark --site wpafb enclave` for the two federal-enclave datasets above (add `--skip-rsei` to
refresh the registers without streaming the ~447 MB RSEI archive).
