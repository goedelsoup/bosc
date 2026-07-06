/**
 * SeasonalField island (#1236, epic #1237) — the Phase-2 water view. It mounts the reusable
 * `FieldLayer` (#1233) over the seasonal net-atmospheric-withdrawal climograph (`water-seasonal-field`
 * feed) as a **cartesian** month-axis strip in an `OrthographicView` (no basemap — the field is a
 * climatology, not a map). client:only over the page's SSR seasonal table.
 *
 * Field semantics (via FieldLayer's ramp/threshold tinting):
 *   - The scalar is net atmospheric withdrawal (reference ET0 − precip, mm/day): a bone→forest→ink
 *     ramp. Cited NASA POWER normals + FAO-56 ET0 → the climograph is `[reference]`.
 *   - `threshold = 0` → the deficit boundary (net = 0, where ET starts to exceed precipitation) is
 *     the load-bearing ink isopleth ("ET0 = precip"); deficit months (net > 0) also tint toward
 *     `--ev-inference` (the growing-season pinch).
 *   - `limit` is left null: the raster scalar is mm/day, so the low-flow *exceedance* read (the draw
 *     ÷ the cited seasonal low flow) is surfaced in the probe/SSR table — where cfs-vs-cfs is honest
 *     — not tinted onto the climate raster.
 *
 * The grid is width=12 (months, JAN→DEC), constant along a thin vertical extent (the climograph is a
 * 1-D annual cycle); `FieldLayer` bilinearly smooths across months and traces the net=0 isopleth as
 * a vertical hairline wherever the year crosses into deficit. The month switcher selects a column
 * (mirroring the air averaging-period switcher); hovering the field reads the month under the cursor.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import DeckGL from "@deck.gl/react";
import { type Layer, OrthographicView } from "@deck.gl/core";
import { LineLayer } from "@deck.gl/layers";
import type { SeasonalField as SeasonalFieldData } from "~/lib/feeds";
import type { FieldGrid } from "~/lib/field";
import FieldLayer, { readFieldColors } from "./FieldLayer";

// Grid geometry: 12 month columns, a thin 2-row band (the climograph is constant along y — the
// annual cycle is 1-D). Node i (month i) lives at world x = i; the band spans world y ∈ [0, 1].
const NX = 12;
const NY = 2;
// The world box the OrthographicView frames — the 0..11 month axis plus margins for the label row.
const X0 = -0.7;
const X1 = 11.7;
const Y0 = -0.5;
const Y1 = 1.9;

const MONTHS_SHORT = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

/** Build the cartesian climograph grid: every row carries the month's net-atmospheric value. */
function toGrid(field: SeasonalFieldData): FieldGrid | null {
  if (field.months.length !== NX) return null;
  const values = new Float32Array(NX * NY);
  for (let row = 0; row < NY; row++) {
    for (let col = 0; col < NX; col++) {
      values[row * NX + col] = field.months[col].net_atmospheric_mm_day;
    }
  }
  return { width: NX, height: NY, values }; // no `bounds` → cartesian (OrthographicView) field
}

interface ViewState {
  target: [number, number, number];
  zoom: [number, number];
}

/** Zoom that fits the world box [X0,X1]×[Y0,Y1] into a `w`×`h` pixel canvas (independent x/y). */
function fitView(w: number, h: number): ViewState {
  const zx = Math.log2(Math.max(w, 1) / (X1 - X0));
  const zy = Math.log2(Math.max(h, 1) / (Y1 - Y0));
  return { target: [(X0 + X1) / 2, (Y0 + Y1) / 2, 0], zoom: [zx, zy] };
}

export default function SeasonalField({ src }: { src: string }): JSX.Element {
  const [field, setField] = useState<SeasonalFieldData | null | undefined>(undefined);
  const [monthIdx, setMonthIdx] = useState(6); // default JUL — the peak-deficit month
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [view, setView] = useState<ViewState>(() => fitView(720, 200));
  const wrapRef = useRef<HTMLDivElement>(null);

  const colors = useMemo(() => readFieldColors(), []);

  useEffect(() => {
    let live = true;
    fetch(src)
      .then((r) => r.json())
      .then((d: SeasonalFieldData | null) => {
        if (live) setField(d);
      })
      .catch(() => {
        if (live) setField(null);
      });
    return () => {
      live = false;
    };
  }, [src]);

  // Refit the orthographic view to the canvas whenever it resizes (responsive strip).
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect;
      if (box && box.width > 0 && box.height > 0) setView(fitView(box.width, box.height));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const grid = useMemo(() => (field?.available ? toGrid(field) : null), [field]);

  const layers = useMemo(() => {
    const out: Layer[] = [];
    if (grid) {
      out.push(
        new FieldLayer({
          id: "seasonal-field",
          data: grid,
          threshold: 0, // net = 0: the deficit boundary (ET0 = precip)
          thresholdLabel: "ET0 = precip",
          showIsopleths: true,
          colors,
          opacity: 1,
        }),
      );
      // The selected month, marked as a vertical hairline across the band.
      out.push(
        new LineLayer({
          id: "month-marker",
          data: [{ x: monthIdx }],
          coordinateSystem: "cartesian",
          getSourcePosition: (d: { x: number }) => [d.x, Y0 + 0.2],
          getTargetPosition: (d: { x: number }) => [d.x, 1.2],
          getColor: [...colors.tintInference, 235] as [number, number, number, number],
          getWidth: 2,
          widthUnits: "pixels",
        }),
      );
    }
    return out;
  }, [grid, monthIdx, colors]);

  // Loading / locked / degraded states.
  if (field === undefined) {
    return (
      <div className="deck-surface deck-surface--empty">
        <p className="deck-loading">Loading the seasonal field…</p>
      </div>
    );
  }
  if (!field?.available || field.months.length === 0) {
    return (
      <div className="deck-surface deck-surface--empty">
        <p className="deck-loading">
          No seasonal withdrawal climograph is on the record for this site yet — the seasonal table below
          carries what the cited climate normals and low flows support.
        </p>
      </div>
    );
  }

  const active = field.months[hoverIdx ?? monthIdx];
  const exceeds = active.multiple != null && active.multiple > 1;

  return (
    <div
      className="seasonal-figure"
      role="figure"
      aria-label="Interactive seasonal net-atmospheric-withdrawal climograph (deck.gl); the same monthly figures are also listed as a table on this page."
    >
      <div className="deck-surface deck-surface--strip">
        <div ref={wrapRef} className="deck-canvas-wrap">
          <DeckGL
            views={new OrthographicView({ id: "ortho", flipY: true, controller: false })}
            viewState={view}
            controller={false}
            layers={layers}
            getCursor={() => "crosshair"}
            onHover={({ coordinate }) => {
              if (!coordinate) return setHoverIdx(null);
              const i = Math.round(coordinate[0]);
              setHoverIdx(i >= 0 && i < NX ? i : null);
            }}
          />
        </div>

        <div className="deck-probe" aria-live="polite">
          <span className="deck-probe-label">{active.month}</span>
          <span className="deck-probe-value">
            {active.net_atmospheric_mm_day > 0 ? "+" : ""}
            {active.net_atmospheric_mm_day.toFixed(2)} mm/day net · ET0 {active.et0_mm_day.toFixed(2)} /
            precip {active.precip_mm_day.toFixed(2)}
          </span>
          <span className="deck-probe-meta">
            draw {active.consumptive_cfs.toFixed(2)} cfs ÷ {active.low_flow_cfs}
            {" cfs "}({active.low_flow_basis}) = {active.multiple == null ? "—" : `${active.multiple}×`}
            {" · "}
            <span className={exceeds ? "ev-tag ev-tag--gap" : "ev-tag ev-tag--inference"}>
              {exceeds ? "over low flow" : "under low flow"}
            </span>{" "}
            [inference]
          </span>
        </div>
      </div>

      <div className="month-switcher" role="group" aria-label="Select month">
        {MONTHS_SHORT.map((m, i) => (
          <button
            type="button"
            key={m}
            className={`month-chip${i === monthIdx ? " is-active" : ""}${
              field.months[i].growing_season ? " is-growing" : ""
            }`}
            aria-pressed={i === monthIdx}
            onClick={() => setMonthIdx(i)}
          >
            {m}
          </button>
        ))}
      </div>

      <p className="seasonal-note">
        The ink hairline is the deficit boundary (ET0 = precip). Shaded months (
        {field.growing_season_months.join(", ")}) run a growing-season deficit — reference ET exceeds
        precipitation, so the cooling draw is read against the tighter summer 30Q10 with no rainfall buffer.
        The climograph is cited climate normals <em>[reference]</em>; the low-flow multiple screens the
        modeled buildout draw <em>[inference]</em>.
      </p>
    </div>
  );
}
