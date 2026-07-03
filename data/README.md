# data/

| Directory | Committed? | Contents |
|-----------|-----------|----------|
| `documents/` | No (git-ignored) | Raw source material: PRR PDF bundles, scans, images. Immutable inputs. |
| `extracted/` | **Yes** | Reviewed, structured extractions (`*.opc.yaml`). The durable artifact. |
| `site/` | **Yes** | Site config — currently `exhibits.yaml`, the curated PDF allowlist. |
| `cache/`, `scratch/` | No | Regenerable intermediate working files. |

## Publishing (the content bundle)

`watermark export` assembles the typed content bundle — JSON feeds + a manifest — from
`extracted/` + the repo `docs/` + the cross-document layer (timeline, entity graph)
and writes it to `data/site/bundle/`. The Astro `web/` app reads that bundle
at build time (the sole presentation tier). The data tier is `src/watermark/site/`.

```bash
watermark export                # write the content bundle to data/site/bundle/
```

Curated source PDFs are published as **Exhibits**; edit
[`site/exhibits.yaml`](site/exhibits.yaml) to add/remove them (page-range slices
are cut from large bundles, so the full file is never republished). Deployment is
to **Cloudflare Pages** (`.github/workflows/pages.yml`); the public cutover to the
new site is parity-gated.

## Extraction file conventions

Structured extractions are YAML validated by `watermark.models`. Filenames follow:

```
<subject>.<kind>.opc.yaml      e.g. roundabouts.summary.opc.yaml
                                    roundabouts.detail.opc.yaml
```

- **`opc`** = "Opinion of Probable Cost" (Tetra Tech's estimate format). Adjust
  the suffix for other document types as the corpus grows.
- **`summary`** = roll-up table; **`detail`** = full line items.

### The `~` approximate marker

Source scans are degraded. Any figure read with less than full confidence is
prefixed with `~` (e.g. `~2490`). In YAML this parses as a string; the models
coerce it back to a number via `watermark.models._coerce_number` while signaling that
the value is approximate. **Dollar totals/subtotals are high-confidence; line-item
quantities are often approximate.** Keep the marker — it is research metadata.

### Provenance

Every extraction's `meta` block should record: source file, PDF page range,
estimator/basis, date, and a confidence note. The reference extractions
(`roundabouts.*.opc.yaml`) come from the financial-projections section of
`documents/aedg/PRR-01-bundle.ocr.pdf` (~page 370 onward).
