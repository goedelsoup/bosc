# DeckGL corridor spike (#70)

A throwaway spike to confirm DeckGL can carry the BOSC maps before we commit to it for
Epic 3. It renders the committed corridor findings
([`data/site/gis-findings.geojson`](../../data/site/gis-findings.geojson)) and exercises
every must-have. The **decision and recommendation** live in
[`docs/deckgl-spike.md`](../../docs/deckgl-spike.md).

## What's here

| File | What it is | Status |
|---|---|---|
| `index.html` | Zero-install runnable prototype — deck.gl UMD from CDN, no build step | ✅ runnable now |
| `CorridorMap.tsx` | Production-shape island (`@deck.gl/react` + `react-map-gl/maplibre`) | reference only — compiles once the Astro scaffold (#63) exists |
| `package.json` | Deps for the `.tsx` reference | not installed (spike ran on a full disk) |

## Run the prototype

It `fetch()`es the committed GeoJSON, so it needs a static server (a `file://` open is
blocked by CORS). From the **repo root**:

```sh
python3 -m http.server 8000
# then open:
open http://localhost:8000/spikes/deckgl-corridor/
```

Override the data source with `?data=<url>` if you want to point it at a different feed.

## What it proves (the issue's must-haves)

- **GeoJsonLayer polygons + points, per-layer styling** — campus / JSMC / flood polygons,
  corridor study area, roadwork centerline (LineString), WWTP + RSEI points; colors and
  widths ported from `bosc.site.gismap`.
- **Click popups (+ hover tooltips)** — hover shows the committed HTML label; click pins
  it in the info panel.
- **Layer toggles** — one checkbox per present layer (RSEI off by default, matching the
  current Leaflet map), plus a basemap selector.
- **Raster TILE layers** — OSM, Esri World Imagery (current), and dated **Esri Wayback**
  aerials (2014 / 2024) as deck.gl `TileLayer` + `BitmapLayer`.

This directory is disposable: once E3.2 builds the real island, delete `spikes/`.
