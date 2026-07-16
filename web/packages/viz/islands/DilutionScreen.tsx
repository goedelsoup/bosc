/**
 * Consumptive-draw island (#222, corrected) — "what the campus takes out of the
 * basin." Scrub the cooling draw and the season, and watch the net **consumptive
 * loss** measured against the Ottawa's low flow: ~24× the annual 7Q10, ~3× the
 * summer 30Q10 (the seasonal pinch), and more than the entire driest-week flow.
 *
 * IMPORTANT framing (the corrected pass): the campus draws from Lima's off-stream
 * reservoirs, **not the Ottawa**, so this is a basin-scale *worst-case bound*,
 * carried as `[inference]` — not a river withdrawal. What the campus discharges
 * *into* the river is the separate, `[verified]` discharge finding rendered above
 * this island (SSR). Numbers are the build-time `DilutionData` (feed's own — no fork).
 */
import { useId, useState } from "react";
import type { DilutionData, DilutionFloor } from "@watermark/core/dilution";
import { fmtMult } from "@watermark/core/format";

export default function DilutionScreen({ data }: { data: DilutionData }): JSX.Element {
  const [coolingMgd, setCoolingMgd] = useState(data.maxCoolingMgd);
  const [seasonKey, setSeasonKey] = useState<DilutionFloor["key"]>("summer");
  const sliderId = useId();

  const floor = data.floors.find((f) => f.key === seasonKey) ?? data.floors[0];
  const draw = coolingMgd * data.cfsPerCoolingMgd;
  const multiple = floor.cfs > 0 ? draw / floor.cfs : Number.POSITIVE_INFINITY;
  const dry = floor.cfs <= 0;

  // Axis = the larger of river floor and draw, so the draw overflows the river
  // bar visibly; a small floor keeps a thread of river showing when it's ~0.
  const axisMax = Math.max(draw, floor.cfs, 0.01);
  const riverPct = Math.max((floor.cfs / axisMax) * 100, dry ? 0 : 1);
  const drawPct = Math.min((draw / axisMax) * 100, 100);

  return (
    <div
      className="dil"
      role="figure"
      aria-label="Interactive basin-loss scale: the campus net consumptive loss against the Ottawa River's low flow by season. The campus draws from Lima's reservoirs, not the river. The same figures are in the seasonal table on this page."
    >
      <div className="dil-head">
        <strong>What the campus takes out of the basin</strong>
        <span
          className="dil-tag"
          title="The campus draws from Lima's off-stream reservoirs, not the Ottawa. Setting the net evaporative loss against the river's low flow is a basin-scale worst-case bound, not a river withdrawal."
        >
          [inference] · basin-loss scale
        </span>
      </div>

      <p className="dil-framing">
        The campus draws from Lima's off-stream reservoirs, <strong>not the river</strong> — this sets its net
        evaporative loss against the Ottawa's low flow as a <em>scale</em>, not a withdrawal.
      </p>

      <div className="dil-bars">
        <div className="dil-barrow">
          <div className="dil-barlabel">
            Ottawa · {floor.label} low flow
            <span className="dil-barnum">{floor.cfs.toFixed(2)} cfs</span>
          </div>
          <div className="dil-track">
            <div className="dil-bar dil-bar--river" style={{ width: `${riverPct}%` }} />
            {dry && <div className="dil-dry">≈ 0 cfs at 1Q10</div>}
          </div>
        </div>
        <div className="dil-barrow">
          <div className="dil-barlabel">
            Campus net consumptive loss
            <span className="dil-barnum">{draw.toFixed(2)} cfs</span>
          </div>
          <div className="dil-track">
            <div className="dil-bar dil-bar--draw" style={{ width: `${drawPct}%` }} />
          </div>
        </div>
      </div>

      <div className="dil-readout" role="status" aria-live="polite" aria-label="Basin-loss scale result">
        <span className="dil-mult">
          {dry ? "more than the whole river" : `${fmtMult(multiple)} the river's low flow`}
        </span>
        <span className="dil-readsub">
          {dry
            ? "the basin loss exceeds the Ottawa's entire driest-week flow"
            : `a permanent basin loss — ${fmtMult(multiple)} the Ottawa's ${floor.label.toLowerCase()}`}
        </span>
      </div>

      <div className="dil-controls">
        <label className="dil-slabel" htmlFor={sliderId}>
          Cooling draw
          <span className="dil-snum">
            {coolingMgd.toFixed(2)} MGD
            <span className="card-meta"> · {data.maxCoolingMgd.toFixed(2)} at full buildout</span>
          </span>
        </label>
        <input
          id={sliderId}
          className="dil-slider"
          type="range"
          min={0}
          max={data.maxCoolingMgd}
          step={data.maxCoolingMgd / 100}
          value={coolingMgd}
          aria-label="Campus cooling draw, million gallons per day"
          onChange={(e) => setCoolingMgd(Number(e.target.value))}
        />
        <div className="dil-seasons" role="group" aria-label="Receiving-stream low-flow season">
          {data.floors.map((f) => (
            <button
              key={f.key}
              type="button"
              className="dil-season"
              aria-pressed={f.key === seasonKey}
              onClick={() => setSeasonKey(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <p className="dil-cite">
        ⌖ {floor.cite}
        {floor.note ? ` · ${floor.note}` : ""}
      </p>
    </div>
  );
}
