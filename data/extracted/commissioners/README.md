# Allen County Commissioners — the legislative record

The Board of County Commissioners' own meeting record (2023–2026), mined from the
[minutes corpus](minutes/README.md) (933 raw PDFs + the OCR'd parquet index) into the
**legislative spine** of Project BOSC, its **closed-deliberation mechanics**, and the
**wastewater economics** the County deferred on in the public-records production.

## Artifacts

| File | What |
|---|---|
| [`bosc-resolution-ledger.yaml`](bosc-resolution-ledger.yaml) | The project's legislative spine, keyed by resolution # → date → verbatim title → mover: NDA **#417-25**, CRA **#548-25**, RDA **#588-25**, the Sanitary Sewer Developer Agreement **#575-25** (amended **#975-25**), pump-station/forcemain engineering **#469-25 → #713-25 → CMAR #137-26/#138-26**, the BOSC Fund **#612-25** — plus the codename-phase narrative and the wastewater-works resolutions. |
| [`closed-deliberation-and-corridor.yaml`](closed-deliberation-and-corridor.yaml) | The executive-session (closed-deliberation) census, by ORC 121.22(G)(n) exemption. The economic-development **(G)(8)** sessions first appear **2025-05-27** (the BOSC CRA, expressly citing the NDA) and never before in the covered record. Plus the land/right-of-way corridor (Hamlet of Hume sewer, ODOT roundabout ROW, force-main easements). |
| [`sanitary-economics.yaml`](sanitary-economics.yaml) | The wastewater thread in dollars and flow: the BOSC sanitary load (**0.13 MGD @ 83 °F** interim), the **~$32M** developer pump station + **~$3.125M** capital permit fee, and the Cridersville/Shawnee Oaks revenue-capture reroute ($1M 0% loan; ends a $102k/yr outflow). |
| [`bosc-water-balance.analysis.md`](bosc-water-balance.analysis.md) | The Tier-0 water-balance run + 7Q10 assimilative screen with those sanitary figures folded in — all three receiving streams already fail the low-flow dilution screen before any BOSC load. |
| [`bosc-2023-backfill.yaml`](bosc-2023-backfill.yaml) | The pre-BOSC baseline year: the 2023 record is **silent on the data center**; what's present is the precursor machinery (Shawnee II Phase 2, the annual AEDG EZ/CRA contract, routine abatements, EMH&T, the Hamlet of Hume sewer origin). |
| [`minutes/`](minutes/README.md) | The underlying minutes/agenda corpus + the OCR parquet index bundle. |

## Provenance

Resolution numbers, titles, dates, and movers are high-confidence (verbatim from the
formal resolution lists); discussion-item figures are OCR-approximate — verify against
the source PDF before quoting. Coverage is 2024–2026 in the committed parquet; 2023 was
mined via ad-hoc OCR (see the backfill). These artifacts carry `kind`s the corpus loader
does not recognize, so they are read directly by the timeline assembler.
