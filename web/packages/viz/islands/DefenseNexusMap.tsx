/**
 * Defense-nexus map (#233 interactive layer). The campus footprint and the JSMC
 * (US-owned) footprint on one deck.gl map, with the **measured gap between them**
 * drawn as a neutral dimension line — not an arrow, not a flow. The whole point of
 * the companion essay is that geographic proximity is not a connection; this makes
 * the proximity literal (you can see the city between them) and the distance exact
 * (computed from the cited parcels, ~5.5 mi), so neither the prose nor the picture
 * can quietly upgrade adjacency into a finding.
 *
 * Three fact tabs (geography / capability / silence) shift the map's emphasis and
 * the readout; the "silence" tab puts the empty gap front and centre — the measured
 * distance with nothing drawn across it, because the record draws nothing across it.
 *
 * Mounted client:only over the page's SSR fallback table (no-JS readable). Data is
 * the build-time `DefenseNexusData` prop; the island imports only the types.
 */
import { useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import type { Layer } from "@deck.gl/core";
import { GeoJsonLayer, LineLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { Map } from "react-map-gl/maplibre";
import type { FeatureCollection } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
import { rgba, type GeoFeature, type GeoProps } from "@watermark/viz/geoStyle";
import type {
  DefenseNexusData,
  DnAnnotation,
  DnEmphasis,
  DnFactKey,
  DnRegister,
} from "@watermark/viz/defenseNexus";
import { RegisterMark } from "./uncertaintyGrammar";
import { rasterTileLayer } from "./rasterTile";

const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const GAP = [96, 102, 120] as const; // neutral slate — a ruler, not a relationship
// Register-encoded annotation pills (matching the engine grammar): verified green,
// inference amber, open slate. Labeled facts on the map — never a connecting line.
const REG_RGB: Record<DnRegister, [number, number, number, number]> = {
  verified: [46, 125, 50, 235],
  inference: [176, 106, 0, 235],
  open: [110, 114, 124, 235],
};

function footprint(
  key: "campus" | "jsmc",
  features: GeoFeature[],
  alpha: number,
  emphasized: boolean,
): GeoJsonLayer<GeoProps> {
  const data: FeatureCollection = {
    type: "FeatureCollection",
    features: features.filter((f) => f.properties.layer === key),
  };
  return new GeoJsonLayer<GeoProps>({
    id: `dn-${key}`,
    data,
    pickable: true,
    stroked: true,
    filled: true,
    getFillColor: (f) => rgba((f as GeoFeature).properties.color, alpha),
    getLineColor: (f) => rgba((f as GeoFeature).properties.color, 255),
    lineWidthUnits: "pixels",
    getLineWidth: emphasized ? 2.5 : 1.5,
    updateTriggers: { getFillColor: alpha, getLineWidth: emphasized },
  });
}

export default function DefenseNexusMap({ data }: { data: DefenseNexusData }): JSX.Element {
  const [active, setActive] = useState<DnFactKey>("geography");
  const [basemap, setBasemap] = useState<"imagery" | "street">("imagery");

  const fact = data.facts.find((f) => f.key === active) ?? data.facts[0];
  const emphasis: DnEmphasis = fact?.emphasis ?? "gap";
  // `data.geo` is FeatureCollection<Polygon, GeoProps>; widen Polygon → Geometry to the
  // shared GeoFeature (a safe single cast, not `as unknown as`). Memoized so the layers-memo
  // dep stays stable (#586).
  const features = useMemo<GeoFeature[]>(() => data.geo.features as GeoFeature[], [data.geo.features]);
  const [a, b] = data.metrics.nearestPair;
  const gapOn = emphasis === "gap";

  const layers = useMemo(() => {
    const out: Layer[] = [];
    // Derive the gap-label midpoint inside the memo: as a fresh `[x,y]` literal at module scope
    // it was a dep that changed identity every render, so the layers never cached (#586).
    const mid: [number, number] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    if (basemap === "imagery") out.push(rasterTileLayer(ESRI));
    out.push(footprint("jsmc", features, emphasis === "jsmc" ? 165 : 70, emphasis === "jsmc"));
    out.push(footprint("campus", features, emphasis === "campus" ? 165 : 70, emphasis === "campus"));
    // The measured gap: a single neutral dimension line + end ticks + a label.
    out.push(
      new LineLayer({
        id: "dn-gap-line",
        data: [{ from: a, to: b }],
        getSourcePosition: (d) => d.from,
        getTargetPosition: (d) => d.to,
        getColor: [...GAP, gapOn ? 255 : 170],
        getWidth: gapOn ? 3 : 1.5,
        widthUnits: "pixels",
      }),
      new ScatterplotLayer({
        id: "dn-gap-ends",
        data: [a, b],
        getPosition: (d) => d,
        getRadius: gapOn ? 5 : 3.5,
        radiusUnits: "pixels",
        getFillColor: [...GAP, 255],
        stroked: true,
        getLineColor: [255, 255, 255, 255],
        lineWidthUnits: "pixels",
        getLineWidth: 1.5,
      }),
      new TextLayer({
        id: "dn-gap-label",
        data: [{ position: mid, text: `~${data.metrics.nearestMi.toFixed(1)} mi` }],
        getPosition: (d) => d.position,
        getText: (d) => d.text,
        getSize: 13,
        getColor: [38, 42, 58, 255],
        getPixelOffset: [0, -12],
        background: true,
        getBackgroundColor: [255, 255, 255, 235],
        backgroundPadding: [6, 3, 6, 3],
        fontFamily: "ui-monospace, monospace",
        fontWeight: 700,
        characterSet: "auto",
      }),
    );
    // The active tab's annotation — a register-encoded label pinned to real geometry.
    // Offset BELOW the point so the "No records" marker sits opposite the distance label,
    // on the gap line, where an inferred connection would be drawn — but never is.
    const ann = data.annotations.filter((x) => x.key === active);
    if (ann.length > 0) {
      out.push(
        new TextLayer<DnAnnotation>({
          id: "dn-annotation",
          data: ann,
          getPosition: (d) => d.position,
          getText: (d) => d.label,
          getSize: 11,
          getColor: [255, 255, 255, 255],
          getPixelOffset: [0, 16],
          getTextAnchor: "middle",
          background: true,
          getBackgroundColor: (d) => REG_RGB[d.register],
          backgroundPadding: [6, 4, 6, 4],
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
          fontWeight: 600,
          characterSet: "auto",
          maxWidth: 16,
          wordBreak: "break-word",
        }),
      );
    }
    return out;
  }, [features, emphasis, basemap, gapOn, a, b, data.metrics.nearestMi, data.annotations, active]);

  return (
    <div className="dn">
      <div
        className="deck-surface dn-map"
        role="figure"
        aria-label="Interactive map: the data-center campus footprint and the JSMC (US-owned) footprint, with the measured gap between them. The same facts and figures are in the table on this page."
      >
        <DeckGL
          initialViewState={{ ...data.view, pitch: 0, bearing: 0 }}
          controller
          layers={layers}
          getTooltip={({ object }) =>
            (object as GeoFeature)?.properties?.label
              ? { html: (object as GeoFeature).properties.label as string }
              : null
          }
        >
          <Map mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json" />
        </DeckGL>

        <div className="deck-controls dn-controls">
          <strong>Basemap</strong>
          {(["imagery", "street"] as const).map((k) => (
            <label key={k}>
              <input type="radio" name="dn-basemap" checked={basemap === k} onChange={() => setBasemap(k)} />{" "}
              {k}
            </label>
          ))}
          <div className="dn-key">
            <span className="dn-key-row">
              <span className="dn-swatch" style={{ background: "#3f51b5" }} /> Campus (Bistrozzi LLC)
            </span>
            <span className="dn-key-row">
              <span className="dn-swatch" style={{ background: "#6d4c41" }} /> JSMC (UNITED STATES)
            </span>
            <span className="dn-key-row">
              <span className="dn-rule" /> measured gap
            </span>
          </div>
        </div>
      </div>

      <div className="dn-tabs" role="group" aria-label="The three confirmed facts">
        {data.facts.map((f) => (
          <button
            key={f.key}
            type="button"
            className={`dn-tab${f.key === active ? " is-active" : ""}`}
            aria-pressed={f.key === active}
            onClick={() => setActive(f.key)}
          >
            {f.tab}
          </button>
        ))}
      </div>

      <div className="dn-detail" role="status" aria-live="polite">
        <div className="dn-detail-head">
          <h3 className="dn-detail-title">{fact?.title}</h3>
          <RegisterMark register="verified" label="[verified]" />
        </div>
        <p className="dn-detail-body">{fact?.body}</p>
        <p className="dn-cite">{fact?.cite}</p>
      </div>

      <div className="dn-metrics" aria-hidden="true">
        <span className="dn-metric">
          <strong>~{data.metrics.nearestMi.toFixed(1)} mi</strong> nearest parcels
        </span>
        <span className="dn-metric">
          <strong>~{data.metrics.centroidMi.toFixed(1)} mi</strong> center to center
        </span>
        <span className="dn-metric">
          <strong>~{Math.round(data.metrics.jsmcAcres)} ac</strong> JSMC, US-owned
        </span>
      </div>

      <div className="dn-readout">
        <div className="dn-readout-row">
          <RegisterMark register="verified" label="[verified]" />
          <span>{data.readout.verified}</span>
        </div>
        <div className="dn-readout-row">
          <RegisterMark register="open" label="[open]" />
          <span>{data.readout.open}</span>
        </div>
      </div>
    </div>
  );
}
