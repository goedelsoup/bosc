# Reach-network river centerlines

Real river-centerline geometry for the model reach network — the lines the deck.gl
`FlowLayer` GPU particle-advection viz (epic #1237 / #1235) advects over. One
`<site>.geojson` per watershed point (`lima.geojson` today).

## Source

USGS **NLDI** (Network-Linked Data Index) navigation over the **NHDPlus** flowline network
(`watermark.hydrology.connectors.nldi`), stitched + cut per reach by
`watermark.hydrology.reach_geometry`. Regenerate with:

```sh
watermark reaches --site lima --write
```

The navigation plan (gage id, tributary WWTP anchors, nav distances, the head/reach split
point) is the committed [`../reach-nav.yaml`](../reach-nav.yaml); reach identity/order come
from [`../network.yaml`](../network.yaml) and the cut ratios from
[`../reaches.yaml`](../reaches.yaml). Raw NLDI responses cache under the git-ignored
`data/cache/`; the offline test fixtures live in `tests/fixtures/hydrology/nldi/`.

## Discipline & gaps

- Centerline geometry is **verbatim NHDPlus** (WGS84), display-only — no reprojection or
  simplification. The model reaches carry no coordinates of their own, so nothing here is
  invented: a reach with no NLDI geometry is **skipped**, never faked.
- The **mainstem** is one navigated line split at the real gage point; the portion above the
  gage is cut into `ottawa-head` / `lima-abstraction` by their `reaches.yaml` length ratios
  (a proportional cut of the real arc length — **not** an NHDPlus segment boundary). The
  portion below is the single `lima-reach` assimilative reach, which runs past both tributary
  confluences to the Auglaize-ward outlet.
- **Tier-0 screening** geometry for a flow visualization — not a calibrated hydraulic network.
