# Sanitary — extracted records

**Collection:** `sanitary/` · reviewed structured artifacts (mirrors `data/documents/sanitary/`)

Structured extractions of the sanitary as-built / record drawings under
[`data/documents/sanitary/`](../../documents/sanitary/), produced by the
discipline-agnostic engineering extractor
(`watermark.pipeline.extract.extract_engineering`, `kind=sanitary` → `<stem>.sanitary.yaml`).

## Status

| Source | Extraction | State |
|---|---|---|
| `indianbrook-ps-asbuilt-2007.pdf` | `indianbrook-ps-asbuilt-2007.sanitary.yaml` | **pending a keyed vision pass** |

The Indian Brook as-built is a 4-page scan with **no text layer**, so the extraction
is a vision read that needs `ANTHROPIC_API_KEY` (gap tracked in **#124**). The
machinery (`EngineeringRecord` model + `extract_sanitary` + offline tests) is in
place; the structured YAML is **not hand-authored** — per chain-of-custody, the
forcemain size, pump capacities, and design flows must be read off the drawing, not
invented. Run once a key is available:

```
watermark extract indianbrook-ps-asbuilt-2007 --kind sanitary --write
```

See `watermark.models.EngineeringRecord` for the schema (the `components`/`specs` and
`sheets`/`design_parameters` axes) and [issue #41](https://github.com/watermark-directory/the-watermark-directory/issues/41).
