# data/

| Directory | Committed? | Contents |
|-----------|-----------|----------|
| `documents/` | No (git-ignored) | Raw source material: PRR PDF bundles, scans, images. Immutable inputs. |
| `extracted/` | **Yes** | Reviewed, structured extractions (`*.opc.yaml`). The durable artifact. |
| `site/` | **Yes** | Site config — currently `exhibits.yaml`, the curated PDF allowlist. |
| `cache/`, `scratch/` | No | Regenerable intermediate working files. |

## Publishing (GitHub Pages)

`bosc site build` stages a markdown source tree under `web/` from `extracted/` +
the repo `docs/` + the cross-document layer (timeline, entity graph), then renders
it to plain multipage HTML under `site/` (Python-Markdown + Jinja2 — no MkDocs).
Both `web/` and `site/` are git-ignored and fully regenerable — the generator
(`src/bosc/site/`) is the source.

```bash
uv sync --extra docs       # install the renderer (markdown + jinja2)
bosc site build            # stage web/ and render site/
bosc site serve            # rebuild + local preview at http://localhost:8000
```

Curated source PDFs are published as **Exhibits**; edit
[`site/exhibits.yaml`](site/exhibits.yaml) to add/remove them (page-range slices
are cut from large bundles, so the full file is never republished). Deployment is
**manual** (`.github/workflows/pages.yml`, `workflow_dispatch`) — the site is a
private/unlisted draft until you choose to publish.

## Extraction file conventions

Structured extractions are YAML validated by `bosc.models`. Filenames follow:

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
coerce it back to a number via `bosc.models._coerce_number` while signaling that
the value is approximate. **Dollar totals/subtotals are high-confidence; line-item
quantities are often approximate.** Keep the marker — it is research metadata.

### Provenance

Every extraction's `meta` block should record: source file, PDF page range,
estimator/basis, date, and a confidence note. The reference extractions
(`roundabouts.*.opc.yaml`) come from the financial-projections section of
`documents/aedg/PRR-01-bundle.ocr.pdf` (~page 370 onward).
