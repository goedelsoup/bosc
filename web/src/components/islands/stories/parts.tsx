/**
 * Shared React render primitives for the Story islands (#1096/#1097). The runtime renderer is a
 * client island, so it can't use the Astro presentation components (`EvidenceTag.astro`,
 * `charts/Sparkline.astro`, …) — these are the compact React echoes, styled off the same design
 * tokens (evidence colors stay reserved for evidence; indigo/forest for signal). Kept tiny and
 * dependency-free (hand-rolled SVG, matching the site's chart idiom).
 */
import type { CSSProperties } from "react";
import { EVIDENCE_META, type EvidenceKind } from "~/lib/storyAtoms";

export const mono = "var(--font-mono)";
export const sans = "var(--font-sans)";

/** An evidence pill — the one place a Story spends the evidence palette. `bracket` renders the
 *  `[verified]` form used inside timeline rows; otherwise a plain tinted chip. */
export function Ev({
  kind,
  bracket = false,
  size = "sm",
}: {
  kind: EvidenceKind;
  bracket?: boolean;
  size?: "sm" | "xs";
}) {
  const m = EVIDENCE_META[kind];
  const pad = size === "xs" ? "1px 6px" : "2px 8px";
  const fs = size === "xs" ? 9.5 : 10.5;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontFamily: mono,
        fontSize: fs,
        fontWeight: 700,
        letterSpacing: "0.2px",
        color: m.fg,
        background: m.bg,
        border: `1px solid ${m.border}`,
        padding: pad,
        whiteSpace: "nowrap",
      }}
    >
      {bracket ? `[${m.label}]` : m.label}
    </span>
  );
}

/** A monospace eyebrow / kind label. */
export function KindLabel({
  children,
  color = "var(--ink-faint)",
}: {
  children: React.ReactNode;
  color?: string;
}) {
  return (
    <span
      style={{
        fontFamily: mono,
        fontSize: 10,
        fontWeight: 800,
        letterSpacing: "0.6px",
        textTransform: "uppercase",
        color,
      }}
    >
      {children}
    </span>
  );
}

/** A hand-rolled sparkline (echoes `charts/Sparkline.astro`). Forest stroke = signal, not evidence. */
export function Sparkline({
  values,
  width = 140,
  height = 36,
}: {
  values: number[];
  width?: number;
  height?: number;
}) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const pts = values.map(
    (v, i) => `${(i * step).toFixed(1)},${(height - ((v - min) / span) * (height - 4) - 2).toFixed(1)}`,
  );
  const last = values[values.length - 1];
  const lx = (values.length - 1) * step;
  const ly = height - ((last - min) / span) * (height - 4) - 2;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="trend">
      <polyline
        points={pts.join(" ")}
        fill="none"
        stroke="var(--forest)"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={lx} cy={ly} r={2.5} fill="var(--forest)" />
    </svg>
  );
}

/** A hand-rolled bar chart (echoes `charts/BarChart.astro`). The highlighted bar reads forest. */
export function MiniBars({
  data,
  height = 120,
}: {
  data: { label: string; value: number; highlight?: boolean }[];
  height?: number;
}) {
  const max = Math.max(...data.map((d) => d.value)) || 1;
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height }}>
      {data.map((d) => (
        <div
          key={d.label}
          style={{
            flex: "1 1 0",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 4,
            height: "100%",
          }}
        >
          <div style={{ flex: 1, width: "100%", display: "flex", alignItems: "flex-end" }}>
            <div
              style={{
                width: "100%",
                height: `${Math.max(2, (d.value / max) * 100)}%`,
                background: d.highlight ? "var(--forest)" : "var(--data-2, var(--forest-line))",
              }}
              title={`${d.label}: ${d.value}`}
            />
          </div>
          <span style={{ fontFamily: mono, fontSize: 9.5, color: "var(--ink-faint)" }}>{d.label}</span>
        </div>
      ))}
    </div>
  );
}

/** A teardown annotation pin (echoes `AnnotationPin`) — a numbered beat marker. */
export function Pin({ n }: { n: number }) {
  return (
    <span
      style={{
        width: 18,
        height: 18,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: mono,
        fontSize: 10,
        fontWeight: 800,
        color: "var(--bone-surface)",
        background: "var(--ink)",
        flex: "0 0 auto",
      }}
    >
      {n}
    </span>
  );
}

/** A compact figure value (echoes `FigureStat` size="sm"): big value + unit + label + sub. */
export function FigureValue({
  label,
  value,
  unit,
  sub,
  evidence,
}: {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  evidence: EvidenceKind;
}) {
  return (
    <div style={{ minWidth: 120 }}>
      <div
        style={{
          fontFamily: mono,
          fontSize: 10,
          letterSpacing: "0.4px",
          textTransform: "uppercase",
          color: "var(--ink-faint)",
        }}
      >
        {label}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 5, margin: "3px 0 2px" }}>
        <span
          style={{
            fontFamily: sans,
            fontSize: 26,
            fontWeight: 800,
            letterSpacing: "-0.5px",
            color: "var(--ink)",
          }}
        >
          {value}
        </span>
        {unit && <span style={{ fontFamily: mono, fontSize: 11, color: "var(--ink-muted)" }}>{unit}</span>}
      </div>
      {sub && <div style={{ fontSize: 11.5, color: "var(--ink-faint)", marginBottom: 4 }}>{sub}</div>}
      <Ev kind={evidence} />
    </div>
  );
}

/** The card frame most atom treatments sit in — a hairline surface panel. */
export const cardFrame: CSSProperties = {
  border: "1px solid var(--line-hair)",
  background: "var(--bone-surface)",
  padding: "14px 16px",
};
