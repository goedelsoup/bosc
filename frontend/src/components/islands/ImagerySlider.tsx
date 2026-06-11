/**
 * Imagery before/during/after slider island (issue #72). A deck.gl map over the
 * campus AOI whose aerial basemap flips between dated Esri **Wayback** releases as
 * the time slider scrubs — the land before, during, and after the data-center
 * buildout. The dated ladder and the AOI footprint come from the `geo/imagery`
 * feed (its `meta.wayback`); the tiles load view-only from Esri. Mounted
 * `client:only` over the page's server-rendered fallback (the dated list).
 */
import { useEffect, useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import type { Layer } from "@deck.gl/core";
import { GeoJsonLayer } from "@deck.gl/layers";
import { Map } from "react-map-gl/maplibre";
import type { FeatureCollection } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
import { rasterTileLayer } from "./rasterTile";
import type { ImageryFeed, WaybackRelease } from "../../lib/feeds";

// The committed AOI centroid; also the fallback when no bbox is read from the feed.
const FALLBACK_VIEW = { longitude: -84.1234, latitude: 40.7969, zoom: 13.2, pitch: 0, bearing: 0 };

function viewForBbox(bbox: number[] | undefined): typeof FALLBACK_VIEW {
  if (!bbox || bbox.length !== 4) return FALLBACK_VIEW;
  const [minx, miny, maxx, maxy] = bbox;
  return { ...FALLBACK_VIEW, longitude: (minx + maxx) / 2, latitude: (miny + maxy) / 2 };
}

export default function ImagerySlider({ src }: { src: string }): JSX.Element {
  const [feed, setFeed] = useState<ImageryFeed | null>(null);
  const [i, setI] = useState(0);

  useEffect(() => {
    let live = true;
    fetch(src)
      .then((r) => r.json())
      .then((d: ImageryFeed) => {
        if (live) setFeed(d);
      })
      .catch(() => setFeed({ type: "FeatureCollection", features: [] }));
    return () => {
      live = false;
    };
  }, [src]);

  const releases: WaybackRelease[] = feed?.meta?.wayback?.releases ?? [];
  const template = feed?.meta?.wayback?.tile_url_template ?? "";
  const aoi = feed?.features ?? [];
  const view = useMemo(() => viewForBbox(aoi[0]?.properties?.bbox), [feed]);
  const idx = Math.min(i, Math.max(0, releases.length - 1));
  const current: WaybackRelease | undefined = releases[idx];

  const layers = useMemo(() => {
    const out: Layer[] = [];
    if (current && template) {
      const url = template.replace("{release}", String(current.release));
      out.push(rasterTileLayer(url, `wayback-${current.release}`));
    }
    if (aoi.length) {
      const data = { type: "FeatureCollection", features: aoi } as unknown as FeatureCollection;
      out.push(
        new GeoJsonLayer({
          id: "imagery-aoi",
          data,
          stroked: true,
          filled: false,
          getLineColor: [255, 213, 79, 255],
          lineWidthUnits: "pixels",
          getLineWidth: 2,
        }),
      );
    }
    return out;
  }, [feed, idx]);

  if (feed && releases.length === 0) {
    return <div className="slider slider-empty">No dated imagery in this bundle yet.</div>;
  }

  return (
    <div className="deck-surface">
      <DeckGL initialViewState={view} controller layers={layers}>
        <Map mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json" />
      </DeckGL>

      <div className="deck-controls imagery-scrubber">
        <strong>Aerial date — before / during / after</strong>
        <input
          type="range"
          min={0}
          max={Math.max(0, releases.length - 1)}
          value={idx}
          aria-label="Scrub aerial date"
          onChange={(e) => setI(Number(e.target.value))}
        />
        <div className="scrubber-date">
          {current ? current.date : "—"}{" "}
          <span className="card-meta">
            ({idx + 1} / {releases.length})
          </span>
        </div>
        <small className="card-meta">{feed?.meta?.wayback?.attribution ?? "Imagery © Esri"}</small>
      </div>
    </div>
  );
}
