/**
 * FlowMap island (#1235, epic #1237) — the water-flow view. It mounts the reusable
 * `FlowLayer` (GPU particle advection) over the real reach-network river centerlines,
 * mirroring `DispersionMap` / `CorridorMap` (DeckGL + `react-map-gl/maplibre`). client:only
 * over the page's SSR reach-attenuation table.
 *
 * The particles ride the `reach-network` geometry; density + speed encode each reach's routed
 * storm-peak magnitude (`routed-hydrograph`), and reaches whose receiving water fails its
 * low-flow assimilative screen (`hydrology-scenarios`) draw oxblood and thin — the join is the
 * server-computed `/feeds/flow.json` (`buildFlowReaches`). Motion is restrained per the design
 * doctrine; the storm-peak magnitude is a modeled screening read, so the page carries the
 * `[inference]` provenance banner and this island only draws the flow.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import DeckGL from "@deck.gl/react";
import type { Layer } from "@deck.gl/core";
import { Map } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { FlowReachView } from "@watermark/viz/flowModel";
import FlowLayer, { readFlowColors } from "./FlowLayer";
import { rasterTileLayer } from "./rasterTile";

const BASEMAPS: Record<string, string | null> = {
  esri: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  street: null, // the MapLibre vector basemap shows through
};

/** The lon/lat centroid of every reach vertex — recenters the camera on the network. */
function networkCenter(reaches: FlowReachView[]): [number, number] | null {
  let sx = 0;
  let sy = 0;
  let n = 0;
  for (const r of reaches) {
    for (const p of r.path) {
      sx += p[0];
      sy += p[1];
      n++;
    }
  }
  return n > 0 ? [sx / n, sy / n] : null;
}

export default function FlowMap({ src }: { src: string }): JSX.Element {
  const [reaches, setReaches] = useState<FlowReachView[] | null>(null);
  const [basemap, setBasemap] = useState<string>("esri");
  const [showChannels, setShowChannels] = useState(true);
  const [time, setTime] = useState(0);

  const colors = useMemo(() => readFlowColors(), []);

  useEffect(() => {
    let live = true;
    fetch(src)
      .then((r) => r.json())
      .then((d: FlowReachView[]) => {
        if (live) setReaches(Array.isArray(d) ? d : []);
      })
      .catch(() => {
        if (live) setReaches([]);
      });
    return () => {
      live = false;
    };
  }, [src]);

  // Advection clock: bump `time` (seconds) each frame so the FlowLayer's vertex shader advects.
  const startRef = useRef<number | null>(null);
  useEffect(() => {
    if (!reaches || reaches.length === 0) return;
    let raf = 0;
    const tick = (t: number) => {
      if (startRef.current == null) startRef.current = t;
      setTime((t - startRef.current) / 1000);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [reaches]);

  const [viewState, setViewState] = useState({
    longitude: -84.122,
    latitude: 40.792,
    zoom: 11,
    pitch: 0,
    bearing: 0,
  });
  const center = useMemo(() => (reaches ? networkCenter(reaches) : null), [reaches]);
  useEffect(() => {
    if (!center) return;
    setViewState((v) => ({ ...v, longitude: center[0], latitude: center[1] }));
  }, [center]);

  const layers = useMemo(() => {
    const out: Layer[] = [];
    const url = BASEMAPS[basemap];
    if (url) out.push(rasterTileLayer(url));
    if (reaches && reaches.length > 0) {
      out.push(
        new FlowLayer({
          id: "reach-flow",
          reaches,
          time,
          colors,
          showChannels,
          opacity: 1,
        }),
      );
    }
    return out;
  }, [reaches, basemap, showChannels, time, colors]);

  // Distinguish still-loading (`reaches === null`) from a loaded-but-empty network so the probe
  // doesn't claim "no deficit reaches" before the fetch resolves.
  const loading = reaches === null;
  const deficitCount = reaches?.filter((r) => r.deficit).length ?? 0;

  if (reaches && reaches.length === 0) {
    return (
      <div className="deck-surface deck-surface--empty">
        <p className="deck-loading">
          No reach-network geometry on the record for this site yet — the reach-attenuation table below
          carries the routed hydrograph.
        </p>
      </div>
    );
  }

  return (
    <div
      className="deck-surface"
      role="figure"
      aria-label="Interactive animated view of water advecting down the reach network (deck.gl); the routed per-reach attenuation is also listed as a table on this page."
    >
      <DeckGL
        viewState={viewState}
        onViewStateChange={(e) => setViewState(e.viewState as typeof viewState)}
        controller
        layers={layers}
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
        <strong>Channels</strong>
        <label>
          <input type="checkbox" checked={showChannels} onChange={(e) => setShowChannels(e.target.checked)} />{" "}
          reach centerlines
        </label>
      </div>

      <div className="deck-probe" aria-live="polite">
        <span className="deck-probe-label">Reach network · {reaches?.length ?? "—"} reaches</span>
        <span className="deck-probe-value">
          {loading
            ? "loading…"
            : deficitCount > 0
              ? `${deficitCount} deficit reach${deficitCount === 1 ? "" : "es"} (oxblood)`
              : "no deficit reaches"}
        </span>
        <span className="deck-probe-meta">density · speed = routed storm peak · [inference]</span>
      </div>
    </div>
  );
}
