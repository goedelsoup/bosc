/**
 * Corridor map island (issue #71) — the production replacement for the legacy
 * `gismap.py` HTML blob. deck.gl `GeoJsonLayer`s over a MapLibre basemap, with
 * dated Esri Wayback aerials as deck `TileLayer`s. Mounted client:only over the
 * page's SSR legend/table fallback.
 *
 * Styling is entirely data-driven: fill/line color come from each feature's
 * `color`, point size from `radius` — straight off the typed geo feeds. The only
 * presentation chrome (layer order, names, RSEI-off-by-default) lives in
 * `lib/geoStyle.ts`. Adapted from the spike's CorridorMap.tsx (#70).
 */
import { useEffect, useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import type { Layer } from "@deck.gl/core";
import { GeoJsonLayer } from "@deck.gl/layers";
import { Map } from "react-map-gl/maplibre";
import type { FeatureCollection } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  DEFAULT_OFF,
  layerLabel,
  layersPresent,
  rgba,
  type GeoFeature,
  type GeoProps,
} from "../../lib/geoStyle";
import { rasterTileLayer } from "./rasterTile";

type FC = FeatureCollection<GeoFeature["geometry"], GeoProps>;

const WAYBACK =
  "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile";
const BASEMAPS: Record<string, string | null> = {
  esri: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  "aerial 2014": `${WAYBACK}/5844/{z}/{y}/{x}`,
  "aerial 2024": `${WAYBACK}/16453/{z}/{y}/{x}`,
  street: null, // the MapLibre vector basemap shows through
};
const INITIAL_VIEW_STATE = { longitude: -84.122, latitude: 40.792, zoom: 12.5, pitch: 0, bearing: 0 };

function layerFor(key: string, features: GeoFeature[]): GeoJsonLayer<GeoProps> {
  const data: FeatureCollection = {
    type: "FeatureCollection",
    features: features.filter((f) => f.properties.layer === key),
  };
  return new GeoJsonLayer<GeoProps>({
    id: `layer-${key}`,
    data,
    pickable: true,
    stroked: true,
    filled: true,
    getFillColor: (f) => {
      const p = (f as GeoFeature).properties;
      if (p.role === "point") return rgba(p.color, p.scored === false ? 80 : 210);
      // The watershed boundaries are large context polygons — a faint wash so the
      // corridor stays legible; everything else keeps the standard area fill.
      if (p.layer === "watershed") return rgba(p.color, 22);
      return rgba(p.color, 70);
    },
    getLineColor: (f) => rgba((f as GeoFeature).properties.color, 255),
    lineWidthUnits: "pixels",
    getLineWidth: key === "roadwork" ? 4 : 2,
    pointType: "circle",
    pointRadiusUnits: "pixels",
    getPointRadius: (f) => (f as GeoFeature).properties.radius ?? 6,
  });
}

export default function CorridorMap({ src }: { src: string }): JSX.Element {
  const [fc, setFc] = useState<FC | null>(null);
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [basemap, setBasemap] = useState<string>("esri");
  const [picked, setPicked] = useState<GeoFeature | null>(null);

  useEffect(() => {
    let live = true;
    fetch(src)
      .then((r) => r.json())
      .then((d: FC) => {
        if (!live) return;
        setFc(d);
        const present = layersPresent(d.features as GeoFeature[]);
        setVisible(Object.fromEntries(present.map((l) => [l, !DEFAULT_OFF.has(l)])));
      })
      .catch(() => setFc({ type: "FeatureCollection", features: [] }));
    return () => {
      live = false;
    };
  }, [src]);

  const features = (fc?.features as GeoFeature[]) ?? [];
  const present = layersPresent(features);
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const f of features) c[f.properties.layer] = (c[f.properties.layer] ?? 0) + 1;
    return c;
  }, [fc]);

  const layers = useMemo(() => {
    const out: Layer[] = [];
    const url = BASEMAPS[basemap];
    if (url) out.push(rasterTileLayer(url));
    for (const key of present) if (visible[key]) out.push(layerFor(key, features));
    return out;
  }, [fc, visible, basemap]);

  return (
    <div className="deck-surface">
      <DeckGL
        initialViewState={INITIAL_VIEW_STATE}
        controller
        layers={layers}
        getTooltip={({ object }) =>
          object?.properties?.label ? { html: object.properties.label as string } : null
        }
        onClick={({ object }) => setPicked((object as GeoFeature) ?? null)}
      >
        <Map mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json" />
      </DeckGL>

      <div className="deck-controls">
        <strong>Basemap</strong>
        {Object.keys(BASEMAPS).map((k) => (
          <label key={k}>
            <input type="radio" name="basemap" checked={basemap === k} onChange={() => setBasemap(k)} /> {k}
          </label>
        ))}
        <strong>Layers</strong>
        {present.map((k) => (
          <label key={k}>
            <input
              type="checkbox"
              checked={visible[k] ?? false}
              onChange={(e) => setVisible((v) => ({ ...v, [k]: e.target.checked }))}
            />{" "}
            {layerLabel(k)} ({counts[k] ?? 0})
          </label>
        ))}
      </div>

      {picked?.properties.label && (
        <aside className="deck-popup">
          <button onClick={() => setPicked(null)} aria-label="Close">
            ×
          </button>
          <div dangerouslySetInnerHTML={{ __html: picked.properties.label }} />
        </aside>
      )}
    </div>
  );
}
