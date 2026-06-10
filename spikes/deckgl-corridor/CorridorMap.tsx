/**
 * Production-shape reference for the corridor map island (issue #70 → gates E3.2).
 *
 * This is the *target* form the Epic-2 Astro frontend will mount as a client island:
 * deck.gl overlaid on a MapLibre GL basemap via `@deck.gl/react` + `react-map-gl/maplibre`.
 * The runnable, zero-install proof of the must-haves is `index.html` (deck.gl UMD); this
 * file shows how the same layers compose in the real React/TypeScript toolchain.
 *
 * NOT built in this spike (the repo has no frontend scaffold yet — that's #63, and the
 * disk was full during the spike). `package.json` lists the deps; once #63 lands, drop
 * this into the Astro app, `npm i`, and it compiles. Data comes from the typed GeoJSON
 * feeds in E1.4 (here: today's committed gis-findings.geojson).
 */
import { useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import { GeoJsonLayer } from "@deck.gl/layers";
import { TileLayer } from "@deck.gl/geo-layers";
import { BitmapLayer } from "@deck.gl/layers";
import { Map } from "react-map-gl/maplibre";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";

type LayerKey =
  | "campus" | "jsmc" | "wwtp" | "corridor" | "roadwork" | "floodway" | "floodplain" | "rsei";

interface FindingProps {
  layer: LayerKey;
  label?: string;
  radius?: number;
  scored?: boolean;
  water_flag?: "critical" | "elevated";
}
type Finding = Feature<Geometry, FindingProps>;
type RGBA = [number, number, number, number];

const STYLE: Record<LayerKey, { label: string; fill: RGBA; line: [number, number, number]; width: number; pointRadius?: number }> = {
  campus:     { label: "Campus footprint",       fill: [63, 81, 181, 64],  line: [63, 81, 181],  width: 2 },
  jsmc:       { label: "JSMC (US-owned)",         fill: [109, 76, 65, 77],  line: [109, 76, 65],  width: 2 },
  wwtp:       { label: "WWTP NPDES points",       fill: [0, 137, 123, 230], line: [0, 105, 92],   width: 2, pointRadius: 7 },
  corridor:   { label: "Corridor study area",     fill: [249, 168, 37, 18], line: [249, 168, 37], width: 1 },
  roadwork:   { label: "Roadwork centerline",     fill: [0, 0, 0, 0],       line: [230, 74, 25],  width: 4 },
  floodway:   { label: "FEMA floodway",           fill: [211, 47, 47, 102], line: [211, 47, 47],  width: 1 },
  floodplain: { label: "FEMA floodplain",         fill: [25, 118, 210, 38], line: [25, 118, 210], width: 1 },
  rsei:       { label: "RSEI facilities",         fill: [142, 36, 170, 140], line: [106, 27, 154], width: 1 },
};
const ORDER: LayerKey[] = ["floodplain", "floodway", "corridor", "campus", "jsmc", "roadwork", "wwtp", "rsei"];
const RSEI_RING: Record<string, [number, number, number]> = { critical: [198, 40, 40], elevated: [239, 108, 0] };

const WAYBACK = "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile";
const BASEMAPS: Record<string, string | null> = {
  esri: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  wb2014: `${WAYBACK}/5844/{z}/{y}/{x}`,
  wb2024: `${WAYBACK}/16453/{z}/{y}/{x}`,
  osm: null, // OSM via the MapLibre style instead of a deck TileLayer
};

function rasterBasemap(url: string) {
  return new TileLayer({
    id: `basemap-${url}`,
    data: url,
    minZoom: 0,
    maxZoom: 19,
    tileSize: 256,
    renderSubLayers: (props) => {
      const { boundingBox } = props.tile;
      return new BitmapLayer(props, {
        data: undefined,
        image: props.data,
        bounds: [boundingBox[0][0], boundingBox[0][1], boundingBox[1][0], boundingBox[1][1]],
      });
    },
  });
}

function findingLayer(key: LayerKey, fc: FeatureCollection) {
  const s = STYLE[key];
  const data = { type: "FeatureCollection", features: (fc.features as Finding[]).filter((f) => f.properties.layer === key) };
  const isRsei = key === "rsei";
  return new GeoJsonLayer<Finding>({
    id: `find-${key}`,
    data,
    pickable: true,
    stroked: true,
    filled: true,
    getFillColor: isRsei ? (f) => [142, 36, 170, f.properties.scored ? 140 : 31] : s.fill,
    getLineColor: isRsei ? (f) => [...(RSEI_RING[f.properties.water_flag ?? ""] ?? s.line), 255] as RGBA : [...s.line, 255] as RGBA,
    lineWidthUnits: "pixels",
    getLineWidth: isRsei ? (f) => (f.properties.water_flag ? 3 : 1) : s.width,
    pointType: "circle",
    pointRadiusUnits: "pixels",
    getPointRadius: isRsei ? (f) => f.properties.radius ?? 5 : s.pointRadius ?? 6,
  });
}

const INITIAL_VIEW_STATE = { longitude: -84.122, latitude: 40.792, zoom: 13, pitch: 0, bearing: 0 };

export function CorridorMap({ data }: { data: FeatureCollection }) {
  const [visible, setVisible] = useState<Record<LayerKey, boolean>>(
    () => Object.fromEntries(ORDER.map((k) => [k, k !== "rsei"])) as Record<LayerKey, boolean>,
  );
  const [basemap, setBasemap] = useState<keyof typeof BASEMAPS>("esri");
  const [picked, setPicked] = useState<Finding | null>(null);

  const layers = useMemo(() => {
    const out = [];
    const url = BASEMAPS[basemap];
    if (url) out.push(rasterBasemap(url));
    for (const key of ORDER) if (visible[key]) out.push(findingLayer(key, data));
    return out;
  }, [visible, basemap, data]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <DeckGL
        initialViewState={INITIAL_VIEW_STATE}
        controller
        layers={layers}
        getTooltip={({ object }) => (object?.properties?.label ? { html: object.properties.label } : null)}
        onClick={({ object }) => setPicked((object as Finding) ?? null)}
      >
        {/* OSM/labels base — deck raster tiles interleave above when an aerial is chosen. */}
        <Map mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json" />
      </DeckGL>

      <Controls data={data} visible={visible} setVisible={setVisible} basemap={basemap} setBasemap={setBasemap} />
      {picked?.properties.label && (
        <aside style={{ position: "absolute", bottom: 12, left: 12, maxWidth: 320, background: "rgba(255,255,255,.95)", padding: 12, borderRadius: 8 }}>
          <button onClick={() => setPicked(null)} style={{ float: "right" }}>×</button>
          <div dangerouslySetInnerHTML={{ __html: picked.properties.label }} />
        </aside>
      )}
    </div>
  );
}

function Controls(props: {
  data: FeatureCollection;
  visible: Record<LayerKey, boolean>;
  setVisible: (v: Record<LayerKey, boolean>) => void;
  basemap: string;
  setBasemap: (b: keyof typeof BASEMAPS) => void;
}) {
  const counts = useMemo(() => {
    const c: Partial<Record<LayerKey, number>> = {};
    for (const f of props.data.features as Finding[]) c[f.properties.layer] = (c[f.properties.layer] ?? 0) + 1;
    return c;
  }, [props.data]);

  return (
    <div style={{ position: "absolute", top: 12, left: 12, background: "rgba(255,255,255,.94)", padding: 12, borderRadius: 8, maxWidth: 260 }}>
      <strong>Basemap</strong>
      {Object.keys(BASEMAPS).map((k) => (
        <label key={k} style={{ display: "block" }}>
          <input type="radio" name="bm" checked={props.basemap === k} onChange={() => props.setBasemap(k as keyof typeof BASEMAPS)} /> {k}
        </label>
      ))}
      <strong>Layers</strong>
      {ORDER.filter((k) => counts[k]).map((k) => (
        <label key={k} style={{ display: "block" }}>
          <input
            type="checkbox"
            checked={props.visible[k]}
            onChange={(e) => props.setVisible({ ...props.visible, [k]: e.target.checked })}
          /> {STYLE[k].label} ({counts[k]})
        </label>
      ))}
    </div>
  );
}
