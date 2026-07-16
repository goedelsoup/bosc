/**
 * DispersionMap island (#1234, epic #1237) — the air view. It mounts the reusable
 * `FieldLayer` (#1233) over the gridded AERMOD screening surface (`air-dispersion-field`
 * feed, #1232), mirroring `CorridorMap.tsx` (DeckGL + `react-map-gl/maplibre` +
 * `rasterTileLayer`). client:only over the page's SSR peak-concentration table.
 *
 * The whole field is **modeled screening data**: the permit redacts the genset stack as
 * CBI, so every concentration is `[inference]`, never `[verified]` — the page carries the
 * amber provenance banner (SSR), and this island only draws the field.
 *
 * Field semantics (via FieldLayer's threshold/limit tinting):
 *   - `limit = NAAQS` always → cells over the standard tint toward `--ev-gap` (oxblood
 *     exceedance), the load-bearing regulatory read.
 *   - `threshold = NAAQS` when the NAAQS isopleth is on → the labeled ink hairline + its
 *     amber `--ev-inference` halo + the faint interior isopleths; off → a clean raster with
 *     only the oxblood exceedance zones (the standard crossing never hides).
 *
 * The receptor feed is row-major from the SOUTH edge (`values[iy*nx+ix]`, iy=0 at the SW
 * corner); `FieldGrid` rows run NORTH-first, so `toGrid` flips rows.
 */
import { useEffect, useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import type { Layer } from "@deck.gl/core";
import { Map } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { DispersionField, DispersionPeriodField } from "@watermark/core/feeds";
import { bilinear, type FieldGrid } from "@watermark/viz/field";
import FieldLayer, { readFieldColors } from "./FieldLayer";
import { rasterTileLayer } from "./rasterTile";

const BASEMAPS: Record<string, string | null> = {
  esri: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  street: null, // the MapLibre vector basemap shows through
};

/** AERMOD `AVE` token → a reader label for the averaging-period switcher. */
function periodLabel(ave: string): string {
  if (ave.toUpperCase() === "ANNUAL") return "Annual";
  return `${ave}-hour`;
}

/** Reshape one period of a `DispersionField` into a north-first `FieldGrid`. */
function toGrid(field: DispersionField, period: DispersionPeriodField): FieldGrid | null {
  const { nx, ny } = field.grid;
  const src = period.values;
  if (src.length !== nx * ny) return null;
  const values = new Float32Array(nx * ny);
  for (let iy = 0; iy < ny; iy++) {
    const dstRow = ny - 1 - iy; // feed row 0 = south; FieldGrid row 0 = north
    for (let ix = 0; ix < nx; ix++) {
      const v = src[iy * nx + ix];
      values[dstRow * nx + ix] = v == null ? Number.NaN : v;
    }
  }
  const { sw_lon, sw_lat, ne_lon, ne_lat } = field.geo_ref;
  return { width: nx, height: ny, values, bounds: [sw_lon, sw_lat, ne_lon, ne_lat] };
}

/** Bilinear µg/m³ at a `[lng, lat]`, or `null` when outside the grid / over a no-data cell. */
function sampleAt(grid: FieldGrid, lng: number, lat: number): number | null {
  const b = grid.bounds;
  if (!b) return null;
  const [w, s, e, n] = b;
  if (lng < w || lng > e || lat < s || lat > n) return null;
  const col = ((lng - w) / (e - w)) * (grid.width - 1);
  const row = ((n - lat) / (n - s)) * (grid.height - 1);
  const v = bilinear(grid, col, row);
  return Number.isNaN(v) ? null : v;
}

interface Probe {
  value: number | null;
}

export default function DispersionMap({ src }: { src: string }): JSX.Element {
  const [fields, setFields] = useState<DispersionField[] | null>(null);
  const [pollutantIdx, setPollutantIdx] = useState(0);
  const [periodIdx, setPeriodIdx] = useState(0);
  const [showNaaqs, setShowNaaqs] = useState(true);
  const [basemap, setBasemap] = useState<string>("esri");
  const [probe, setProbe] = useState<Probe | null>(null);

  const colors = useMemo(() => readFieldColors(), []);

  useEffect(() => {
    let live = true;
    fetch(src)
      .then((r) => r.json())
      .then((d: DispersionField[]) => {
        if (live) setFields(Array.isArray(d) ? d : []);
      })
      .catch(() => {
        if (live) setFields([]);
      });
    return () => {
      live = false;
    };
  }, [src]);

  // Only the pollutants that actually carry a modeled surface are switchable.
  const modeled = useMemo(
    () => (fields ?? []).filter((f) => f.available && f.periods.some((p) => p.values.length > 0)),
    [fields],
  );
  const field = modeled[Math.min(pollutantIdx, modeled.length - 1)] ?? null;
  const period = field?.periods[Math.min(periodIdx, (field?.periods.length ?? 1) - 1)] ?? null;
  const grid = useMemo(() => (field && period ? toGrid(field, period) : null), [field, period]);
  const naaqs = period?.naaqs_ug_m3 ?? null;

  // Controlled camera: DeckGL treats `initialViewState` as mount-only, but the field loads
  // after mount, so we drive `viewState` ourselves and recenter on the field's source anchor
  // whenever it changes (first load, or a field whose grid is centered elsewhere), leaving the
  // user's own pan/zoom untouched in between.
  const [viewState, setViewState] = useState({
    longitude: -84.122,
    latitude: 40.792,
    zoom: 12,
    pitch: 0,
    bearing: 0,
  });
  const srcLon = field?.geo_ref.source_lon;
  const srcLat = field?.geo_ref.source_lat;
  useEffect(() => {
    if (srcLon == null || srcLat == null) return;
    setViewState((v) => ({ ...v, longitude: srcLon, latitude: srcLat }));
  }, [srcLon, srcLat]);

  const layers = useMemo(() => {
    const out: Layer[] = [];
    const url = BASEMAPS[basemap];
    if (url) out.push(rasterTileLayer(url));
    if (grid) {
      out.push(
        new FieldLayer({
          id: "dispersion-field",
          data: grid,
          threshold: showNaaqs && naaqs != null ? naaqs : Number.POSITIVE_INFINITY,
          limit: naaqs,
          showIsopleths: showNaaqs,
          thresholdLabel: showNaaqs && naaqs != null ? `NAAQS ${naaqs} µg/m³` : undefined,
          colors,
          opacity: 1,
        }),
      );
    }
    return out;
  }, [grid, basemap, showNaaqs, naaqs, colors]);

  if (fields && modeled.length === 0) {
    return (
      <div className="deck-surface deck-surface--empty">
        <p className="deck-loading">
          No modeled air-dispersion field on the record for this site yet — the peak-concentration table below
          carries what is disclosed.
        </p>
      </div>
    );
  }

  return (
    <div
      className="deck-surface"
      role="figure"
      aria-label="Interactive modeled air-dispersion field over the campus (deck.gl); the peak concentrations are also listed as a table on this page."
    >
      <DeckGL
        viewState={viewState}
        onViewStateChange={(e) => setViewState(e.viewState as typeof viewState)}
        controller
        layers={layers}
        onHover={({ coordinate }) => {
          if (!grid || !coordinate) return setProbe(null);
          setProbe({ value: sampleAt(grid, coordinate[0], coordinate[1]) });
        }}
      >
        <Map mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json" />
      </DeckGL>

      <div className="deck-controls">
        {modeled.length > 1 && (
          <>
            <strong>Pollutant</strong>
            {modeled.map((f, i) => (
              <label key={f.pollutant}>
                <input
                  type="radio"
                  name="pollutant"
                  checked={pollutantIdx === i}
                  onChange={() => {
                    setPollutantIdx(i);
                    setPeriodIdx(0);
                  }}
                />{" "}
                {f.pollutant}
              </label>
            ))}
          </>
        )}
        <strong>Averaging period</strong>
        {(field?.periods ?? []).map((p, i) => (
          <label key={p.averaging_period}>
            <input type="radio" name="period" checked={periodIdx === i} onChange={() => setPeriodIdx(i)} />{" "}
            {periodLabel(p.averaging_period)}
          </label>
        ))}
        <strong>Reference</strong>
        <label>
          <input type="checkbox" checked={showNaaqs} onChange={(e) => setShowNaaqs(e.target.checked)} /> NAAQS
          isopleth
        </label>
        <strong>Basemap</strong>
        {Object.keys(BASEMAPS).map((k) => (
          <label key={k}>
            <input type="radio" name="basemap" checked={basemap === k} onChange={() => setBasemap(k)} /> {k}
          </label>
        ))}
      </div>

      <div className="deck-probe" aria-live="polite">
        <span className="deck-probe-label">
          {field?.pollutant} · {period ? periodLabel(period.averaging_period) : "—"}
        </span>
        <span className="deck-probe-value">
          {probe == null
            ? "hover the field"
            : probe.value == null
              ? "no receptor"
              : `${probe.value.toFixed(2)} µg/m³`}
        </span>
        {naaqs != null && <span className="deck-probe-meta">NAAQS {naaqs} µg/m³ · [inference]</span>}
      </div>
    </div>
  );
}
