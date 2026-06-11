/**
 * A deck.gl raster basemap layer from an XYZ tile-URL template — shared by the
 * map islands (corridor map #71, imagery slider #72). Client-only: it imports
 * deck.gl, so it must never be pulled into an SSR/`.astro` module.
 *
 * The URL template carries `{z}/{x}/{y}` placeholders (Esri Wayback uses
 * `{z}/{y}/{x}` order — deck substitutes each by name regardless of path order).
 */
import { BitmapLayer } from "@deck.gl/layers";
import { TileLayer } from "@deck.gl/geo-layers";

export function rasterTileLayer(url: string, id = `basemap-${url}`): TileLayer {
  return new TileLayer({
    id,
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
