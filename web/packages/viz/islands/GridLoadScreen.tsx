/**
 * Grid load-band simulator (epic #271 Phase 2, #265). The headline "313 MW" is backup,
 * not load, and the per-engine rating behind it is redacted in the issued permit — so the
 * working load is an inference chain (313 backup → IT via N+1 → ×PUE → facility ~348 MW),
 * and that chain IS the uncertainty. Disclose the operating load and the band collapses;
 * the load-not-jobs bars hold the finding that survives both disciplines. Reuses the
 * uncertainty engine + grammar.
 */
import { useMemo, useState } from "react";
import {
  AEP_OHIO_RETAIL_GWH,
  BACKUP_MW,
  GRID_PRIORS,
  PROMISED_JOBS,
  annualGwh,
  equivalentHomes,
  facilityDrawModel,
  mwPerJob,
  pctOfAepRetail,
} from "@watermark/core/gridLoad";
import {
  DEFAULT_SEED,
  type Prior,
  applyDisclosures,
  outcomeBand,
  priorCentral,
  sample,
  summarize,
} from "@watermark/core/uncertainty";
import { fmtMw } from "@watermark/core/format";
import { DiscloseList, Line } from "./scenarioControls";
import { DistributionStrip, RegisterMark } from "./uncertaintyGrammar";

export default function GridLoadScreen({ priors = GRID_PRIORS }: { priors?: Prior[] } = {}): JSX.Element {
  const [disclosed, setDisclosed] = useState<Record<string, boolean>>({});

  // `priors` is feed-sourced from the facility's disclosed IT-load range (#1632) when the page
  // passes it; else the Lima default GRID_PRIORS. Either way the basin and this band share one
  // sourced IT figure.
  const effectivePriors = useMemo(() => applyDisclosures(priors, disclosed), [priors, disclosed]);

  const band = useMemo(() => outcomeBand(effectivePriors, facilityDrawModel), [effectivePriors]);
  const summary = useMemo(
    () => summarize(sample(effectivePriors, facilityDrawModel, 6000, DEFAULT_SEED), 24),
    [effectivePriors],
  );
  const baseline = useMemo(() => outcomeBand(priors, facilityDrawModel), [priors]);

  // The load-not-jobs figures, read off the central inferred facility draw + IT load.
  const gwh = annualGwh(band.central);
  const itCentral = priorCentral(priors, "it_load");
  const halfWidth = (band.high - band.low) / 2;

  return (
    <div className="unc unc-grid">
      <div className="unc-band-head">
        <div className="unc-band-figure">
          {fmtMw(band.low)} – {fmtMw(band.high)}
        </div>
        <div className="unc-band-sub">
          inferred facility draw · ±{fmtMw(halfWidth)}{" "}
          {Object.values(disclosed).some(Boolean)
            ? "(narrowed by disclosure)"
            : "(the band the redaction leaves)"}
        </div>
      </div>

      <div className="unc-chain">
        <span className="unc-chain-step">
          <RegisterMark register="verified" /> {BACKUP_MW} MW backup <em>(draft)</em>
        </span>
        <span className="unc-chain-arrow">→</span>
        <span className="unc-chain-step">
          <RegisterMark register="assumption" /> IT load (N+1)
        </span>
        <span className="unc-chain-arrow">→</span>
        <span className="unc-chain-step">
          <RegisterMark register="assumption" /> × PUE = facility draw
        </span>
      </div>

      <DistributionStrip
        low={band.low}
        central={band.central}
        high={band.high}
        p10={summary.p10}
        p90={summary.p90}
        bins={summary.bins}
        domain={[Math.floor(baseline.low) - 3, Math.ceil(baseline.high) + 3]}
        ghost={{ low: baseline.low, high: baseline.high }}
        register="inference"
        format={fmtMw}
      />

      <h4 className="unc-h4">Produce a record → collapse the inference</h4>
      <DiscloseList
        priors={priors}
        disclosed={disclosed}
        onToggle={(key, value) => setDisclosed((d) => ({ ...d, [key]: value }))}
      />

      <h4 className="unc-h4">Load, not jobs</h4>
      <dl className="unc-readout">
        <Line
          label="Annual energy"
          value={`${Math.round(gwh).toLocaleString("en-US")} GWh/yr`}
          register="inference"
        />
        <Line
          label="Share of AEP Ohio retail sales"
          value={`${pctOfAepRetail(gwh).toFixed(1)}% of ${AEP_OHIO_RETAIL_GWH.toLocaleString("en-US")} GWh`}
          register="verified"
          strong
        />
        <Line
          label="Equivalent Ohio homes"
          value={`~${Math.round(equivalentHomes(gwh) / 1000)}k homes`}
          register="inference"
        />
        <Line label="Promised jobs" value={`~${PROMISED_JOBS}`} register="verified" />
        <Line
          label="Load per job"
          value={`~${mwPerJob(itCentral).toFixed(1)} MW / job`}
          register="inference"
          strong
        />
      </dl>

      <p className="unc-note">
        <strong>313 MW is backup, not load.</strong> The per-engine rating that pins it is redacted in the
        issued permit — the band above exists <em>because</em> the record is withheld. "Behind-the-meter" is a
        proponent claim <code>[open]</code>: the campus is a PUCO-regulated <strong>retail</strong> customer
        of AEP Ohio (the 114 gensets are emergency backup, not primary generation). PJM dollar figures are a
        <code>[reference]</code> screen, not a finding. What survives is the load: ~5–6% of a utility's entire
        retail electricity, ~260k homes of it, for ~50 jobs.
      </p>
    </div>
  );
}
