/**
 * StoryAtom (#1097) — the render slot for one cited catalog atom, resolved live against the fetched
 * render catalog. This is the closed dispatch table made concrete: every one of the 14 kinds routes
 * to exactly one treatment (record/doc, entity/person/place, timeline/meeting share a family and a
 * card, mirroring how the live site already shares `RecordBlock`/`ProfileHeader`/`Timeline`).
 *
 * Three states, always handled (never a broken card):
 *  - **resolved** — the live payload, echoing the kind's canonical on-site presentation at embedded
 *    scale;
 *  - **loading** — a quiet skeleton while the island resolves the handle against the catalog asset;
 *  - **dangling** — the handle no longer resolves; renders the write-time thin snapshot (kind +
 *    title) as a struck-through, labeled placeholder (chain of custody: the citation still shows
 *    where it stood).
 */
import type { CatalogKind } from "~/lib/catalog";
import { KIND_FAMILY, type HydratedAtom } from "~/lib/storyAtoms";
import { Ev, FigureValue, KindLabel, MiniBars, Pin, Sparkline, cardFrame, mono } from "./parts";

export interface StoryAtomProps {
  handle: string;
  /** The SDM thin snapshot (present even when the live payload doesn't resolve). */
  snapshotKind: CatalogKind;
  snapshotTitle: string;
  /** The live resolution, or null/undefined when the handle doesn't resolve (dangling). */
  atom?: HydratedAtom | null;
  loading?: boolean;
}

export default function StoryAtom({ handle, snapshotKind, snapshotTitle, atom, loading }: StoryAtomProps) {
  if (loading) return <AtomSkeleton />;
  if (!atom || atom.dangling) return <Dangling handle={handle} kind={snapshotKind} title={snapshotTitle} />;
  return <Resolved atom={atom} />;
}

// --- loading + dangling ---------------------------------------------------------------------
function AtomSkeleton() {
  const bar = (w: string, h: number, delay: number) => (
    <div
      className="wm-atom-pulse"
      style={{ height: h, width: w, background: "var(--bone-band)", animationDelay: `${delay}s` }}
    />
  );
  return (
    <div style={{ ...cardFrame, display: "flex", flexDirection: "column", gap: 8 }} aria-busy="true">
      {bar("120px", 10, 0)}
      {bar("70%", 16, 0.1)}
      {bar("44%", 10, 0.2)}
    </div>
  );
}

function Dangling({ handle, kind, title }: { handle: string; kind: CatalogKind; title: string }) {
  return (
    <div
      style={{
        border: "1px dashed var(--line-2)",
        background: "var(--bone-band)",
        padding: "14px 16px",
        display: "flex",
        gap: 12,
      }}
    >
      <span aria-hidden style={{ color: "var(--ink-ghost)", fontFamily: mono, flex: "0 0 auto" }}>
        ⛓
      </span>
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontFamily: mono,
            fontSize: 10,
            fontWeight: 800,
            letterSpacing: "0.6px",
            textTransform: "uppercase",
            color: "var(--ink-ghost)",
            marginBottom: 4,
          }}
        >
          {kind} · no longer resolves
        </div>
        <div
          style={{
            fontSize: 14.5,
            fontWeight: 600,
            color: "var(--ink-muted)",
            textDecoration: "line-through",
            textDecorationColor: "var(--ink-ghost)",
          }}
        >
          {title}
        </div>
        <div style={{ fontFamily: mono, fontSize: 11, color: "var(--ink-ghost)", marginTop: 5 }}>
          {handle} · showing the title captured when this was cited
        </div>
      </div>
    </div>
  );
}

// --- resolved: dispatch on family -----------------------------------------------------------
function Resolved({ atom }: { atom: HydratedAtom }) {
  switch (KIND_FAMILY[atom.kind]) {
    case "record":
      return <RecordCard atom={atom} />;
    case "profile":
      return <ProfileCard atom={atom} />;
    case "event":
      return <EventCard atom={atom} />;
    case "exhibit":
      return <ExhibitCard atom={atom} />;
    case "concept":
      return <ConceptCard atom={atom} />;
    case "lead":
      return <LeadCard atom={atom} />;
    case "dataset":
      return <DatasetCard atom={atom} />;
    case "teardown":
      return <TeardownCard atom={atom} />;
    case "chapter":
      return <ChapterCard atom={atom} />;
    case "figure":
      return <FigureCard atom={atom} />;
  }
}

/** A minimal card for a resolved atom that has no rich payload yet (thin hydration). */
function CompactCard({ atom }: { atom: HydratedAtom }) {
  return (
    <div style={cardFrame}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          marginBottom: 4,
        }}
      >
        <KindLabel>{atom.kindLabel}</KindLabel>
        <Ev kind={atom.evidence} />
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink)" }}>{atom.title}</div>
    </div>
  );
}

// record / doc
function RecordCard({ atom }: { atom: HydratedAtom }) {
  const r = atom.record;
  if (!r) return <CompactCard atom={atom} />;
  return (
    <div style={cardFrame}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          marginBottom: 8,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <KindLabel>{r.kind}</KindLabel>
          <span style={{ fontSize: 15.5, fontWeight: 700, color: "var(--ink)" }}>{r.title}</span>
        </div>
        <Ev kind={r.evidence} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 14, rowGap: 4 }}>
        {r.fields.map((f) => (
          <FieldRow key={f.label} label={f.label} value={f.value} />
        ))}
      </div>
      {(r.recordId || r.source) && (
        <div
          style={{
            marginTop: 10,
            paddingTop: 8,
            borderTop: "1px solid var(--line-faint)",
            fontFamily: mono,
            fontSize: 10.5,
            color: "var(--ink-faint)",
            display: "flex",
            gap: 10,
            flexWrap: "wrap",
          }}
        >
          {r.recordId && <span>{r.recordId}</span>}
          {r.source && (
            <span>
              {r.source.file} · {r.source.pages} · {r.source.collection}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function FieldRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <span
        style={{
          fontFamily: mono,
          fontSize: 11,
          color: "var(--ink-faint)",
          letterSpacing: "0.3px",
          textTransform: "uppercase",
        }}
      >
        {label}
      </span>
      <span style={{ fontSize: 13.5, color: "var(--ink-prose)" }}>{value}</span>
    </>
  );
}

// entity / person / place
function ProfileCard({ atom }: { atom: HydratedAtom }) {
  const p = atom.profile;
  if (!p) return <CompactCard atom={atom} />;
  return (
    <div style={cardFrame}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          marginBottom: 5,
        }}
      >
        <KindLabel>{p.kindLabel}</KindLabel>
        <Ev kind={p.evidence} />
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-0.3px", color: "var(--ink)" }}>
          {p.name}
        </span>
        {p.variants?.map((v) => (
          <span key={v} style={{ fontFamily: mono, fontSize: 11, color: "var(--ink-faint)" }}>
            a.k.a. {v}
          </span>
        ))}
      </div>
      {p.descriptor && (
        <div style={{ fontSize: 13.5, lineHeight: 1.5, color: "var(--ink-prose)", marginTop: 5 }}>
          {p.descriptor}
        </div>
      )}
    </div>
  );
}

// timeline / meeting
function EventCard({ atom }: { atom: HydratedAtom }) {
  const e = atom.event;
  if (!e) return <CompactCard atom={atom} />;
  return (
    <div style={{ ...cardFrame, borderLeft: "3px solid var(--forest)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap", marginBottom: 4 }}>
        <span style={{ fontFamily: mono, fontSize: 11.5, fontWeight: 700, color: "var(--ink-muted)" }}>
          {e.date}
        </span>
        <Ev kind={e.evidence} bracket />
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink)" }}>{e.title}</div>
      {e.summary && (
        <div style={{ fontSize: 12.5, color: "var(--ink-muted)", lineHeight: 1.45, marginTop: 3 }}>
          {e.summary}
        </div>
      )}
      {e.connect && e.connect.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
          {e.connect.map((c) => (
            <span
              key={c.label}
              style={{
                fontFamily: mono,
                fontSize: 10.5,
                color: "var(--forest)",
                background: "var(--forest-tint)",
                border: "1px solid var(--forest-line)",
                padding: "2px 7px",
              }}
            >
              {c.kind} · {c.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// exhibit
function ExhibitCard({ atom }: { atom: HydratedAtom }) {
  const s = atom.source;
  if (!s) return <CompactCard atom={atom} />;
  return (
    <div style={cardFrame}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <KindLabel>{atom.kindLabel}</KindLabel>
        {s.badge && (
          <span
            style={{
              fontFamily: mono,
              fontSize: 9,
              fontWeight: 800,
              letterSpacing: "0.6px",
              color: "var(--bone-surface)",
              background: "var(--ink)",
              padding: "1px 6px",
            }}
          >
            {s.badge}
          </span>
        )}
      </div>
      <div
        style={{ border: "1px solid var(--line-hair)", background: "var(--bone-sunk)", padding: "10px 12px" }}
      >
        <div style={{ fontFamily: mono, fontSize: 12, fontWeight: 700, color: "var(--ink)" }}>{s.file}</div>
        <div style={{ fontFamily: mono, fontSize: 10.5, color: "var(--ink-faint)", marginTop: 2 }}>
          {s.pages} · {s.collection}
        </div>
        {s.fields && s.fields.length > 0 && (
          <div
            style={{
              marginTop: 8,
              display: "grid",
              gridTemplateColumns: "auto 1fr",
              columnGap: 12,
              rowGap: 3,
            }}
          >
            {s.fields.map((f) => (
              <FieldRow key={f.label} label={f.label} value={f.value} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// concept — a new composition (no canonical on-site component); built from Eyebrow + EvidenceTag.
function ConceptCard({ atom }: { atom: HydratedAtom }) {
  const c = atom.concept;
  if (!c) return <CompactCard atom={atom} />;
  return (
    <div
      style={{
        border: "1px solid var(--forest-line)",
        background: "var(--forest-tint)",
        padding: "14px 16px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          marginBottom: 6,
        }}
      >
        <KindLabel color="#3a4a3e">Concept</KindLabel>
        <Ev kind={c.evidence} />
      </div>
      <div
        style={{ fontFamily: mono, fontSize: 16, fontWeight: 700, color: "var(--forest)", marginBottom: 4 }}
      >
        {c.term}
      </div>
      <div style={{ fontSize: 13.5, lineHeight: 1.5, color: "var(--ink-prose)" }}>{c.descriptor}</div>
    </div>
  );
}

// lead
function LeadCard({ atom }: { atom: HydratedAtom }) {
  const l = atom.lead;
  if (!l) return <CompactCard atom={atom} />;
  return (
    <div style={{ ...cardFrame, borderLeft: "3px solid var(--ev-open-border)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
        <KindLabel color="var(--ev-open-fg)">
          {l.kind} · {l.confidence}
        </KindLabel>
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink)" }}>{l.title}</div>
      <div style={{ fontSize: 13, color: "var(--ink-muted)", lineHeight: 1.45, marginTop: 4 }}>
        {l.detail}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          marginTop: 10,
        }}
      >
        {l.action && (
          <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--forest)" }}>{l.action} ›</span>
        )}
        {l.count && (
          <span style={{ fontFamily: mono, fontSize: 10.5, color: "var(--ink-faint)" }}>{l.count}</span>
        )}
      </div>
    </div>
  );
}

// dataset
function DatasetCard({ atom }: { atom: HydratedAtom }) {
  const d = atom.dataset;
  if (!d) return <CompactCard atom={atom} />;
  return (
    <div style={cardFrame}>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <FigureValue label={d.label} value={d.value} unit={d.unit} sub={d.sub} evidence={d.evidence} />
        <div style={{ flex: "1 1 200px", minWidth: 180 }}>
          <MiniBars data={d.bars} height={110} />
        </div>
      </div>
    </div>
  );
}

// teardown — a new composition: beat pins + a link-out to the full Record Screen.
function TeardownCard({ atom }: { atom: HydratedAtom }) {
  const t = atom.teardown;
  if (!t) return <CompactCard atom={atom} />;
  return (
    <div style={{ ...cardFrame, borderColor: "var(--ink)", display: "flex", alignItems: "center", gap: 14 }}>
      <div style={{ display: "flex", gap: 3, flex: "0 0 auto" }}>
        {Array.from({ length: t.beats }, (_, i) => (
          <Pin key={i} n={i + 1} />
        ))}
      </div>
      <div style={{ flex: "1 1 auto", minWidth: 0 }}>
        <KindLabel color="var(--forest)">{atom.kindLabel}</KindLabel>
        <div style={{ fontSize: 15, fontWeight: 700, margin: "2px 0", color: "var(--ink)" }}>{t.title}</div>
        <div style={{ fontSize: 12.5, color: "var(--ink-muted)" }}>{t.headline}</div>
      </div>
      <span
        style={{
          flex: "0 0 auto",
          fontSize: 12.5,
          color: "var(--forest)",
          fontWeight: 700,
          whiteSpace: "nowrap",
        }}
      >
        Open teardown ›
      </span>
    </div>
  );
}

// chapter — a new composition mirroring the Hypotheses lens card, scaled down.
function ChapterCard({ atom }: { atom: HydratedAtom }) {
  const c = atom.chapter;
  if (!c) return <CompactCard atom={atom} />;
  return (
    <div style={{ ...cardFrame, display: "flex", alignItems: "center", gap: 12 }}>
      <span
        style={{
          fontFamily: mono,
          fontSize: 12,
          fontWeight: 800,
          color: "var(--bone-surface)",
          background: "var(--forest)",
          padding: "4px 9px",
          flex: "0 0 auto",
        }}
      >
        {c.n}
      </span>
      <div style={{ flex: "1 1 auto", minWidth: 0 }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink)" }}>{c.name}</div>
        <div style={{ fontSize: 13, color: "var(--ink-muted)", marginTop: 2 }}>{c.claim}</div>
      </div>
      <span
        style={{
          flex: "0 0 auto",
          fontFamily: mono,
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.4px",
          textTransform: "uppercase",
          color: "var(--forest)",
          background: "var(--forest-tint)",
          border: "1px solid var(--forest-line)",
          padding: "3px 8px",
          whiteSpace: "nowrap",
        }}
      >
        {c.status}
      </span>
    </div>
  );
}

// figure — a deck.gl figure grabbed as a whole widget (never per-scalar).
function FigureCard({ atom }: { atom: HydratedAtom }) {
  const f = atom.figure;
  if (!f) return <CompactCard atom={atom} />;
  return (
    <div style={{ ...cardFrame, display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
      <FigureValue label={f.label} value={f.value} unit={f.unit} sub={f.sub} evidence={atom.evidence} />
      <Sparkline values={f.spark} width={140} height={36} />
      <span style={{ marginLeft: "auto", fontFamily: mono, fontSize: 10.5, color: "var(--ink-faint)" }}>
        deck.gl figure · embedded whole
      </span>
    </div>
  );
}
