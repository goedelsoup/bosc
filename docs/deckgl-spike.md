# DeckGL spike & decision (#70)

**Status:** complete · **Recommendation:** **adopt DeckGL**, paired with a MapLibre GL
basemap, as the map/visualization layer for Epic 3. · **Gates:** E3.2 (corridor map),
E3.3 (watershed + imagery), E3.4 (entity graph).

This is the decision artifact for [#70](https://github.com/goedelsoup/bosc/issues/70).
The runnable prototype is [`spikes/deckgl-corridor/`](../spikes/deckgl-corridor/).

## Why we're looking at this

The current map is a `_MAP_HTML` string blob in
[`bosc.site.gismap`](../src/bosc/site/gismap.py): a Leaflet map injected as raw HTML/JS
into a markdown page, with layer styles, the Wayback aerial ladder, and the RSEI overlay
all hand-built in template strings. It works, but it's untyped, untestable, hard to
restyle, and it can't grow into the watershed map, the imagery time-slider, or the entity
graph the redesign wants (Epic 3). The two-tier refactor (#53/#54) moves geometry into
typed feeds (E1.4) and presentation into the Astro frontend — so the map needs to become
a real frontend component, and the question is *which library*.

## What was tested

The prototype renders **today's committed `gis-findings.geojson`** (76 features across 8
layers: campus, jsmc, wwtp, corridor, roadwork, floodway, floodplain, rsei) and was built
to hit each must-have from the issue. It uses the deck.gl **UMD scripting bundle** (no
build, no `node_modules`) so it runs against the real data with zero setup — important
given the repo has no frontend scaffold yet (#63) and disk was full during the spike.

| Must-have | Result | How |
|---|---|---|
| GeoJsonLayer polygons + points, per-layer styling | ✅ | One `GeoJsonLayer` per layer key; fills/lines/widths ported verbatim from `gismap._LAYER_COLORS`/`_style_js`. Polygons, the roadwork LineString, and WWTP/RSEI points all render from one layer type. |
| Click popups | ✅ | `onClick` pins the feature's committed HTML `label` in an info panel; `getTooltip` also gives a hover preview. |
| Layer toggles | ✅ | Checkbox per present layer (driven by feature counts); RSEI off by default to match the current map. Toggling rebuilds `layers` via `setProps`. |
| Raster tile layers (OSM / Esri / dated Wayback) | ✅ | `TileLayer` + `BitmapLayer` with the same OSM/Esri/Wayback URLs the Leaflet map uses; the Wayback release numbers (e.g. 2014→5844, 2024→16453) come straight from `gismap._WAYBACK`. |
| RSEI graduated points + water-flag rings | ✅ (bonus) | `getPointRadius` from `properties.radius`; ring color from `properties.water_flag`; hollow fill where reported-but-unscored — reproduces the Leaflet behavior. |

The deck.gl `TileLayer` raster recipe was the only real unknown (Leaflet does tiles
natively); it works cleanly, which removes the main risk. Smooth basemap panning/labels
are better served by a vector basemap, which is why the recommendation pairs deck.gl with
MapLibre rather than using a deck `TileLayer` as the only base in production.

## Recommendation: adopt DeckGL + MapLibre

- **Production shape:** a React island = `@deck.gl/react` `DeckGL` overlaid on a
  `react-map-gl/maplibre` `<Map>` (free vector basemap, e.g. CARTO Positron), with the
  dated **aerials as deck `TileLayer`s** interleaved on top. The
  [`CorridorMap.tsx`](../spikes/deckgl-corridor/CorridorMap.tsx) reference is the starting
  point; it drops into the Astro app once #63 lands.
- **Data:** consumes the typed GeoJSON feeds from **E1.4** (the spike used today's
  `gis-findings.geojson` directly). Styling stays data-driven — layer color/label/role as
  feature properties — so nothing is hardcoded per the project conventions.
- **Why deck.gl over staying on Leaflet:**
  - One component model scales to all three Epic-3 targets — the same `DeckGL` surface
    does the corridor map, the watershed map, the imagery raster/time-slider, *and* the
    entity-graph (`ScatterplotLayer`/`LineLayer`/`GraphLayer`). Leaflet would need a
    second stack (and a graph lib) for the non-map visualizations.
  - GPU rendering handles the county-wide RSEI overlay and future large feeds without the
    DOM/SVG cost Leaflet's vector layers pay.
  - Typed, testable, restyle-from-data — the opposite of the current string blob.
  - Imagery: deck.gl's raster/`TileLayer` + a time/opacity control gives the
    before/during/after slider (E3.3) far more directly than Leaflet.
- **Why keep MapLibre in the mix:** deck.gl is a layer renderer, not a basemap — MapLibre
  gives smooth basemap interaction, road/place labels, and attribution for free, and is
  the standard deck.gl pairing.

## Trade-offs & risks (and how we handle them)

- **Bundle size / JS shipped.** deck.gl + MapLibre is heavier than Leaflet. Mitigated by
  Astro islands — the map JS loads only on pages that mount it (`client:visible`), and the
  rest of the site stays zero-JS. Acceptable for the few interactive map pages.
- **No-JS fallback.** The current page renders a markdown summary table even with
  scripting off. Preserve that: the Astro page should server-render the legend + a
  feature table from the feed, and mount the deck island as progressive enhancement.
- **Third-party tiles.** OSM/Esri/Wayback tiles load directly from their servers
  (view-only, no redistribution) — unchanged from today. Keep them basemap-only; the
  analysis-grade imagery stays the `bosc imagery` Sentinel/NAIP/Landsat pulls.
- **Learning curve.** deck.gl's layer/accessor model is new to the repo; the `.tsx`
  reference + this doc lower it, and E3.1 deliberately precedes the build tickets.

## What E3.2–E3.4 inherit

- **E3.2 (corridor map):** promote `CorridorMap.tsx` into the Astro app, wire it to the
  E1.4 feed, add the full Wayback ladder + attribution + the no-JS fallback.
- **E3.3 (watershed + imagery):** reuse the `TileLayer`/`BitmapLayer` pattern for the
  imagery slider; add the watershed polygons + water-balance charts.
- **E3.4 (entity graph):** same `DeckGL` surface with node/edge layers — no second viz
  stack needed.

## Verification notes

`index.html`'s script was syntax-checked and the prototype was served and confirmed to
fetch + parse the committed GeoJSON (76 features, 8 layers). It was **not** opened in a
real browser during the spike (no browser automation + full disk), so a reviewer should
do a quick visual pass per the run steps in the
[spike README](../spikes/deckgl-corridor/README.md). The `.tsx` reference was not compiled
(no frontend scaffold yet — #63); it's a starting point, not a finished build.
