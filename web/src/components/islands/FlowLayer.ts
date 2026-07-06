/**
 * FlowLayer (#1235, epic #1237) — a reusable deck.gl layer that advects instanced GPU
 * particles down a river reach network, encoding flow magnitude as particle density + speed
 * and drawing deficit reaches (consumptive draw > supply) in oxblood. The water-side peer of
 * `FieldLayer`; driven by the `reach-network` geometry feed joined to `routed-hydrograph`
 * (magnitude) and `hydrology-scenarios` (deficit) in the `FlowMap` island.
 *
 * Two parts:
 *   - `FlowParticleLayer` — a bare luma `Model` of instanced billboard quads. Each reach's
 *     centerline is re-sampled to a fixed `K` evenly-spaced vertices (via the tested
 *     `lib/flow.resamplePath`) and packed into one row of an RGBA32F **position texture**. A
 *     particle instance carries only its reach row + a phase/speed/alpha/color; the *vertex
 *     shader* advects it — `s = fract(phase + time·speed)` indexes the row and lerps two
 *     texels to a lon/lat, so the advection runs entirely on the GPU (no per-frame CPU work,
 *     no path data in the instance buffer). Motion is restrained (slow, no bounce; particles
 *     fade at the wrap seam rather than popping) per the design doctrine.
 *   - `FlowLayer` — a `CompositeLayer` that draws the faint reach centerlines (a `PathLayer`,
 *     forest hairline; oxblood for deficit reaches) under the particles.
 *
 * Colors resolve from `design/tokens/colors.css` at mount (`readFlowColors`) — indigo/forest
 * is the one data signal; oxblood (`--ev-gap`) is spent only where a regulatory floor (a
 * deficit reach) is crossed. Client-only (imports deck.gl/luma.gl) — never in an SSR module.
 */
import { CompositeLayer, Layer, type UpdateParameters } from "@deck.gl/core";
import { project32 } from "@deck.gl/core";
import { PathLayer } from "@deck.gl/layers";
import { Model } from "@luma.gl/engine";
import type { Texture } from "@luma.gl/core";
import { type FlowReach, particleCount, resamplePath } from "~/lib/flow";

/** Vertices each reach centerline is re-sampled to (one texture column per vertex). */
const RESAMPLE_K = 64;
/** Particle billboard radius, in pixels. */
const POINT_RADIUS_PX = 2.2;
/** Particles a full-density reach carries (deficit reaches are thinned by `particleCount`). */
const MAX_PARTICLES_PER_REACH = 44;

export type RGB = [number, number, number];

/** RGB (0–255) design-token colors the flow is drawn with. */
export interface FlowColors {
  /** The flowing water / particle signal — `--forest`. */
  flow: RGB;
  /** Deficit reaches (draw > supply) — `--ev-gap-fg` (oxblood). */
  deficit: RGB;
}

/** Token fallbacks (from `design/tokens/colors.css`) when the DOM isn't readable. */
export const DEFAULT_FLOW_COLORS: FlowColors = {
  flow: [31, 111, 74], // --forest
  deficit: [122, 34, 48], // --ev-gap-fg
};

function parseColor(raw: string): RGB | null {
  const s = raw.trim();
  const hex = s.replace("#", "");
  if (/^[0-9a-f]{6}$/i.test(hex)) {
    const n = Number.parseInt(hex, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  if (/^[0-9a-f]{3}$/i.test(hex)) {
    const n = Number.parseInt(hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2], 16);
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
 * Resolve the flow palette from `design/tokens/colors.css` custom properties on `el`
 * (defaults to `document.documentElement`), falling back per-token to
 * {@link DEFAULT_FLOW_COLORS} when a variable is unset or unreadable (SSR).
 */
export function readFlowColors(el?: Element): FlowColors {
  if (typeof window === "undefined" || typeof getComputedStyle === "undefined") {
    return DEFAULT_FLOW_COLORS;
  }
  const cs = getComputedStyle(el ?? document.documentElement);
  const pick = (name: string, fallback: RGB): RGB => parseColor(cs.getPropertyValue(name)) ?? fallback;
  return {
    flow: pick("--forest", DEFAULT_FLOW_COLORS.flow),
    deficit: pick("--ev-gap-fg", DEFAULT_FLOW_COLORS.deficit),
  };
}

const unit = (c: RGB): [number, number, number] => [c[0] / 255, c[1] / 255, c[2] / 255];

// --- GPU particle sublayer --------------------------------------------------

/** `flow` shader-module UBO — the advection clock + billboard/texture geometry. */
const flowUniformBlock = `\
layout(std140) uniform flowUniforms {
  float time;
  float texWidth;
  float pointRadius;
  float baseAlpha;
} flow;
`;

const flowUniforms = {
  name: "flow",
  vs: flowUniformBlock,
  fs: flowUniformBlock,
  uniformTypes: {
    time: "f32",
    texWidth: "f32",
    pointRadius: "f32",
    baseAlpha: "f32",
  },
} as const;

const FLOW_VERTEX_SHADER = `\
#version 300 es
#define SHADER_NAME flow-particle-vertex-shader

in vec3 positions;          // unit billboard corner, xy in [-1, 1]
in float instanceRow;       // this particle's reach row in the position texture
in float instancePhase;     // start offset along the reach, [0, 1)
in float instanceSpeed;     // advection speed (fraction of reach per second)
in float instanceAlpha;     // per-particle opacity
in vec3 instanceColor;      // rgb (0–1) — forest, or oxblood on a deficit reach

uniform sampler2D posTexture;

out vec2 unitPos;
out vec4 vColor;

// The lon/lat at arc-length fraction s along a reach row (texels are evenly spaced).
vec2 sampleReach(int row, float s) {
  float fx = clamp(s, 0.0, 1.0) * (flow.texWidth - 1.0);
  int i0 = int(floor(fx));
  int i1 = min(i0 + 1, int(flow.texWidth) - 1);
  vec2 p0 = texelFetch(posTexture, ivec2(i0, row), 0).xy;
  vec2 p1 = texelFetch(posTexture, ivec2(i1, row), 0).xy;
  return mix(p0, p1, fract(fx));
}

void main(void) {
  float s = fract(instancePhase + flow.time * instanceSpeed);
  vec2 lonlat = sampleReach(int(instanceRow), s);
  vec3 pos = vec3(lonlat, 0.0);
  geometry.worldPosition = pos;

  vec4 clip = project_position_to_clipspace(pos, vec3(0.0), vec3(0.0), geometry.position);
  vec2 offset = positions.xy * flow.pointRadius;
  clip.xy += project_pixel_size_to_clipspace(offset);
  gl_Position = clip;

  unitPos = positions.xy;
  // Fade in/out at the reach ends so a wrapping particle doesn't pop.
  float edge = smoothstep(0.0, 0.06, s) * (1.0 - smoothstep(0.94, 1.0, s));
  vColor = vec4(instanceColor, instanceAlpha * flow.baseAlpha * edge);
}
`;

const FLOW_FRAGMENT_SHADER = `\
#version 300 es
#define SHADER_NAME flow-particle-fragment-shader
precision highp float;

in vec2 unitPos;
in vec4 vColor;
out vec4 fragColor;

void main(void) {
  float d = length(unitPos);
  if (d > 1.0) discard;
  float a = vColor.a * smoothstep(1.0, 0.55, d); // soft round particle
  fragColor = vec4(vColor.rgb, a);
}
`;

interface ParticleBuffers {
  count: number;
  rows: Float32Array;
  phases: Float32Array;
  speeds: Float32Array;
  alphas: Float32Array;
  colors: Float32Array;
}

/** Build the per-particle instance arrays from the reaches (density → count, magnitude → speed). */
function buildParticles(reaches: FlowReach[], colors: FlowColors): ParticleBuffers {
  const rows: number[] = [];
  const phases: number[] = [];
  const speeds: number[] = [];
  const alphas: number[] = [];
  const cols: number[] = [];
  reaches.forEach((reach, row) => {
    const n = particleCount(reach, MAX_PARTICLES_PER_REACH);
    const color = unit(reach.deficit ? colors.deficit : colors.flow);
    // Restrained motion: a slow base rate scaled by the reach's normalized speed.
    const speed = 0.04 + 0.06 * reach.speed;
    for (let i = 0; i < n; i++) {
      rows.push(row);
      phases.push((i + 0.5) / n); // evenly spread so the stream reads continuous
      speeds.push(speed);
      alphas.push(reach.deficit ? 0.5 : 0.85);
      cols.push(color[0], color[1], color[2]);
    }
  });
  return {
    count: rows.length,
    rows: new Float32Array(rows),
    phases: new Float32Array(phases),
    speeds: new Float32Array(speeds),
    alphas: new Float32Array(alphas),
    colors: new Float32Array(cols),
  };
}

/** Pack every reach's re-sampled centerline into one RGBA32F row (lon, lat, 0, 1). */
function buildPositionTexture(reaches: FlowReach[]): Float32Array {
  const data = new Float32Array(RESAMPLE_K * Math.max(1, reaches.length) * 4);
  reaches.forEach((reach, row) => {
    const pts = resamplePath(reach.path, RESAMPLE_K);
    for (let col = 0; col < RESAMPLE_K; col++) {
      const p = pts[col] ?? pts.at(-1) ?? [0, 0];
      const o = (row * RESAMPLE_K + col) * 4;
      data[o] = p[0];
      data[o + 1] = p[1];
      data[o + 2] = 0;
      data[o + 3] = 1;
    }
  });
  return data;
}

type FlowParticleProps = {
  id?: string;
  reaches: FlowReach[];
  colors: FlowColors;
  time: number;
  opacity?: number;
};

/** A bare instanced-billboard `Model` that advects particles along the position texture. */
class FlowParticleLayer extends Layer<FlowParticleProps> {
  static override layerName = "FlowParticleLayer";

  declare state: {
    model?: Model;
    posTexture?: Texture;
    count: number;
  };

  override initializeState(): void {
    this.state = { count: 0 };
  }

  override updateState(params: UpdateParameters<this>): void {
    const { props, oldProps, changeFlags } = params;
    // `time` ticks every frame but doesn't touch the geometry/instances — only rebuild the
    // (expensive) model + texture when the reaches or the palette actually change.
    if (changeFlags.dataChanged || props.reaches !== oldProps.reaches || props.colors !== oldProps.colors) {
      this.state.model?.destroy();
      this.state.posTexture?.destroy();
      this._build();
    }
  }

  override finalizeState(): void {
    this.state.model?.destroy();
    this.state.posTexture?.destroy();
  }

  private _build(): void {
    const { reaches, colors } = this.props;
    const device = this.context.device;
    const p = buildParticles(reaches, colors);
    this.state.count = p.count;
    if (p.count === 0) {
      this.state.model = undefined;
      return;
    }
    this.state.posTexture = device.createTexture({
      format: "rgba32float",
      width: RESAMPLE_K,
      height: Math.max(1, reaches.length),
      data: buildPositionTexture(reaches),
      mipLevels: 1,
      sampler: { minFilter: "nearest", magFilter: "nearest" },
    });
    // A unit quad (two triangles) instanced once per particle.
    const quad = new Float32Array([-1, -1, 0, 1, -1, 0, -1, 1, 0, -1, 1, 0, 1, -1, 0, 1, 1, 0]);
    const model = new Model(device, {
      id: `${this.props.id}-model`,
      vs: FLOW_VERTEX_SHADER,
      fs: FLOW_FRAGMENT_SHADER,
      modules: [project32, flowUniforms],
      bufferLayout: [
        { name: "positions", format: "float32x3" },
        { name: "instanceRow", format: "float32", stepMode: "instance" },
        { name: "instancePhase", format: "float32", stepMode: "instance" },
        { name: "instanceSpeed", format: "float32", stepMode: "instance" },
        { name: "instanceAlpha", format: "float32", stepMode: "instance" },
        { name: "instanceColor", format: "float32x3", stepMode: "instance" },
      ],
      attributes: {
        positions: device.createBuffer({ data: quad }),
        instanceRow: device.createBuffer({ data: p.rows }),
        instancePhase: device.createBuffer({ data: p.phases }),
        instanceSpeed: device.createBuffer({ data: p.speeds }),
        instanceAlpha: device.createBuffer({ data: p.alphas }),
        instanceColor: device.createBuffer({ data: p.colors }),
      },
      vertexCount: 6,
      instanceCount: p.count,
      parameters: { depthCompare: "always", blend: true },
      isInstanced: true,
    });
    this.state.model = model;
  }

  override draw(): void {
    const { model, posTexture } = this.state;
    if (!model || !posTexture) return;
    model.setBindings({ posTexture });
    model.shaderInputs.setProps({
      flow: {
        time: this.props.time,
        texWidth: RESAMPLE_K,
        pointRadius: POINT_RADIUS_PX,
        baseAlpha: this.props.opacity ?? 1,
      },
    });
    model.draw(this.context.renderPass);
  }
}

// --- Public composite layer -------------------------------------------------

export type FlowLayerProps = {
  id?: string;
  /** The reaches to advect over — centerline geometry + normalized flow encodings. */
  reaches: FlowReach[];
  /** Animation clock, in seconds (the island bumps it via requestAnimationFrame). */
  time: number;
  /** Palette (resolve via {@link readFlowColors}); defaults to token fallbacks. */
  colors?: FlowColors;
  /** Overall opacity forwarded to particles + centerlines. */
  opacity?: number;
  /** Draw the faint reach centerlines under the particles (default true). */
  showChannels?: boolean;
};

export default class FlowLayer extends CompositeLayer<FlowLayerProps> {
  static override layerName = "FlowLayer";

  declare state: { valid: FlowReach[] };

  override initializeState(): void {
    this.state = { valid: [] };
  }

  override updateState(params: UpdateParameters<this>): void {
    const { props, oldProps } = params;
    // Cache the filtered reaches so the reference is stable across `time` ticks — otherwise a
    // fresh array every frame makes FlowParticleLayer think `reaches` changed and rebuild.
    if (props.reaches !== oldProps.reaches) {
      this.setState({ valid: props.reaches.filter((r) => r.path.length >= 2) });
    }
  }

  renderLayers(): Layer[] {
    const { time } = this.props;
    const colors = this.props.colors ?? DEFAULT_FLOW_COLORS;
    const opacity = this.props.opacity ?? 1;
    const valid = this.state.valid;
    if (valid.length === 0) return [];

    const layers: Layer[] = [];

    // The reach centerlines — a faint channel bed the particles ride (oxblood on deficit).
    if (this.props.showChannels !== false) {
      layers.push(
        new PathLayer<FlowReach>(this.getSubLayerProps({ id: "channels" }) as object, {
          data: valid,
          getPath: (r: FlowReach) => r.path,
          getColor: (r: FlowReach) =>
            [...(r.deficit ? colors.deficit : colors.flow), r.deficit ? 150 : 70] as [
              number,
              number,
              number,
              number,
            ],
          getWidth: (r: FlowReach) => (r.deficit ? 2 : 1.25),
          widthUnits: "pixels",
          capRounded: true,
          jointRounded: true,
          opacity,
          pickable: false,
        }),
      );
    }

    layers.push(
      new FlowParticleLayer(this.getSubLayerProps({ id: "particles" }) as object, {
        reaches: valid,
        colors,
        time,
        opacity,
      }),
    );

    return layers;
  }
}
