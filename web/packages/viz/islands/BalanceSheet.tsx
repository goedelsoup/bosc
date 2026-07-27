/**
 * The public balance sheet (epic #271 Phase 4 capstone, #273). Every narrative's band on
 * one register-encoded sheet, with the cost of opacity priced in aggregate: N withheld
 * records span the public's exposure, and producing them collapses the bands. Composes the
 * existing consumer models via the shared `UncertainOutcome` contract — no new data.
 *
 * Reads as a map of what *isn't* known, not a verdict. Reuses the uncertainty grammar.
 */
import { type BalanceUnit, type GridItLoad, buildBalanceSheet } from "@watermark/core/balanceSheet";
import { fmtMw } from "@watermark/core/format";
import { fmtUsdM } from "@watermark/core/money";
import { siteHref } from "@watermark/core/base";
import { DistributionStrip, RegisterMark } from "./uncertaintyGrammar";

function formatter(unit: BalanceUnit): (n: number) => string {
  if (unit === "usd") return fmtUsdM;
  if (unit === "mw") return fmtMw;
  return (n) => `${n.toFixed(0)}%`;
}

export default function BalanceSheet({
  toxicsEffluentCfs,
  toxicsNaturalCfs,
  site = "lima",
  gridItLoad,
}: {
  toxicsEffluentCfs: number;
  toxicsNaturalCfs: number;
  /** Active site slug — the page passes it so in-island links resolve to this site (#740). */
  site?: string;
  /** The facility feed's IT-load bracket, so the grid row is feed-sourced (#1632). */
  gridItLoad?: GridItLoad | null;
}): JSX.Element {
  const sheet = buildBalanceSheet(toxicsEffluentCfs, toxicsNaturalCfs, site, gridItLoad);
  // Null for a site with no abatement instrument on the record (#1642 E4) — the headline then
  // states the withheld-record count rather than another county's dollar exposure.
  const e = sheet.econExposure;

  return (
    <div className="unc unc-balance">
      <div className="unc-band-head">
        <div className="unc-band-figure">
          {e ? (
            <>
              {fmtUsdM(e.low)} – {fmtUsdM(e.high)}
            </>
          ) : (
            <>{sheet.resolvingRecords.length} withheld records</>
          )}
        </div>
        <div className="unc-band-sub">
          {e ? (
            <>
              the public's monetized 15-year exposure rides on{" "}
              <strong>{sheet.resolvingRecords.length} withheld records</strong> — produce them and the band
              collapses to a number.{" "}
            </>
          ) : (
            <>
              no abatement instrument is on this site's record, so there is no dollar exposure to price — what
              stands are the bands below.{" "}
            </>
          )}
          <em>This is a map of what the record doesn't say, not a verdict.</em>
        </div>
      </div>

      <div className="unc-bs-rows">
        {sheet.rows.map((row) => {
          const o = row.outcome;
          const fmt = formatter(row.unit);
          const pad = (o.high - o.low) * 0.12 || 1;
          return (
            <div className="unc-bs-row" key={o.key}>
              <div className="unc-bs-rowhead">
                <RegisterMark register={o.register} />
                <a className="unc-bs-name" href={row.href}>
                  {row.narrative}
                </a>
                <span className="unc-bs-central">{fmt(o.central)}</span>
              </div>
              <div className="unc-bs-label">{o.label}</div>
              <DistributionStrip
                low={o.low}
                central={o.central}
                high={o.high}
                domain={[o.low - pad, o.high + pad]}
                register={o.register}
                format={fmt}
              />
              {o.resolvingRecord && (
                <div className="unc-bs-resolve">
                  <span className="unc-bs-resolve-tag">what would resolve it</span> {o.resolvingRecord}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <h4 className="unc-h4">The withheld records — the mandamus, in one column</h4>
      <ul className="unc-bs-records">
        {sheet.resolvingRecords.map((rec) => (
          <li key={rec}>
            <RegisterMark register="open" /> {rec}
          </li>
        ))}
      </ul>
      <p className="unc-note">
        Each band above is wide for one reason: a figure the county has not produced.
        {e ? " The economic give is the only line in dollars; the" : " The"} load and the river are bands the
        record never measures. Disclosure — not a verdict from this page — is what narrows any of them. See
        the <a href={siteHref(site, "/site/legal/corpus-completeness-audit")}>corpus-completeness audit</a>{" "}
        for what's missing, and why.
      </p>
    </div>
  );
}
