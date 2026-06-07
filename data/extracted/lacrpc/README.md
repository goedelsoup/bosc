# LACRPC planning / land-use / zoning extractions

Reviewed reads of the **Lima-Allen County Regional Planning Commission** corpus
(36 documents under [`data/documents/lacrpc/`](../../documents/lacrpc/README.md);
full provenance in [`MANIFEST.yaml`](../../documents/lacrpc/MANIFEST.yaml)).

The collection is the land-use context for the BOSC corridor. Most of it is
general planning reference for jurisdictions other than the data-center site;
only **American Township** (the site's own jurisdiction) is deep-extracted.

## Files

| File | What |
|---|---|
| `american-township-zoning.zoning.yaml` | The site's zoning. American Township's current Zoning Resolution (amended/adopted through **2026-02-09**) **defines** "Data Center" and "Hyperscale Data Center" and makes "hyper-data centers" a **conditional use in M-2 General Manufacturing** (§11.2.4 — BZA conditional-use certificate after a public hearing). M-1 caps data centers at 10,000 SF and bars hyperscale (§10.2.2). M-2 structures are height-capped at **50 ft**; State/County-road setback 90 ft. The amendment cycle brackets the deal timeline [inference]. |
| `collection-index.yaml` | Relevance-tiered catalog of all **36** LACRPC documents: Tier-1 American Township (site), Tier-2 county-wide regs + Shawnee/Bath (receiving-WWTP) townships, Tier-3 = 25 other-jurisdiction plans/zoning + personnel rosters (indexed only, not content-read). |

## Notes

- The American Township zoning PDF is a native text layer (read with `pypdf`);
  figures/quotes are transcribed verbatim. It has **no amendment-log page**, so
  *which* amendment added the data-center language is not content-verifiable.
- The American Township Comprehensive Plan (2009) future-land-use is **map-image
  only** — the site-specific designation is not text-extractable (open question:
  plan-consistency of the M-2 use).
- Tier-3 documents are catalogued for corpus completeness; no per-document read
  was performed and none is claimed.
- **Records hook:** a hyperscale data center in M-2 is a *conditional* use, so a
  BZA conditional-use proceeding (application, hearing notice, decision) — and any
  rezoning to M-2 — should exist as public record for the site.
