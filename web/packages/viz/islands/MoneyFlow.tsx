/**
 * Follow-the-money island (#223) — the Cost chapter. The public's roadwork money
 * on one axis: the $14.5M "Company Contribution" collected up front, the Tetra
 * Tech OPC estimate (six corridor segments — hover/focus to read each), and the
 * first actual construction award (Eagle Bridge, N. Cole) running far under. The
 * §5.5 grant-refund routes any certified surplus back to the developer.
 *
 * Mounted `client:only` over the page's SSR flow table; the numbers are the
 * build-time `MoneyFlowData` (the OPC line items are the records feed's own — no
 * fork). The §5.5 consequence is flagged `[inference]`.
 */
import { useState } from "react";
import { fmtUsd, fmtUsdFull } from "@watermark/core/money";
import type { MoneyFlowData } from "@watermark/core/moneyFlow";

export default function MoneyFlow({ data }: { data: MoneyFlowData }): JSX.Element {
  const [active, setActive] = useState<number | null>(null);
  const axis = Math.max(data.collectedUsd, data.opcTotalUsd, data.firstAward.usd, 1);
  const pct = (n: number): string => `${Math.min((n / axis) * 100, 100)}%`;
  const item = active != null ? data.opcItems[active] : null;

  return (
    <div
      className="mf"
      role="figure"
      aria-label="Follow the money: the $14.5M Company Contribution collected, the Tetra Tech OPC estimate by corridor, and the first actual construction award. The same figures are in the table on this page."
    >
      <div className="mf-stage">
        <div className="mf-stage-head">
          <span>Collected · “Company Contribution”</span>
          <strong>{fmtUsd(data.collectedUsd)}</strong>
        </div>
        <div className="mf-track">
          <div className="mf-bar mf-bar--collected" style={{ width: pct(data.collectedUsd) }} />
        </div>
      </div>

      <div className="mf-stage">
        <div className="mf-stage-head">
          <span>Tetra Tech OPC estimate · 6 corridors</span>
          <strong>{fmtUsd(data.opcTotalUsd)}</strong>
        </div>
        <div className="mf-track">
          <div className="mf-segbar" style={{ width: pct(data.opcTotalUsd) }}>
            {data.opcItems.map((it, i) => (
              <button
                key={it.name}
                type="button"
                className={`mf-seg${active === i ? " is-active" : ""}`}
                style={{ flexGrow: it.usd }}
                aria-label={`${it.name}: ${fmtUsdFull(it.usd)}`}
                onMouseEnter={() => setActive(i)}
                onFocus={() => setActive(i)}
                onMouseLeave={() => setActive(null)}
                onBlur={() => setActive(null)}
              />
            ))}
          </div>
        </div>
        <div className="mf-segread" role="status" aria-live="polite" aria-label="Selected corridor line item">
          {item ? (
            <>
              {item.name} · <strong>{fmtUsdFull(item.usd)}</strong>
            </>
          ) : (
            <span className="card-meta">Hover or tab a segment to read each corridor's line item.</span>
          )}
        </div>
      </div>

      <div className="mf-stage">
        <div className="mf-stage-head">
          <span>First actual award · Eagle Bridge (N. Cole)</span>
          <strong>{fmtUsd(data.firstAward.usd)}</strong>
        </div>
        <div className="mf-track">
          <div className="mf-bar mf-bar--actual" style={{ width: pct(data.firstAward.usd) }} />
        </div>
        <div className="mf-note card-meta">the rest of the program is still being awarded</div>
      </div>

      <div className="mf-refund">
        <span className="mf-refund-arrow" aria-hidden="true">
          ↩
        </span>
        <div>
          <span className="mf-tag">[inference]</span> Actual awards are running well under the sum collected
          up front — and <strong>§5.5</strong> refunds any certified overpayment back to the developer, with
          public grants able to backfill the “private” contribution.
        </div>
      </div>
    </div>
  );
}
