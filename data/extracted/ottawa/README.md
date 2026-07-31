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
