# data/reference/imagery/

AOI-clipped satellite captures for the tracking sites, produced by
[`bosc imagery pull`](../../../docs/imagery-subsystem.md) (`bosc.gis.raster`).

## Layout

```
<site>/<collection>/<acquisition-date>.<asset>.tif       # the clipped GeoTIFF
<site>/<collection>/<acquisition-date>.<asset>.tif.yaml   # provenance sidecar
```

e.g. `campus/sentinel-2-l2a/2024-09-20.visual.tif` + `.tif.yaml`.

## Source & discipline

- **Source:** free/open collections via the Microsoft Planetary Computer STAC catalog
  — `sentinel-2-l2a` (ESA Copernicus, open), `naip` / `landsat-c2-l2` (US public
  domain). The site AOIs come from `data/site/gis-findings.geojson`.
- **Pixels are verbatim.** Each `.tif` is a windowed read of the source COG clipped to
  the site AOI, in the scene's **native CRS — no resampling** or radiometric change.
- **Chain of custody** lives in the sidecar: the `scene_id` and unsigned `source_url`
  (re-pull the identical pixels from the archive), the **sensing date vs. retrieval
  timestamp** (kept distinct), CRS, AOI bbox, processing note, and a **sha256** of the
  GeoTIFF.
- GeoTIFFs are **Git LFS**-tracked (see `.gitattributes`); the raw signed scene reads
  are not cached here. Regenerate any capture with `bosc imagery pull`.

## Gaps

- Only what has been pulled so far. The campus is the first tracking site; the Amazon
  warehouse parcel and the off-stream reservoir need geometry added to the GIS findings
  before they can be captured.
