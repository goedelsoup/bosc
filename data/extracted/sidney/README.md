# Sidney (sidney) — extractions

Per-site onboarding tree for the Sidney watershed point (basin: great-miami), scaffolded by `watermark onboard sidney` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard sidney` over the Sidney `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Platform gaps found while ingesting the City instruments (#1380, 2026-08-01)

Two defects that are the platform's, not this site's. Both are recorded here rather than worked
around, because a workaround would misfile evidence.

- **Update (#2003):** the five authorizing RESOLUTIONS are now published in their own right, as
  instrument-level `resolution:` extractions under `council/` — they classify as
  `local-legislation`, which is what the impact study's `governance` chapter reads, and that
  chapter moved `partial` -> `data`. This does not close the gap below: the register itself is
  still `corpus.unrecognized`, so the executed AGREEMENTS (their terms, the PILOT schedule, the
  reserved sewer capacity) remain unreachable. The acts and the agreements are different
  instruments and only the acts have been split out.
- **`assembly` still cannot be lit, and should not be.** The register's `land_acquisition:` block
  recites three O.R. 2329 deeds from an agreement's *Exhibit A*, and records that the grantors,
  instrument numbers and per-deed consideration are UNREAD. Publishing it as a conveyance register
  would assert a chain the corpus does not hold. That chapter stays `partial` until the deeds are
  pulled from the Shelby County Recorder (#1998).

- **`incentive-instruments.yaml` is not published as a record.** `watermark.site.records`
  classifies an extraction by its payload block, and no group claims an executed municipal
  incentive/service agreement — so the single most important document set at this site loads as
  `corpus.unrecognized` and never reaches the `records` feed or the site's record pages. This is
  the same class of gap #1724 fixed for Urbana's litigation and land-assembly artifacts, and it
  affects Urbana's own `incentive-instruments.yaml` identically. The fix is a new group in
  `_WHOLE_DOC_BLOCK_TO_GROUP`, not a re-shaping of the data: filing a CRA agreement under the
  existing `award`/`finance` group would present a tax exemption as a grant award. Sidney's
  `record` domain is `live` on other evidence, so this suppresses reach, not readiness.
- **`oepa/sidney/1PD00009.npdes.yaml` fails corpus validation and is silently dropped.** The
  #1383 structured read of the Sidney WWTP permit and fact sheet is a richer, hand-authored shape
  (`meta:`, `stream_design_flows:`, `wasteload_allocation:`, `reconciliation:`) that carries no
  extraction envelope, so `_classify` routes it to `npdes` on its `permit:` key and
  `NpdesExtraction` then rejects it for missing `doc_id`, `kind` and `dpi`. Consequence: the
  receiving POTW and the Great Miami River are **absent from this site's entity graph and
  timeline**, while `records.py` (which reads raw dicts) publishes it fine — so it looks present
  and is not. Left alone deliberately: it is another issue's artifact and reshaping it changes
  the WWTP's identity across feeds.

## Regenerate

`watermark onboard sidney`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
