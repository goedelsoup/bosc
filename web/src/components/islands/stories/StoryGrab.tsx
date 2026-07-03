/**
 * The grab affordance (#1096) — how a reader pulls an atom into a Story-in-progress *while reading
 * ordinary site content*. The affordance rides on top of the content (a record card, a timeline row,
 * a figure widget); grabbing never navigates away — it drops a thin snapshot into the persistent,
 * non-modal Story tray (`./tray`, sessionStorage), which the editor then seeds from.
 *
 * `GrabPin` is the reusable primitive (default / hover / grabbed / ungrabbable). This module's
 * default export is the standalone demo host that mirrors the design: a grabbable record + timeline
 * (one event ungrabbable — no stable ref) + a figure (grabbed as a whole widget), a state legend, and
 * the live tray. It doubles as the integration reference for wiring pins onto real content pages.
 */
import { useState } from "react";
import { FIXTURE_CATALOG } from "~/lib/storyAtoms.fixture";
import StoryAtom from "./StoryAtom";
import { Ev, mono } from "./parts";
import { type TrayItem, readTray, toggleTray } from "./tray";

// --- the reusable pin -----------------------------------------------------------------------
export function GrabPin({
  grabbed,
  ungrabbable,
  onToggle,
  label,
}: {
  grabbed: boolean;
  ungrabbable?: boolean;
  onToggle?: () => void;
  label?: string;
}) {
  const [hover, setHover] = useState(false);
  if (ungrabbable) {
    return (
      <span
        title="No stable reference yet — this can't be cited"
        style={{
          width: 28,
          height: 28,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          border: "1.5px dashed var(--line-2)",
          color: "var(--ink-ghost)",
          cursor: "not-allowed",
        }}
      >
        +
      </span>
    );
  }
  const bg = grabbed ? "var(--forest)" : hover ? "var(--forest-tint)" : "var(--bone-surface)";
  const bd = grabbed || hover ? "var(--forest)" : "var(--line-2)";
  const fg = grabbed ? "var(--bone-surface)" : hover ? "var(--forest)" : "var(--ink-muted)";
  return (
    <button
      type="button"
      onClick={onToggle}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      aria-pressed={grabbed}
      aria-label={grabbed ? `Remove ${label ?? "atom"} from story` : `Grab ${label ?? "atom"} into story`}
      style={{
        width: 28,
        height: 28,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        border: `1.5px solid ${bd}`,
        background: bg,
        color: fg,
        cursor: "pointer",
        transition: "background var(--dur) var(--ease), border-color var(--dur) var(--ease)",
      }}
    >
      {grabbed ? "✓" : "+"}
    </button>
  );
}

// --- the demo host --------------------------------------------------------------------------
const DEED = FIXTURE_CATALOG["record:lima:deed-0008300"];
const CLEARING = FIXTURE_CATALOG["timeline:lima:site-clearing"];
const FIGURE = FIXTURE_CATALOG["figure:lima:dilution-curve"];

const grab = (a: { handle: string; kind: TrayItem["kind"]; title: string }): TrayItem => ({
  handle: a.handle,
  kind: a.kind,
  title: a.title,
});

const GRABBABLE: Record<string, TrayItem> = {
  deed: grab(DEED),
  // e1 has no separate fixture atom (the shared catalog models one timeline event); it's a demo-only
  // row, so it carries an inline snapshot rather than a resolved catalog handle.
  e1: { handle: "timeline:lima:deed-recorded", kind: "timeline", title: "Seven-parcel deed recorded" },
  e2: grab(CLEARING),
  figure: grab(FIGURE),
};

export default function StoryGrab({ composeHref = "#" }: { composeHref?: string }) {
  const [tray, setTray] = useState<TrayItem[]>(() => (typeof window === "undefined" ? [] : readTray()));
  const grabbed = (handle: string) => tray.some((t) => t.handle === handle);
  const toggle = (item: TrayItem) => setTray(toggleTray(item));

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", paddingBottom: 100 }}>
      <div
        style={{
          fontFamily: mono,
          fontSize: 11,
          fontWeight: 800,
          letterSpacing: "1px",
          textTransform: "uppercase",
          color: "var(--forest)",
          marginBottom: 6,
        }}
      >
        Record · deed
      </div>
      <h1
        style={{
          fontFamily: "var(--font-sans)",
          fontWeight: 800,
          fontSize: 30,
          letterSpacing: "-0.6px",
          margin: "0 0 4px",
          color: "var(--ink)",
        }}
      >
        Limited Warranty Deed
      </h1>
      <p
        style={{
          fontSize: 14.5,
          color: "var(--ink-muted)",
          lineHeight: 1.5,
          maxWidth: 620,
          margin: "0 0 26px",
        }}
      >
        Ordinary site content, unchanged — the grab affordance rides on top of it. Grabbing never navigates
        away; it drops the atom into the Story tray at the bottom of the screen.
      </p>

      {/* ① a record, grabbable */}
      <section style={{ position: "relative", marginBottom: 34 }}>
        <StoryAtom handle={DEED.handle} snapshotKind={DEED.kind} snapshotTitle={DEED.title} atom={DEED} />
        <div
          style={{ position: "absolute", top: 14, right: 16, display: "flex", alignItems: "center", gap: 8 }}
        >
          {!grabbed(DEED.handle) && (
            <span
              style={{
                fontFamily: mono,
                fontSize: 9.5,
                fontWeight: 700,
                letterSpacing: "0.4px",
                textTransform: "uppercase",
                color: "var(--ink-faint)",
              }}
            >
              grab this record
            </span>
          )}
          <GrabPin
            grabbed={grabbed(DEED.handle)}
            onToggle={() => toggle(GRABBABLE.deed)}
            label={DEED.title}
          />
        </div>
      </section>

      {/* ② a timeline — two grabbable, one ungrabbable (no stable ref) */}
      <section style={{ marginBottom: 34 }}>
        <div
          style={{
            fontFamily: mono,
            fontSize: 11,
            letterSpacing: "1px",
            textTransform: "uppercase",
            color: "var(--ink-faint)",
            fontWeight: 700,
            marginBottom: 12,
          }}
        >
          The record · chronology
        </div>
        <EventRow
          date="2025-08-13"
          evidence="verified"
          title="Seven-parcel deed recorded"
          detail="Brenneman Trusts → Bistrozzi LLC, 340.2 ac."
          grabbed={grabbed(GRABBABLE.e1.handle)}
          onToggle={() => toggle(GRABBABLE.e1)}
        />
        <EventRow
          date="2025-03-11"
          evidence="verified"
          title="Site clearing begins"
          detail="Clearing starts before the water permit is public."
          grabbed={grabbed(GRABBABLE.e2.handle)}
          onToggle={() => toggle(GRABBABLE.e2)}
        />
        <EventRow
          date="2025 · undated"
          evidence="open"
          title="A neighbor recalls survey stakes appearing"
          detail="An oral account, not yet tied to a filed record."
          ungrabbable
          note="no stable reference yet — this event can't be cited until it does"
        />
      </section>

      {/* ③ a figure, grabbed as a whole widget */}
      <section style={{ position: "relative", marginBottom: 34 }}>
        <StoryAtom
          handle={FIGURE.handle}
          snapshotKind={FIGURE.kind}
          snapshotTitle={FIGURE.title}
          atom={FIGURE}
        />
        <div style={{ position: "absolute", top: 14, right: 16 }}>
          <GrabPin
            grabbed={grabbed(FIGURE.handle)}
            onToggle={() => toggle(GRABBABLE.figure)}
            label={FIGURE.title}
          />
        </div>
        <div style={{ fontSize: 11.5, color: "var(--ink-faint)", marginTop: 8 }}>
          A figure grabs as a whole widget — never a single scalar off of it.
        </div>
      </section>

      <Legend />
      <StoryTray tray={tray} composeHref={composeHref} />
    </div>
  );
}

function EventRow({
  date,
  evidence,
  title,
  detail,
  grabbed,
  onToggle,
  ungrabbable,
  note,
}: {
  date: string;
  evidence: "verified" | "open";
  title: string;
  detail: string;
  grabbed?: boolean;
  onToggle?: () => void;
  ungrabbable?: boolean;
  note?: string;
}) {
  return (
    <div style={{ position: "relative", display: "flex", marginBottom: 10 }}>
      <div
        style={{
          flex: "1 1 auto",
          minWidth: 0,
          background: "var(--bone-surface)",
          border: "1px solid var(--line-hair)",
          borderLeft: `3px solid ${ungrabbable ? "var(--ink-ghost)" : "var(--forest)"}`,
          padding: "12px 48px 12px 14px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap", marginBottom: 4 }}>
          <span style={{ fontFamily: mono, fontSize: 11.5, fontWeight: 700, color: "var(--ink-muted)" }}>
            {date}
          </span>
          <Ev kind={evidence} bracket />
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink)" }}>{title}</div>
        <div style={{ fontSize: 12.5, color: "var(--ink-muted)", lineHeight: 1.4, marginTop: 3 }}>
          {detail}
        </div>
        {note && <div style={{ fontSize: 11, color: "var(--ink-ghost)", marginTop: 7 }}>{note}</div>}
      </div>
      <div style={{ position: "absolute", top: 11, right: 12 }}>
        <GrabPin grabbed={!!grabbed} onToggle={onToggle} ungrabbable={ungrabbable} label={title} />
      </div>
    </div>
  );
}

function Legend() {
  const cell = (border: string, bg: string, fg: string, glyph: string, label: string, dashed = false) => (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      <span
        style={{
          width: 30,
          height: 30,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: `1.5px ${dashed ? "dashed" : "solid"} ${border}`,
          background: bg,
          color: fg,
        }}
      >
        {glyph}
      </span>
      <span style={{ fontSize: 11, color: "var(--ink-muted)" }}>{label}</span>
    </div>
  );
  return (
    <div style={{ marginTop: 44, paddingTop: 24, borderTop: "1px solid var(--line-hair)" }}>
      <div
        style={{
          fontFamily: mono,
          fontSize: 11,
          letterSpacing: "1px",
          textTransform: "uppercase",
          color: "var(--ink-faint)",
          fontWeight: 700,
          marginBottom: 14,
        }}
      >
        The affordance, every state
      </div>
      <div style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
        {cell("var(--line-2)", "var(--bone-surface)", "var(--ink-muted)", "+", "default")}
        {cell("var(--forest)", "var(--forest-tint)", "var(--forest)", "+", "hover")}
        {cell("var(--forest)", "var(--forest)", "var(--bone-surface)", "✓", "grabbed")}
        {cell("var(--line-2)", "transparent", "var(--ink-ghost)", "+", "ungrabbable", true)}
      </div>
    </div>
  );
}

// --- the persistent tray --------------------------------------------------------------------
export function StoryTray({ tray, composeHref = "#" }: { tray: TrayItem[]; composeHref?: string }) {
  const has = tray.length > 0;
  return (
    <div
      style={{
        position: "fixed",
        left: 0,
        right: 0,
        bottom: 0,
        background: "var(--ink)",
        color: "var(--bone-surface)",
        padding: "13px 32px",
        display: "flex",
        alignItems: "center",
        gap: 16,
        zIndex: 40,
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          background: has ? "var(--forest-on-ink)" : "var(--ink-ghost)",
          flex: "0 0 auto",
        }}
      />
      <div style={{ fontSize: 13.5, fontWeight: 600 }}>
        Story in progress · <span style={{ fontFamily: mono }}>{tray.length}</span> grabbed
      </div>
      <div style={{ display: "flex", gap: 6, flex: "1 1 auto", overflow: "hidden" }}>
        {tray.map((t) => (
          <span
            key={t.handle}
            style={{
              fontFamily: mono,
              fontSize: 10.5,
              color: "var(--forest-on-ink)",
              background: "rgba(255,255,255,0.1)",
              padding: "3px 9px",
              whiteSpace: "nowrap",
            }}
          >
            {t.title}
          </span>
        ))}
      </div>
      {has ? (
        <a
          href={composeHref}
          style={{
            flex: "0 0 auto",
            fontSize: 13,
            fontWeight: 700,
            color: "var(--bone-surface)",
            background: "var(--forest)",
            padding: "8px 16px",
            textDecoration: "none",
          }}
        >
          Open in editor →
        </a>
      ) : (
        // Empty tray: a non-link (no href, out of tab order, not announced as actionable) rather than
        // a visually-disabled anchor that stays keyboard-focusable.
        <span
          aria-disabled="true"
          style={{
            flex: "0 0 auto",
            fontSize: 13,
            fontWeight: 700,
            color: "var(--bone-surface)",
            background: "var(--forest)",
            padding: "8px 16px",
            opacity: 0.5,
            cursor: "default",
          }}
        >
          Open in editor →
        </span>
      )}
    </div>
  );
}
