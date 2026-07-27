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
  type BackupRecord,
  GRID_PRIORS,
  type GridBaseline,
  annualGwh,
  equivalentHomes,
  facilityDrawModel,
  mwPerJob,
  pctOfUtilityRetail,
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

export interface GridLoadScreenProps {
  priors?: Prior[];
  /** The feed-sourced denominators (`gridBackdrop.buildGridBaseline`) — #1642 E2. Null ⇒ the
   *  site carries no `grid` feed, so the load-vs-baseline readouts are withheld rather than
   *  divided by another utility's sales. (Named apart from the local `baseline` band below, which
   *  is the undisclosed outcome band that fixes the chart axes.) */
  gridBaseline?: GridBaseline | null;
  /** The cited backup record behind the headline MW (`gridLoad.backupRecord`) — null off Lima. */
  backup?: BackupRecord | null;
  /** The site's non-binding promised job count (`econLedger.promisedJobs`) — null where none. */
  promisedJobs?: number | null;
}

export default function GridLoadScreen({
  priors = GRID_PRIORS,
  gridBaseline = null,
  backup = null,
  promisedJobs = null,
}: GridLoadScreenProps = {}): JSX.Element {
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
          {backup ? (
            <>
              <RegisterMark register="verified" /> {backup.backupMw} MW backup <em>(draft)</em>
            </>
          ) : (
            <>
              <RegisterMark register="open" /> backup capacity <em>(not on this site's record)</em>
            </>
          )}
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
      {/* Every line below the annual energy divides by a per-site figure from the `grid` /
          `economics-demand-pressure` feeds (#1642 E2). A site missing one withholds that line
          rather than borrowing another utility's sales or another county's job promise. */}
      <dl className="unc-readout">
        <Line
          label="Annual energy"
          value={`${Math.round(gwh).toLocaleString("en-US")} GWh/yr`}
          register="inference"
        />
        {gridBaseline && (
          <Line
            label={`Share of ${gridBaseline.utilityLabel} retail sales`}
            value={`${pctOfUtilityRetail(gwh, gridBaseline.utilityRetailGwh).toFixed(1)}% of ${gridBaseline.utilityRetailGwh.toLocaleString("en-US")} GWh`}
            register="verified"
            strong
          />
        )}
        {gridBaseline?.householdKwhYr != null && (
          <Line
            label="Equivalent homes"
            value={`~${Math.round(equivalentHomes(gwh, gridBaseline.householdKwhYr) / 1000)}k homes`}
            register="inference"
          />
        )}
        {promisedJobs != null && (
          <>
            <Line label="Promised jobs" value={`~${promisedJobs}`} register="verified" />
            <Line
              label="Load per job"
              value={`~${mwPerJob(itCentral, promisedJobs).toFixed(1)} MW / job`}
              register="inference"
              strong
            />
          </>
        )}
      </dl>

      {backup && (
        <p className="unc-note">
          <strong>{backup.backupMw} MW is backup, not load.</strong> The per-engine rating that pins it is
          redacted in the issued permit — the band above exists <em>because</em> the record is withheld.
          "Behind-the-meter" is a proponent claim <code>[open]</code>: the campus is a rate-regulated{" "}
          <strong>retail</strong> customer of {gridBaseline?.utilityLabel ?? "the serving utility"} (the{" "}
          {backup.nEngines} gensets are emergency backup, not primary generation). PJM dollar figures are a{" "}
          <code>[reference]</code> screen, not a finding. What survives is the load.
        </p>
      )}
    </div>
  );
}
