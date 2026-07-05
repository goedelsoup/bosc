/**
 * FieldLayer (#1233, epic #1237) — a reusable deck.gl layer that renders a
 * continuous scalar field as a GPU raster with ink-hairline isopleths. Shared by
 * the air dispersion field (#1234) and the Phase-2 water evaporation/withdrawal
 * surface (#1236).
 *
 * Two parts:
 *   - `FieldRasterLayer` — a `BitmapLayer` subclass whose fragment shader uploads
 *     the grid as an R32F float texture, bilinearly interpolates it per-fragment,
 *     and maps value → color through the bone→forest→ink luminance ramp. Cells
 *     above `threshold` tint toward `--ev-inference`; above an optional regulatory
 *     `limit` toward `--ev-gap` (amber/oxblood only where a limit is crossed).
 *   - `FieldLayer` — a `CompositeLayer` that stacks the raster, the light interior
 *     isopleths, and the load-bearing `threshold` isopleth (a heavier ink hairline
 *     with a mono label), all derived from the tested helpers in `lib/field.ts`.
 *
 * Colors are never hardcoded: `readFieldColors()` resolves them from the
 * `design/tokens/colors.css` custom properties at mount and they flow in as the
 * `colors` prop (→ shader uniforms). The layer geo-references onto the
 * `rasterTileLayer` basemap when `bounds` are present, else lives in a bare
 * cartesian (OrthographicView) space.
 *
 * Client-only: it imports deck.gl/luma.gl, so it must never be pulled into an
 * SSR/`.astro` module.
 */
import { CompositeLayer, type CoordinateSystem, type Layer, type UpdateParameters } from "@deck.gl/core";
import { BitmapLayer, LineLayer, TextLayer } from "@deck.gl/layers";
import type { Device, Texture } from "@luma.gl/core";
import {
  contourLevels,
  type FieldGrid,
  marchingSquares,
  type RGB,
  segmentToWorld,
  valueExtent,
} from "~/lib/field";

/** Value written into the float texture for a no-data (`NaN`) cell; discarded in-shader. */
const NO_DATA_SENTINEL = -1e30;
/** Default number of interior (non-threshold) isopleths. */
const DEFAULT_ISOPLETHS = 4;

/** RGB (0–255) design-token colors the field is drawn with. */
export interface FieldColors {
  /** Ramp low end — bone/paper. */
  rampLow: RGB;
  /** Ramp midpoint — forest. */
  rampMid: RGB;
  /** Ramp high end — ink. */
  rampHigh: RGB;
  /** Tint applied above `threshold` — `--ev-inference`. */
  tintInference: RGB;
  /** Tint applied above `limit` — `--ev-gap`. */
  tintGap: RGB;
  /** Isopleth hairline ink. */
  isopleth: RGB;
}

/** Token fallbacks (from `design/tokens/colors.css`) when the DOM isn't readable. */
export const DEFAULT_FIELD_COLORS: FieldColors = {
  rampLow: [245, 242, 234], // --bone-surface
  rampMid: [31, 111, 74], // --forest
  rampHigh: [22, 32, 26], // --ink
  tintInference: [154, 106, 20], // --ev-inference-fg
  tintGap: [122, 34, 48], // --ev-gap-fg
  isopleth: [22, 32, 26], // --ink
};

// --- CSS-variable resolution ------------------------------------------------

function parseColor(raw: string): RGB | null {
  const s = raw.trim();
  const hex = s.replace("#", "");
  if (/^[0-9a-f]{6}$/i.test(hex)) {
    const n = Number.parseInt(hex, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  if (/^[0-9a-f]{3}$/i.test(hex)) {
    const r = hex[0];
    const g = hex[1];
    const b = hex[2];
    const n = Number.parseInt(r + r + g + g + b + b, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  const m = s.match(/rgba?\(([^)]+)\)/i);
  if (m) {
    const parts = m[1].split(/[\s,/]+/).map(Number);
    if (parts.length >= 3 && parts.slice(0, 3).every((v) => !Number.isNaN(v))) {
      return [parts[0], parts[1], parts[2]];
    }
  }
  return null;
}

/**
 * Resolve the field palette from `design/tokens/colors.css` custom properties on
 * `el` (defaults to `document.documentElement`). Falls back to
 * {@link DEFAULT_FIELD_COLORS} per-token when a variable is unset or unreadable
 * (e.g. during SSR).
 */
export function readFieldColors(el?: Element): FieldColors {
  if (typeof window === "undefined" || typeof getComputedStyle === "undefined") {
    return DEFAULT_FIELD_COLORS;
  }
  const cs = getComputedStyle(el ?? document.documentElement);
  const pick = (varName: string, fallback: RGB): RGB => parseColor(cs.getPropertyValue(varName)) ?? fallback;
  return {
    rampLow: pick("--bone-surface", DEFAULT_FIELD_COLORS.rampLow),
    rampMid: pick("--forest", DEFAULT_FIELD_COLORS.rampMid),
    rampHigh: pick("--ink", DEFAULT_FIELD_COLORS.rampHigh),
    tintInference: pick("--ev-inference-fg", DEFAULT_FIELD_COLORS.tintInference),
    tintGap: pick("--ev-gap-fg", DEFAULT_FIELD_COLORS.tintGap),
    isopleth: pick("--ink", DEFAULT_FIELD_COLORS.isopleth),
  };
}

const unit = (c: RGB): [number, number, number] => [c[0] / 255, c[1] / 255, c[2] / 255];

// --- GPU raster sublayer ----------------------------------------------------

/** `field` shader-module UBO — the ramp/threshold state the fragment shader reads. */
const fieldUniformBlock = `\
layout(std140) uniform fieldUniforms {
  vec2 gridSize;
  vec2 valueRange;
  float threshold;
  float limit;
  float hasLimit;
  float noData;
  float fieldOpacity;
  vec3 rampLow;
  vec3 rampMid;
  vec3 rampHigh;
  vec3 tintInference;
  vec3 tintGap;
} field;
`;

const fieldUniforms = {
  name: "field",
  vs: fieldUniformBlock,
  fs: fieldUniformBlock,
  uniformTypes: {
    gridSize: "vec2<f32>",
    valueRange: "vec2<f32>",
    threshold: "f32",
    limit: "f32",
    hasLimit: "f32",
    noData: "f32",
    fieldOpacity: "f32",
    rampLow: "vec3<f32>",
    rampMid: "vec3<f32>",
    rampHigh: "vec3<f32>",
    tintInference: "vec3<f32>",
    tintGap: "vec3<f32>",
  },
} as const;

// Reuses BitmapLayer's vertex shader (vTexCoord/vTexPos) and `bitmap` UBO (bounds +
// coordinateConversion) for the geo/cartesian UV; only the fragment stage changes.
const FIELD_FRAGMENT_SHADER = `\
#version 300 es
#define SHADER_NAME field-raster-fragment-shader
#ifdef GL_ES
precision highp float;
#endif

uniform sampler2D bitmapTexture;

in vec2 vTexCoord;
in vec2 vTexPos;

out vec4 fragColor;

/* projection utils (mirrors bitmap-layer-fragment) */
const float TILE_SIZE = 512.0;
const float PI = 3.1415926536;
const float WORLD_SCALE = TILE_SIZE / PI / 2.0;

vec2 lnglat_to_mercator(vec2 lnglat) {
  float x = lnglat.x;
  float y = clamp(lnglat.y, -89.9, 89.9);
  return vec2(radians(x) + PI, PI + log(tan(PI * 0.25 + radians(y) * 0.5))) * WORLD_SCALE;
}
vec2 mercator_to_lnglat(vec2 xy) {
  xy /= WORLD_SCALE;
  return degrees(vec2(xy.x - PI, atan(exp(xy.y - PI)) * 2.0 - PI * 0.5));
}
vec2 getUV(vec2 pos) {
  return vec2(
    (pos.x - bitmap.bounds[0]) / (bitmap.bounds[2] - bitmap.bounds[0]),
    (pos.y - bitmap.bounds[3]) / (bitmap.bounds[1] - bitmap.bounds[3])
  );
}

float texelValue(ivec2 p, ivec2 sz) {
  return texelFetch(bitmapTexture, clamp(p, ivec2(0), sz - 1), 0).r;
}

void main(void) {
  vec2 uv = vTexCoord;
  if (bitmap.coordinateConversion < -0.5) {
    uv = getUV(mercator_to_lnglat(vTexPos));
  } else if (bitmap.coordinateConversion > 0.5) {
    uv = getUV(lnglat_to_mercator(vTexPos));
  }

  // Bilinear interpolation across the four surrounding texels (centers at +0.5).
  ivec2 sz = ivec2(field.gridSize);
  vec2 p = uv * field.gridSize - 0.5;
  vec2 f = fract(p);
  ivec2 i0 = ivec2(floor(p));
  float v00 = texelValue(i0, sz);
  float v10 = texelValue(i0 + ivec2(1, 0), sz);
  float v01 = texelValue(i0 + ivec2(0, 1), sz);
  float v11 = texelValue(i0 + ivec2(1, 1), sz);
  if (v00 <= field.noData || v10 <= field.noData || v01 <= field.noData || v11 <= field.noData) {
    discard;
  }
  float value = mix(mix(v00, v10, f.x), mix(v01, v11, f.x), f.y);

  float span = max(field.valueRange.y - field.valueRange.x, 1e-6);
  float t = clamp((value - field.valueRange.x) / span, 0.0, 1.0);
  vec3 col = t < 0.5
    ? mix(field.rampLow, field.rampMid, t * 2.0)
    : mix(field.rampMid, field.rampHigh, (t - 0.5) * 2.0);

  if (value >= field.threshold) {
    col = mix(col, field.tintInference, 0.35);
  }
  if (field.hasLimit > 0.5 && value >= field.limit) {
    col = mix(col, field.tintGap, 0.5);
  }

  fragColor = vec4(col, field.fieldOpacity * layer.opacity);
  geometry.uv = uv;
  DECKGL_FILTER_COLOR(fragColor, geometry);
}
`;

type FieldRasterExtraProps = {
  grid: FieldGrid;
  valueRange: [number, number];
  threshold: number;
  limit: number | null;
  colors: FieldColors;
  fieldOpacity: number;
};

function buildFieldTexture(device: Device, grid: FieldGrid): Texture {
  const data = new Float32Array(grid.width * grid.height);
  for (let i = 0; i < data.length; i++) {
    const v = grid.values[i];
    data[i] = Number.isNaN(v) ? NO_DATA_SENTINEL : v;
  }
  return device.createTexture({
    format: "r32float",
    width: grid.width,
    height: grid.height,
    data,
    mipLevels: 1,
    sampler: { minFilter: "nearest", magFilter: "nearest" },
  });
}

/** BitmapLayer subclass that renders the scalar field from an R32F texture. */
class FieldRasterLayer extends BitmapLayer<FieldRasterExtraProps> {
  static override layerName = "FieldRasterLayer";
  static override defaultProps = {
    ...BitmapLayer.defaultProps,
    grid: { type: "object", value: null } as unknown as FieldGrid,
    valueRange: { type: "array", value: [0, 1] } as unknown as [number, number],
    threshold: { type: "number", value: Number.POSITIVE_INFINITY },
    limit: { type: "object", value: null } as unknown as number | null,
    colors: { type: "object", value: DEFAULT_FIELD_COLORS } as unknown as FieldColors,
    fieldOpacity: { type: "number", value: 0.82 },
  };

  declare state: BitmapLayer["state"] & { fieldTexture?: Texture };

  override getShaders() {
    const shaders = super.getShaders();
    return {
      ...shaders,
      fs: FIELD_FRAGMENT_SHADER,
      modules: [...shaders.modules, fieldUniforms],
    };
  }

  override updateState(params: UpdateParameters<this>): void {
    super.updateState(params);
    const { props, oldProps } = params;
    // Compare the underlying sample array, not the grid wrapper: FieldLayer.renderLayers
    // rebuilds a fresh `{...grid}` object every update, so an identity check on `grid`
    // would re-upload the texture on every frame even when the data is unchanged.
    if (!this.state.fieldTexture || props.grid.values !== oldProps.grid?.values) {
      this.state.fieldTexture?.destroy();
      this.state.fieldTexture = buildFieldTexture(this.context.device, props.grid);
    }
  }

  override finalizeState(context: UpdateParameters<this>["context"]): void {
    this.state.fieldTexture?.destroy();
    super.finalizeState(context);
  }

  override draw(): void {
    const { model, coordinateConversion, bounds, fieldTexture } = this.state;
    if (!model || !fieldTexture) return;
    const { grid, valueRange, threshold, limit, colors, fieldOpacity } = this.props;
    model.shaderInputs.setProps({
      bitmap: {
        bitmapTexture: fieldTexture,
        bounds,
        coordinateConversion,
        desaturate: 0,
        tintColor: [1, 1, 1],
        transparentColor: [0, 0, 0, 0],
      },
      field: {
        gridSize: [grid.width, grid.height],
        valueRange,
        threshold,
        limit: limit ?? 0,
        hasLimit: limit == null ? 0 : 1,
        noData: NO_DATA_SENTINEL,
        fieldOpacity,
        rampLow: unit(colors.rampLow),
        rampMid: unit(colors.rampMid),
        rampHigh: unit(colors.rampHigh),
        tintInference: unit(colors.tintInference),
        tintGap: unit(colors.tintGap),
      },
    });
    model.draw(this.context.renderPass);
  }
}

// --- Public composite layer -------------------------------------------------

export type FieldLayerProps = {
  id?: string;
  /** The scalar grid. Its own `bounds` geo-reference it unless `bounds` overrides. */
  data: FieldGrid;
  /** `[west, south, east, north]`; overrides `data.bounds`. Omit for a cartesian field. */
  bounds?: [number, number, number, number];
  /** The load-bearing isopleth level (e.g. a NAAQS / 7Q10 limit); also tints the raster. */
  threshold: number;
  /** Optional harder regulatory limit — cells above it tint toward `--ev-gap`. */
  limit?: number | null;
  /** Explicit interior isopleth levels; defaults to evenly spaced across the value range. */
  isopleths?: number[];
  /** Draw the interior isopleths (the threshold isopleth is always drawn). */
  showIsopleths?: boolean;
  /** Text label on the threshold isopleth (mono); omit to suppress. */
  thresholdLabel?: string;
  /** Palette (resolve via {@link readFieldColors}); defaults to token fallbacks. */
  colors?: FieldColors;
  /** Raster fill opacity (0–1). */
  fieldOpacity?: number;
  /** Overall layer opacity forwarded to sublayers. */
  opacity?: number;
  /** Fixed color scale `[min, max]`; defaults to the grid's value extent. */
  valueRange?: [number, number];
};

/** Two-point isoline record for the deck `LineLayer`. */
interface IsoSegment {
  source: [number, number];
  target: [number, number];
}

export default class FieldLayer extends CompositeLayer<FieldLayerProps> {
  static override layerName = "FieldLayer";

  renderLayers(): Layer[] {
    const props = this.props;
    const grid = props.data;
    if (!grid || grid.width < 2 || grid.height < 2) return [];

    const bounds = props.bounds ?? grid.bounds;
    const eff: FieldGrid = bounds ? { ...grid, bounds } : { ...grid, bounds: undefined };
    const geo = Boolean(bounds);
    const coordinateSystem: CoordinateSystem = geo ? "lnglat" : "cartesian";
    const [min, max] = props.valueRange ?? valueExtent(eff);
    const colors = props.colors ?? DEFAULT_FIELD_COLORS;
    const fieldOpacity = props.fieldOpacity ?? 0.82;

    // BitmapLayer quad in the field's coordinate space: geo → [W,S,E,N]; cartesian
    // → the grid index box with row 0 at the top (matches `gridToWorld`).
    const rasterBounds: [number, number, number, number] = geo
      ? (bounds as [number, number, number, number])
      : [0, eff.height - 1, eff.width - 1, 0];

    const layers: Layer[] = [
      new FieldRasterLayer(this.getSubLayerProps({ id: "raster" }) as object, {
        grid: eff,
        bounds: rasterBounds,
        valueRange: [min, max] as [number, number],
        threshold: props.threshold,
        limit: props.limit ?? null,
        colors,
        fieldOpacity,
        _imageCoordinateSystem: geo ? ("lnglat" as CoordinateSystem) : undefined,
        pickable: false,
      }),
    ];

    const toSegments = (level: number): IsoSegment[] =>
      marchingSquares(eff, level).map((seg) => {
        const [source, target] = segmentToWorld(eff, seg);
        return { source, target };
      });

    // Interior isopleths — faint ink hairlines.
    if (props.showIsopleths !== false) {
      const levels = props.isopleths ?? contourLevels(min, max, DEFAULT_ISOPLETHS);
      const interior = levels.filter((l) => l !== props.threshold).flatMap(toSegments);
      if (interior.length > 0) {
        layers.push(
          new LineLayer(this.getSubLayerProps({ id: "isopleths" }) as object, {
            data: interior,
            coordinateSystem,
            getSourcePosition: (d: IsoSegment) => d.source,
            getTargetPosition: (d: IsoSegment) => d.target,
            getColor: [...colors.isopleth, 90] as [number, number, number, number],
            getWidth: 1,
            widthUnits: "pixels",
          }),
        );
      }
    }

    // The load-bearing threshold isopleth — a heavier ink hairline.
    const thresholdSegs = toSegments(props.threshold);
    if (thresholdSegs.length > 0) {
      layers.push(
        new LineLayer(this.getSubLayerProps({ id: "threshold" }) as object, {
          data: thresholdSegs,
          coordinateSystem,
          getSourcePosition: (d: IsoSegment) => d.source,
          getTargetPosition: (d: IsoSegment) => d.target,
          getColor: [...colors.isopleth, 235] as [number, number, number, number],
          getWidth: 1.75,
          widthUnits: "pixels",
        }),
      );

      if (props.thresholdLabel) {
        // Anchor the mono label at the centroid of the threshold crossing points.
        let sx = 0;
        let sy = 0;
        for (const s of thresholdSegs) {
          sx += s.source[0] + s.target[0];
          sy += s.source[1] + s.target[1];
        }
        const n = thresholdSegs.length * 2;
        const anchor: [number, number] = [sx / n, sy / n];
        layers.push(
          new TextLayer(this.getSubLayerProps({ id: "threshold-label" }) as object, {
            data: [{ position: anchor, text: props.thresholdLabel }],
            coordinateSystem,
            getPosition: (d: { position: [number, number] }) => d.position,
            getText: (d: { text: string }) => d.text,
            getSize: 11,
            getColor: [...colors.isopleth, 255] as [number, number, number, number],
            fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
            fontWeight: 500,
            getTextAnchor: "middle",
            getAlignmentBaseline: "center",
            background: true,
            getBackgroundColor: [...colors.rampLow, 200] as [number, number, number, number],
            backgroundPadding: [4, 2, 4, 2],
          }),
        );
      }
    }

    return layers;
  }
}
