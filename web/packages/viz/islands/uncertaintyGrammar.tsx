/**
 * Shared visual grammar for the uncertainty engine (epic #271 / #272). Hand-rolled SVG,
 * no dependency, register-encoded so the *evidence status* of a band is legible at a
 * glance — the same vocabulary as the prose tags and `EvidenceTag`:
 *   [verified]   → solid fill
 *   [assumption]/[inference] → hatched
 *   [open]       → outlined (no fill)
 * Reusable by every quantitative narrative's island. Pure presentational components.
 */
import type { Register } from "@watermark/core/uncertainty";

type Reg = Register | "inference";

/** Map a register to its band fill style (solid / hatched / outlined). */
function fillFor(register: Reg, hatchId: string): { fill: string; stroke?: string } {
  if (register === "verified") return { fill: "var(--unc-verified)" };
  if (register === "open") return { fill: "transparent", stroke: "var(--unc-open)" };
  return { fill: `url(#${hatchId})`, stroke: "var(--unc-assumption)" }; // assumption / inference
}

/** The small swatch that names a register in a legend or beside a label. */
export function RegisterMark({ register, label }: { register: Reg; label?: string }): JSX.Element {
  const id = `rm-${register}`;
  const f = fillFor(register, id);
  return (
    <span className={`unc-mark unc-mark--${register}`}>
      <svg width="14" height="10" aria-hidden="true">
        <defs>
          <Hatch id={id} />
        </defs>
        <rect
          x="0.5"
          y="0.5"
          width="13"
          height="9"
          rx="2"
          fill={f.fill}
          stroke={f.stroke ?? "var(--unc-assumption)"}
          strokeWidth="1"
        />
      </svg>
      {label && <span className="unc-mark-label">{label}</span>}
    </span>
  );
}

/** A reusable diagonal-hatch pattern for the [assumption]/[inference] register. */
function Hatch({ id }: { id: string }): JSX.Element {
  return (
    <pattern id={id} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="5" height="5" fill="var(--unc-assumption-bg)" />
      <line x1="0" y1="0" x2="0" y2="5" stroke="var(--unc-assumption)" strokeWidth="1.4" />
    </pattern>
  );
}

export interface DistributionStripProps {
  low: number;
  central: number;
  high: number;
  p10?: number;
  p90?: number;
  bins?: { x0: number; x1: number; n: number }[];
  domain: [number, number];
  register: Reg;
  format: (n: number) => string;
  /** A second band drawn faint behind the main one — the pre-disclosure band, to show the collapse. */
  ghost?: { low: number; high: number };
}

/** A horizontal band with a central tick, optional P10–P90 inner band + density, register-
 *  encoded. The cost-of-opacity object: wide [open] band → tight [verified] line on disclosure. */
export function DistributionStrip(props: DistributionStripProps): JSX.Element {
  const { low, central, high, p10, p90, bins, domain, register, format, ghost } = props;
  const W = 320;
  const H = 64;
  const padX = 6;
  const span = domain[1] - domain[0] || 1;
  const x = (v: number): number => padX + ((v - domain[0]) / span) * (W - 2 * padX);
  const hatchId = "ds-hatch";
  const f = fillFor(register, hatchId);
  const maxN = bins?.length ? Math.max(...bins.map((b) => b.n)) || 1 : 1;
  const bandY = 30;
  const bandH = 16;

  return (
    <svg
      className="unc-strip"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Band ${format(low)} to ${format(high)}, central ${format(central)}`}
    >
      <defs>
        <Hatch id={hatchId} />
      </defs>
      {/* density (faint), when a Monte-Carlo histogram is supplied */}
      {bins?.map((b) => {
        const h = (b.n / maxN) * 18;
        return (
          <rect
            key={b.x0}
            x={x(b.x0)}
            y={28 - h}
            width={Math.max(1, x(b.x1) - x(b.x0) - 0.5)}
            height={h}
            className="unc-density"
          />
        );
      })}
      {/* the pre-disclosure ghost band */}
      {ghost && (
        <rect
          x={x(ghost.low)}
          y={bandY}
          width={Math.max(2, x(ghost.high) - x(ghost.low))}
          height={bandH}
          className="unc-ghost"
          rx="3"
        />
      )}
      {/* the band */}
      <rect
        x={x(low)}
        y={bandY}
        width={Math.max(2, x(high) - x(low))}
        height={bandH}
        fill={f.fill}
        stroke={f.stroke ?? "var(--unc-assumption)"}
        strokeWidth="1.2"
        rx="3"
      />
      {/* P10–P90 inner band */}
      {p10 != null && p90 != null && (
        <rect
          x={x(p10)}
          y={bandY + 3}
          width={Math.max(1, x(p90) - x(p10))}
          height={bandH - 6}
          className="unc-p1090"
          rx="2"
        />
      )}
      {/* central tick */}
      <line x1={x(central)} y1={bandY - 4} x2={x(central)} y2={bandY + bandH + 4} className="unc-central" />
      {/* labels */}
      <text x={x(low)} y={H - 4} className="unc-axis unc-axis--start">
        {format(low)}
      </text>
      <text x={x(high)} y={H - 4} className="unc-axis unc-axis--end">
        {format(high)}
      </text>
      <text x={x(central)} y={20} className="unc-axis unc-axis--mid">
        {format(central)}
      </text>
    </svg>
  );
}

export interface TornadoBarView {
  key: string;
  label: string;
  register: Reg;
  low: number;
  high: number;
  swing: number;
}

/** Sensitivity ranking: one bar per knob (already sorted by swing), each spanning the
 *  outcome with that knob at its extremes, register-encoded. "The one record that tells
 *  you the most." */
export function TornadoChart({
  bars,
  domain,
  format,
}: {
  bars: TornadoBarView[];
  domain: [number, number];
  format: (n: number) => string;
}): JSX.Element {
  const W = 320;
  const rowH = 26;
  const labelW = 0;
  const padX = 6;
  const H = bars.length * rowH + 8;
  const span = domain[1] - domain[0] || 1;
  const x = (v: number): number => labelW + padX + ((v - domain[0]) / span) * (W - labelW - 2 * padX);
  const hatchId = "tc-hatch";
  return (
    <svg className="unc-tornado" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Sensitivity tornado">
      <defs>
        <Hatch id={hatchId} />
      </defs>
      {bars.map((b, i) => {
        const f = fillFor(b.register, hatchId);
        const y = i * rowH + 6;
        return (
          <g key={b.key}>
            <rect
              x={x(b.low)}
              y={y}
              width={Math.max(2, x(b.high) - x(b.low))}
              height={12}
              fill={f.fill}
              stroke={f.stroke ?? "var(--unc-assumption)"}
              strokeWidth="1.2"
              rx="3"
            />
            <text x={x(b.low)} y={y + 22} className="unc-tlabel">
              {b.label}
            </text>
            <text x={x(b.high)} y={y + 10} className="unc-tswing">
              ±{format(b.swing / 2)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
