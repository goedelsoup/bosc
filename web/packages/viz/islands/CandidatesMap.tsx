/**
 * The international data-center candidates map (#1394, epic #1387).
 *
 * A world map of what open registers say is out there, drawn so that the *quality of the
 * evidence* is the thing you see first. Two encodings carry that, and they are kept strictly
 * apart, per the design system's rule that indigo encodes data and the evidence palette only
 * encodes evidence:
 *
 * - **Corroboration is the fill.** A candidate two independent registers agree on reads solid; a
 *   single-source lead reads hollow. That is a claim about evidence, so it uses the evidence
 *   palette — and it is deliberately the loudest difference on the map, because it is the only
 *   quality signal a priors-only sweep has.
 * - **Contested attribution is a ring.** Where the registers name *different* operators the point
 *   wears an oxblood ring, so a reader cannot pick up a name from this map without also picking
 *   up the fact that it is disputed.
 *
 * Nothing here is sized by capacity, load or footprint: the funnel cannot source any of those,
 * and a radius encoding invented from network counts would read as scale. Every point is the
 * same size. The one thing a point's position claims is a position.
 *
 * Mounted `client:only` over the page's SSR table, which carries the same rows as text.
 */
import { useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import type { Layer } from "@deck.gl/core";
import { ScatterplotLayer } from "@deck.gl/layers";
import { Map } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AoiSummary, Candidate, CandidatesRegister, PriorSource } from "@watermark/core/intlCandidates";
import { SOURCE_LABELS, aoiSummaries } from "@watermark/core/intlCandidates";

/** The evidence palette, as deck RGBA. Fixed values from the design system's `--ev-*` tokens —
 *  never recolored, and never used for anything that is not a statement about evidence. */
const EV_REFERENCE = [31, 111, 74] as const; // forest — the one signal colour
const EV_GAP = [122, 34, 48] as const; // oxblood — contested attribution
const INK = [26, 26, 26] as const;

const WORLD_VIEW = { longitude: 20, latitude: 25, zoom: 1.4, pitch: 0, bearing: 0 };
const BASEMAP = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

interface Props {
  register: CandidatesRegister;
}

type Filter = "all" | "corroborated" | "contested";

function pointLayer(rows: Candidate[]): Layer {
  return new ScatterplotLayer<Candidate>({
    id: "candidates",
    data: rows,
    pickable: true,
    radiusUnits: "pixels",
    // One size for every candidate — see the module docstring. A scaled radius would be read
    // as capacity, and this funnel knows nothing about capacity.
    getRadius: 5,
    radiusMinPixels: 4,
    stroked: true,
    lineWidthUnits: "pixels",
    getPosition: (d) => [d.longitude, d.latitude],
    // Solid = corroborated, hollow = a single register's lead.
    getFillColor: (d) =>
      d.corroboration === "corroborated" ? [...EV_REFERENCE, 210] : [...EV_REFERENCE, 40],
    // The ring says "the sources disagree about who runs this".
    getLineColor: (d) => (d.attribution.is_contested ? [...EV_GAP, 255] : [...INK, 120]),
    getLineWidth: (d) => (d.attribution.is_contested ? 2 : 1),
    updateTriggers: { getFillColor: rows, getLineColor: rows },
  });
}

function tooltipHtml(d: Candidate): string {
  const name = d.name ?? d.key;
  const a = d.attribution;
  const operator = a.operator
    ? a.is_contested
      ? `contested — ${a.operator} vs. ${a.contested.map((c) => c.operator).join(", ")}`
      : a.operator
    : "[open] — no source names an operator";
  const sources = d.sources.map((s: PriorSource) => SOURCE_LABELS[s]).join(" + ");
  return `<div style="font-family:ui-monospace,monospace;font-size:11px;line-height:1.5;max-width:22rem">
    <strong>${escapeHtml(name)}</strong><br/>
    ${escapeHtml(operator)}<br/>
    <span style="opacity:.7">${escapeHtml(sources)} · [${d.tag}]</span>
  </div>`;
}

function escapeHtml(text: string): string {
  return text.replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string,
  );
}

export default function CandidatesMap({ register }: Props): JSX.Element {
  const [filter, setFilter] = useState<Filter>("corroborated");
  const [aoi, setAoi] = useState<string>("all");
  const [picked, setPicked] = useState<Candidate | null>(null);
  const [view, setView] = useState(WORLD_VIEW);

  const summaries: AoiSummary[] = useMemo(() => aoiSummaries(register), [register]);

  const rows = useMemo(() => {
    let out = register.candidates;
    if (aoi !== "all") out = out.filter((c) => c.aoi === aoi);
    if (filter === "corroborated") out = out.filter((c) => c.corroboration === "corroborated");
    if (filter === "contested") out = out.filter((c) => c.attribution.is_contested);
    return out;
  }, [register, filter, aoi]);

  const layers = useMemo(() => [pointLayer(rows)], [rows]);

  function flyTo(slug: string): void {
    setAoi(slug);
    setPicked(null);
    if (slug === "all") {
      setView(WORLD_VIEW);
      return;
    }
    const target = summaries.find((s) => s.slug === slug);
    if (target) {
      setView({
        ...WORLD_VIEW,
        longitude: target.center.longitude,
        latitude: target.center.latitude,
        zoom: 9.5,
      });
    }
  }

  return (
    <div
      className="deck-surface dcc-surface"
      role="figure"
      aria-label="Map of international data-center candidates from open registers; the same candidates are listed as text below this map."
    >
      <DeckGL
        initialViewState={view}
        controller
        layers={layers}
        getTooltip={({ object }) => (object ? { html: tooltipHtml(object as Candidate) } : null)}
        onClick={({ object }) => setPicked((object as Candidate) ?? null)}
      >
        <Map mapStyle={BASEMAP} />
      </DeckGL>

      <div className="deck-controls dcc-controls">
        <strong>Show</strong>
        {(
          [
            [
              "corroborated",
              `Corroborated (${register.candidates.filter((c) => c.corroboration === "corroborated").length})`,
            ],
            [
              "contested",
              `Contested attribution (${register.candidates.filter((c) => c.attribution.is_contested).length})`,
            ],
            ["all", `All clusters (${register.candidates.length})`],
          ] as [Filter, string][]
        ).map(([key, label]) => (
          <label key={key}>
            <input type="radio" name="dcc-filter" checked={filter === key} onChange={() => setFilter(key)} />{" "}
            {label}
          </label>
        ))}
        <strong>Area of interest</strong>
        <label>
          <input type="radio" name="dcc-aoi" checked={aoi === "all"} onChange={() => flyTo("all")} />{" "}
          Everywhere swept
        </label>
        {summaries.map((s) => (
          <label key={s.slug}>
            <input type="radio" name="dcc-aoi" checked={aoi === s.slug} onChange={() => flyTo(s.slug)} />{" "}
            {s.label} ({s.corroborated_count})
          </label>
        ))}
      </div>

      <div className="dcc-legend">
        <span>
          <i className="dcc-swatch dcc-swatch--solid" aria-hidden="true"></i> corroborated — two independent
          registers
        </span>
        <span>
          <i className="dcc-swatch dcc-swatch--hollow" aria-hidden="true"></i> single-source lead
        </span>
        <span>
          <i className="dcc-swatch dcc-swatch--contested" aria-hidden="true"></i> sources name different
          operators
        </span>
      </div>

      {picked && (
        <aside className="deck-popup dcc-popup">
          <button type="button" onClick={() => setPicked(null)} aria-label="Close">
            ×
          </button>
          <h3>{picked.name ?? picked.key}</h3>
          <p className="dcc-popup-tag">
            [{picked.tag}] · {picked.corroboration === "corroborated" ? "corroborated" : "single source"}
          </p>
          <dl>
            <dt>Operator</dt>
            <dd>
              {picked.attribution.operator ? (
                <>
                  <a href={picked.attribution.citation ?? "#"}>{picked.attribution.operator}</a>
                  {picked.attribution.is_contested && (
                    <>
                      {" "}
                      <em>
                        — contested by{" "}
                        {picked.attribution.contested.map((c, i) => (
                          <span key={c.citation}>
                            {i > 0 && ", "}
                            <a href={c.citation}>{c.operator}</a> ({SOURCE_LABELS[c.source]})
                          </span>
                        ))}
                      </em>
                    </>
                  )}
                </>
              ) : (
                <span>[open] — no source names one</span>
              )}
            </dd>
            <dt>Placed by</dt>
            <dd>
              {picked.observations.map((o, i) => (
                <span key={o.url}>
                  {i > 0 && " · "}
                  <a href={o.url}>{SOURCE_LABELS[o.source]}</a>
                </span>
              ))}
            </dd>
            <dt>Position</dt>
            <dd>
              {picked.latitude.toFixed(5)}, {picked.longitude.toFixed(5)}
            </dd>
            <dt>Cooling</dt>
            <dd>
              {picked.cooling === "unknown"
                ? "[open] — no open register publishes cooling design"
                : picked.cooling}
            </dd>
          </dl>
        </aside>
      )}
    </div>
  );
}
