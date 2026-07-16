/**
 * OPC roundabout scenario explorer — the native successor to the marimo
 * `opc_scenario.py` notebook (retired; the evaluation is `docs/marimo-integration-
 * investigation.md`). A contingency-rate slider + an intersection multiselect re-derive
 * the six Tetra Tech *Opinion of Probable Project Cost* sub-estimates live, over the
 * committed `records` feed — the same numbers the library renders, no fork.
 *
 * Island-over-SSR: the page's <noscript> table is the no-JS fallback (the source totals
 * at the source's 25% convention, from the same model); this is the client island.
 *
 * Discipline: each `construction_subtotal` is the high-confidence figure [verified]; the
 * modeled total is `subtotal × (1 + rate)` [inference], a re-pricing under a chosen rate,
 * not a second source. Read-only — moving the knob re-prices the record, never edits it.
 */
import { useMemo, useState } from "react";
import { fmtUsdFull } from "@watermark/core/money";
import {
  modeledRows,
  type OpcScenario as OpcScenarioData,
  programTotal,
  sourceProgramTotal,
} from "@watermark/core/opcScenario";
import { Line, Slider } from "./scenarioControls";
import { RegisterMark } from "./uncertaintyGrammar";

function signed(n: number): string {
  return `${n < 0 ? "−" : "+"}${fmtUsdFull(Math.abs(n))}`;
}

export default function OpcScenario({ scenario }: { scenario: OpcScenarioData }): JSX.Element {
  const [pct, setPct] = useState(scenario.sourceContingencyPct);
  const [selected, setSelected] = useState<Set<string>>(() => new Set(scenario.subs.map((s) => s.name)));

  function toggle(name: string): void {
    setSelected((cur) => {
      const next = new Set(cur);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  const rows = useMemo(() => modeledRows(scenario.subs, pct, selected), [scenario.subs, pct, selected]);
  const modeledProgram = programTotal(rows);
  const sourceProgram = sourceProgramTotal(rows);

  return (
    <div className="unc unc-opc">
      <div className="unc-sliders">
        <Slider
          label="Contingency + inflation (%)"
          value={pct}
          min={0}
          max={50}
          step={1}
          onChange={setPct}
          fmt={(v) => `${Math.round(v)}%`}
          register="assumption"
        />
      </div>

      <h4 className="unc-h4">Intersections</h4>
      <div className="unc-disclose" role="group" aria-label="Intersections">
        {scenario.subs.map((s) => (
          <label key={s.name} className={`unc-disclose-row${selected.has(s.name) ? " is-disclosed" : ""}`}>
            <input type="checkbox" checked={selected.has(s.name)} onChange={() => toggle(s.name)} />
            <span className="unc-disclose-label">
              <RegisterMark register="verified" /> {s.name}
            </span>
            <span className="unc-disclose-rec">{fmtUsdFull(s.constructionSubtotal)} constr.</span>
          </label>
        ))}
      </div>

      <div className="unc-band-head">
        <div className="unc-band-figure">{fmtUsdFull(modeledProgram)}</div>
        <div className="unc-band-sub">
          modeled program construction cost · {rows.length} of {scenario.subs.length} intersections at{" "}
          {Math.round(pct)}% contingency
        </div>
      </div>

      <dl className="unc-readout">
        <Line
          label={`Source program total (at ${scenario.sourceContingencyPct}%)`}
          value={fmtUsdFull(sourceProgram)}
          register="verified"
        />
        <Line label="Modeled − source" value={signed(modeledProgram - sourceProgram)} register="inference" />
      </dl>

      <h4 className="unc-h4">By intersection — modeled vs source</h4>
      <dl className="unc-readout">
        {rows.length === 0 ? (
          <Line label="No intersections selected" value="—" register="open" />
        ) : (
          rows.map((r) => (
            <Line
              key={r.name}
              label={r.name}
              value={`${fmtUsdFull(r.modeledTotal)} · source ${fmtUsdFull(r.sourceTotal)}`}
              register="inference"
            />
          ))
        )}
      </dl>

      <p className="unc-note">
        Construction subtotals are the high-confidence figures <RegisterMark register="verified" />; each
        modeled total is that subtotal re-derived at the chosen rate <RegisterMark register="assumption" />,
        not a second source. At the source's {scenario.sourceContingencyPct}% convention the modeled totals
        reproduce the {scenario.estimator} totals. Read-only over the committed {scenario.basis.toLowerCase()}{" "}
        estimate — the knob re-prices the record, it never edits it.
      </p>
    </div>
  );
}
