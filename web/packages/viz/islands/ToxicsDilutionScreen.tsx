/**
 * Toxics seasonal-dilution simulator (epic #271 Phase 2, #264). Drag the Ottawa's low
 * flow from the summer 30Q10 down to the driest 1Q10 and watch the river leaving Lima
 * climb toward 100% treated effluent — the dilution collapses while the loads stay fixed.
 * The RSEI dischargers stack on the same reach, register-encoded `[inference]` (a modeled
 * screen, not a measurement). Reuses the uncertainty grammar; consumes the feed's
 * discharge constants (no fork).
 */
import { useMemo, useState } from "react";
import type { DilutionDischarge } from "@watermark/core/dilution";
import {
  ANNUAL_OTTAWA_7Q10,
  FLOW_REGIMES,
  MAX_OTTAWA_CFS,
  RSEI_DISCHARGERS,
  effluentMultiple,
  effluentPct,
  naturalAt,
  screeningConc,
} from "@watermark/core/toxicsDilution";
import { fmtMult } from "@watermark/core/format";
import { Slider } from "./scenarioControls";
import { DistributionStrip, RegisterMark } from "./uncertaintyGrammar";

const fmtPct = (n: number): string => `${n.toFixed(0)}%`;
const fmtConc = (n: number): string => (Number.isFinite(n) ? `${n.toFixed(0)} mg/L` : "→ ∞");

export default function ToxicsDilutionScreen({ discharge }: { discharge: DilutionDischarge }): JSX.Element {
  const effluentCfs = discharge.wwtpCfs + discharge.campusFm2Cfs;
  const naturalAnnual = discharge.naturalCfs;
  const [ottawa, setOttawa] = useState(ANNUAL_OTTAWA_7Q10);

  const now = useMemo(() => {
    const natural = naturalAt(ottawa, naturalAnnual);
    return {
      natural,
      pct: effluentPct(effluentCfs, natural),
      mult: effluentMultiple(effluentCfs, natural),
    };
  }, [ottawa, effluentCfs, naturalAnnual]);

  const summerPct = effluentPct(effluentCfs, naturalAt(MAX_OTTAWA_CFS, naturalAnnual));
  const concDomainMax = Math.max(...RSEI_DISCHARGERS.map((d) => d.conc7q10MgL));

  return (
    <div className="unc unc-toxics">
      <div className="unc-band-head">
        <div className="unc-band-figure">{fmtPct(now.pct)} treated effluent</div>
        <div className="unc-band-sub">
          the Ottawa leaving Lima at this flow · effluent is <strong>{fmtMult(now.mult)}</strong> the river's
          own water
        </div>
      </div>

      <div className="unc-sliders">
        <Slider
          label="Ottawa low flow — drag toward the dry floor"
          value={ottawa}
          min={0}
          max={MAX_OTTAWA_CFS}
          step={0.05}
          onChange={setOttawa}
          fmt={(v) => `${v.toFixed(2)} cfs`}
          register="open"
        />
        <div className="unc-tabs" role="group" aria-label="Low-flow regime">
          {FLOW_REGIMES.map((r) => (
            <button
              key={r.key}
              type="button"
              className={`unc-tab${Math.abs(ottawa - r.ottawaCfs) < 0.03 ? " is-active" : ""}`}
              onClick={() => setOttawa(r.ottawaCfs)}
              title={r.note}
            >
              {r.label} ({r.ottawaCfs} cfs)
            </button>
          ))}
        </div>
      </div>

      <h4 className="unc-h4">The assimilative band — what the record never measures</h4>
      <DistributionStrip
        low={summerPct}
        central={now.pct}
        high={100}
        domain={[Math.floor(summerPct), 100]}
        register="open"
        format={fmtPct}
      />
      <p className="unc-band-sub">
        Summer dilutes most; at the <strong>1Q10 the river is gone</strong> and what leaves Lima is effluent.
        The record carries no DMRs and no ambient sampling — the actual capacity is <code>[open]</code>.
      </p>

      <h4 className="unc-h4">RSEI toxic dischargers on the same reach — a modeled screen, not the river</h4>
      <div className="unc-rsei">
        {RSEI_DISCHARGERS.map((d) => {
          const conc = screeningConc(d, ottawa);
          return (
            <div className="unc-rsei-row" key={d.name}>
              <div className="unc-rsei-head">
                <RegisterMark register={d.receivingCited ? "verified" : "inference"} />
                <span className="unc-rsei-name">{d.name}</span>
                <span className="unc-rsei-conc">{fmtConc(conc)}</span>
              </div>
              <DistributionStrip
                low={screeningConc(d, MAX_OTTAWA_CFS)}
                central={d.conc7q10MgL}
                high={d.conc7q10MgL}
                domain={[0, concDomainMax]}
                register="inference"
                format={(n) => `${n.toFixed(0)}`}
              />
              <div className="unc-rsei-note">
                RSEI {d.score.toLocaleString("en-US")} · {d.topChemical} ·{" "}
                {d.receivingCited ? "receiving water ECHO-cited" : "receiving water inferred"}
              </div>
            </div>
          );
        })}
      </div>

      <p className="unc-note">
        EPA's RSEI <em>ranks</em> who releases what; it is not a concentration, a dose, or a risk estimate.
        The screening figures are a coarse <code>[inference: derived]</code> mix at the 7Q10 — no mixing zone,
        no decay. Only Lima Refining's Ottawa receiving water is independently ECHO-cited. The screen shows
        three large dischargers on a near-undiluted reach; it does <strong>not</strong> show the river exceeds
        its capacity — that record (DMRs, ambient sampling) is the one the corpus is missing.
      </p>
    </div>
  );
}
