/**
 * End-use & workloads explorer (#251 interactive layer). The report's [verified]
 * taxonomy, made selectable: pick one of the four things called "data center" and
 * read who owns the compute, who benefits, and — the axis that narrows — who can
 * even use it. A persistent Lima readout holds the payoff: confirming the customer
 * (Google) did not resolve the use.
 *
 * Mounted `client:only` over the page's SSR table (no-JS readable). The data is the
 * build-time `EndUseData` (curated from the committee record); the island imports
 * only the type.
 */
import { useState } from "react";
import { type DcKey, type EndUseData, IL_LADDER } from "@watermark/core/endUse";
import { siteHref } from "@watermark/core/base";
import { RegisterMark } from "./uncertaintyGrammar";

export default function EndUseExplorer({
  data,
  site = "lima",
}: {
  data: EndUseData;
  site?: string;
}): JSX.Element {
  const [activeKey, setActiveKey] = useState<DcKey>("hyperscale");
  const active = data.types.find((t) => t.key === activeKey) ?? data.types[0];
  const reach = active.ladderReach; // [from, to] indices into IL_LADDER, or null (self only)

  return (
    <div
      className="eu"
      role="figure"
      aria-label="Interactive: the four businesses called 'data center' and what the Lima record says about each. The same content is in the table on this page."
    >
      <div className="eu-tabs" role="group" aria-label="Type of data center">
        {data.types.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`eu-tab${t.key === activeKey ? " is-active" : ""}${
              t.limaStatus === "ruled-out" ? " is-ruled-out" : ""
            }`}
            aria-pressed={t.key === activeKey}
            onClick={() => setActiveKey(t.key)}
          >
            <span className="eu-tab-label">{t.label}</span>
            <span className="eu-tab-tag">{t.tagline}</span>
          </button>
        ))}
      </div>

      <div className="eu-detail" role="status" aria-live="polite">
        <div className="eu-detail-head">
          <h3 className="eu-detail-title">{active.label}</h3>
          <span className={`eu-lima eu-lima--${active.limaStatus}`}>
            {active.limaStatus === "ruled-out" ? "Lima: ruled out" : "Lima: [open]"}
          </span>
        </div>

        <dl className="eu-attrs">
          <div className="eu-attr">
            <dt>Who owns the compute</dt>
            <dd>{active.ownsCompute}</dd>
          </div>
          <div className="eu-attr">
            <dt>Who benefits</dt>
            <dd>{active.whoBenefits}</dd>
          </div>
          <div className="eu-attr">
            <dt>Who can use it</dt>
            <dd>{active.whoCanUse}</dd>
          </div>
          <div className="eu-attr">
            <dt>Who captures the abatement</dt>
            <dd>
              <RegisterMark register={active.benefitCapture.register} /> {active.benefitCapture.who}{" "}
              <a className="eu-ledger-link" href={siteHref(site, "/reports/the-economic-ledger")}>
                (the subsidy →)
              </a>
            </dd>
          </div>
          <div className="eu-attr">
            <dt>Local economy</dt>
            <dd>{active.localEconomy}</dd>
          </div>
        </dl>

        {/* The "who can use it" dimension as the FedRAMP/DoD-IL ladder, broad → sealed.
            Highlight this model's reach; structure, not a Lima finding. */}
        <div className="eu-ladder" role="group" aria-label="FedRAMP / DoD impact-level access ladder">
          {IL_LADDER.map((rung, i) => {
            const inReach = reach !== null && i >= reach[0] && i <= reach[1];
            return (
              <span
                key={rung.key}
                className={`eu-rung${inReach ? " is-reach" : ""}${reach && i === reach[1] ? " is-ceiling" : ""}`}
                title={rung.note}
              >
                {rung.label}
              </span>
            );
          })}
        </div>
        <p className="eu-access-note">
          {reach === null
            ? "Off the ladder — a mine is its own only user."
            : reach[1] >= 4
              ? "This model can reach the sealed IL-6 enclave — the access the Lima record can neither confirm nor rule out."
              : "Broad-to-FedRAMP access; the ladder above it is structure, not a Lima finding."}
        </p>

        <p className="eu-evidence">
          <span className="eu-evidence-mark" aria-hidden="true">
            ⌖
          </span>{" "}
          <RegisterMark register={active.evidenceRegister} /> {active.evidence}
        </p>
        <p className="eu-lima-note">{active.limaNote}</p>
      </div>

      <div className="eu-readout">
        <div className="eu-readout-row">
          <RegisterMark register="verified" />
          <span>{data.verified}</span>
        </div>
        <div className="eu-readout-row">
          <RegisterMark register="open" />
          <span>{data.openQuestion}</span>
        </div>
      </div>

      {/* The two pointed silences — absences that bear on the [open], never findings. */}
      <div className="eu-silences">
        <div className="eu-silences-head">Two pointed silences — neither is a finding</div>
        {data.silences.map((s) => (
          <div className="eu-silence" key={s.label}>
            <RegisterMark register={s.register} />
            <div>
              <strong>{s.label}.</strong> {s.note}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
