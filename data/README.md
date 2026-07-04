# data/

The evidence base. Raw source documents on one end, reviewed structured data and
the published bundle on the other — every layer committed and traceable.

| Directory | Committed? | Contents |
|-----------|-----------|----------|
| `documents/` | **Yes** (Git LFS for binaries) | Raw source material: PRR PDF bundles, scans, permits, deeds, minutes. Immutable, chain-of-custody inputs — never edited. |
| `extracted/` | **Yes** | Reviewed, structured extractions (`*.yaml`). The durable artifact tests run on. |
| `reference/` | **Yes** | Authoritative external datasets (EPA ECHO, USGS/NOAA, RSEI, EIA, parcels). Each folder carries a README naming its source + gaps; regenerable from a `watermark` subcommand. |
| `entities/` | **Yes** | Resolved people & points-of-interest graph. |
| `hypotheses/` | **Yes** | Per-site hypothesis store (boom-origin × site). |
| `research/` | **Yes** | Agent finding manifests and leads (`research/<site>/`). |
| `catalog/` | **Yes** | Pydantic-validated data catalog (`watermark catalog check` in CI). |
| `site/` | **Yes** | Export feeds + the content bundle (`site/bundle/`, built by `watermark export`) and site config (`exhibits.yaml`, the curated PDF allowlist; `leads.yaml`). |
| `cache/`, `scratch/` | No (git-ignored) | Regenerable API responses and intermediate working files. |

## Publishing (the content bundle)

`watermark export` assembles the typed content bundle — JSON feeds + a
`manifest.json` (stamped with `CONTRACT_VERSION`) — from `extracted/` + the repo
`docs/` + the cross-document layer (timeline, entity graph) and writes it to
`data/site/bundle/`. The Astro `web/` app reads that bundle at build time (the
sole presentation tier). The data tier is `src/watermark/site/`.

```bash
watermark export                # write the content bundle to data/site/bundle/
```

Curated source PDFs are published as **Exhibits**; edit
[`site/exhibits.yaml`](site/exhibits.yaml) to add/remove them (page-range slices
are cut from large bundles, so the full file is never republished). Deployment is
to **Cloudflare Pages** (`.github/workflows/pages.yml`); the public cutover is
parity-gated.

## Chain of custody

`documents/**` is litigation evidence: never alter a source byte, and never
rename or "fix" a malformed/typo'd source filename in place — keep the
as-received name and record the canonical name + a content-verified date in a
non-destructive alias manifest (see
`extracted/commissioners/minutes/filename-map.yaml`). Removing a source file is
only OK when it's a checksum-verified byte-identical duplicate.

## Extraction file conventions

Structured extractions are YAML validated by `watermark.models`. Filenames
follow:

```
<subject>.<kind>.opc.yaml      e.g. roundabouts.summary.opc.yaml
                                    roundabouts.detail.opc.yaml
```

- **`opc`** = "Opinion of Probable Cost" (an engineering estimate format).
  Adjust the suffix for other document kinds as the corpus grows.
- **`summary`** = roll-up table; **`detail`** = full line items.

The extracted tree **mirrors `documents/` by collection** — an artifact lands
under the same first-level collection as its source (`aedg/`, `oepa/`,
`recorder/`, …).

### The `~` approximate marker

Source scans are degraded. Any figure read with less than full confidence is
prefixed with `~` (e.g. `~2490`). In YAML this parses as a string; the models
coerce it back to a number via `watermark.models._coerce_number` while signaling
that the value is approximate. **Dollar totals/subtotals are high-confidence;
line-item quantities are often approximate.** Keep the marker — it is research
metadata, never silently dropped.

### Provenance

Every extraction's `meta` block should record: source file, PDF page range,
estimator/basis, date, and a confidence note, and every claim carries an
evidence tag (`[verified]` / `[inference]` / `[reference]` / `[open]`). The
reference extractions (`roundabouts.*.opc.yaml`) are the six Tetra Tech OPC
estimates at pp. 317–328 of `documents/aedg/PRR-01-bundle.ocr.pdf`.
