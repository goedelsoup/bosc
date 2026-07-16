/**
 * Shared controls for the scenario islands — the register-marked slider + readout line
 * lifted out of `EconLedgerSimulator` so every "scenario" island (the economic ledger,
 * the OPC roundabout explorer, the next precomputed-results notebook) renders the same
 * knob/readout grammar over the same `unc-*` styles. Pure presentational; the
 * evidence-palette `RegisterMark` keeps a knob's evidence status legible at a glance.
 */
import type { Prior } from "@watermark/core/uncertainty";
import { RegisterMark } from "./uncertaintyGrammar";

/** A register-marked range input with a formatted live value (a scenario knob). */
export function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
  fmt,
  register,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  fmt: (v: number) => string;
  register: "verified" | "assumption" | "open";
}): JSX.Element {
  return (
    <label className="unc-slider">
      <span className="unc-slider-label">
        <RegisterMark register={register} /> {label}
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="unc-slider-val">{fmt(value)}</span>
    </label>
  );
}

/**
 * The "produce a record → collapse the band" disclose list — one toggle per withheld
 * prior, each pinning its knob to reference on check. Lifted out of the econ/grid
 * simulators, which rendered byte-identical markup over their `*_PRIORS` (#580).
 */
export function DiscloseList({
  priors,
  disclosed,
  onToggle,
}: {
  priors: Prior[];
  disclosed: Record<string, boolean>;
  onToggle: (key: string, value: boolean) => void;
}): JSX.Element {
  return (
    <div className="unc-disclose">
      {priors.map((p) => (
        <label key={p.key} className={`unc-disclose-row${disclosed[p.key] ? " is-disclosed" : ""}`}>
          <input
            type="checkbox"
            checked={!!disclosed[p.key]}
            onChange={(e) => onToggle(p.key, e.target.checked)}
          />
          <span className="unc-disclose-label">
            <RegisterMark register={p.register} /> {p.label}
          </span>
          <span className="unc-disclose-rec">{disclosed[p.key] ? "disclosed" : p.resolvingRecord}</span>
        </label>
      ))}
    </div>
  );
}

/** A register-marked label/value readout row (one line of a scenario's output). */
export function Line({
  label,
  value,
  register,
  strong,
}: {
  label: string;
  value: string;
  register: "verified" | "assumption" | "inference" | "open";
  strong?: boolean;
}): JSX.Element {
  return (
    <div className={`unc-line${strong ? " is-strong" : ""}`}>
      <dt>
        <RegisterMark register={register} /> {label}
      </dt>
      <dd>{value}</dd>
    </div>
  );
}
