// Watermark — a record screen (the Record Teardown). Mirrors the shipped `RecordTeardown.astro`
// (rendered by `…/site/records/[group]/[id].astro`): one data-driven teardown bound to the live
// content bundle, in five beats — ① source ② what we read ③ what it reveals ④ how to check
// ⑤ where it connects — rendered in any of THREE layouts (split / scroll / annotated), with a
// "● in the published bundle" badge when the record resolves against the bundle, and numbered
// margin pins on the annotated layout.
//
// FEATURE FLAG `teaching` (default OFF → exactly what ships: one record, the 5-beat scroll-spy
// rail, no type switcher). Flipped ON, the left rail adds the Cost · Air · NPDES record-type
// switcher — a TEACHING device (one screen showing the evidence grammar across record types).
// The per-record page never shows this switcher; the teaching intent now has its own live home:
// the "How to read any record" explainer at …/site/records/how-to-read (#697, built on the real
// OPC/AIR/NPDES teardowns). The canvas toggle previews both states.
function RecordScreen({ onBack, onOpenProfile, teaching = false }) {
  const { Eyebrow, EvidenceTag, FigureStat, SourceCard, ConnectChip, AnnotationPin, Button } = window.WatermarkDesignSystem_dbe30a;
  const [teach, setTeach] = React.useState(teaching);
  const [variant, setVariant] = React.useState("cost");
  const [layout, setLayout] = React.useState("split");

  const VARIANTS = {
    cost: {
      tab: "Cost estimate", eyebrow: "Record · cost estimate", title: "Opinion of Probable Cost",
      meta: "Tetra Tech · BOSC Roadwork · filed 2025-07-11", inBundle: true,
      source: { file: "PRR-01-bundle.pdf", badge: "SCAN", pages: "pp. 317–328", collection: "Public Records Request 01" },
      read: [
        ["Program total", "$14,223,081", "verified"], ["Sub-estimates", "6 corridors", "verified"],
        ["Contingency", "25%", "verified"], ["Largest — Cole St", "$3,899,800", "verified"],
        ["Drainage line", "$1,068,530 · 7.5%", "inference"], ["Design-storm basis", "~ not cited", "open"],
        ["Detention shown", "~ none", "open"],
      ],
      figures: [],
      reveals: ["The public's road package is priced to the dollar — ", { b: "$14,223,081" }, " — yet drainage is just 7.5% of it, the only one of six items detailed, with no design-storm basis and no detention shown. A number that precise on a scope this thin is the tell."],
      check: [["verified", "totals"], ["↗", "Open exhibit · pp. 317–328"], ["→", "Read the extraction method"]],
      gaps: null,
      connect: [["entity", "Tetra Tech", true], ["timeline", "2025 · CRA filed", false], ["concept", "[[roadwork-development-agreement]]", false], ["map", "roundabout layer", false]],
    },
    air: {
      tab: "Air permit", eyebrow: "Record · air permit-to-install", title: "Air Permit-to-Install P0138965",
      meta: "Ohio EPA · 115 emissions units · finalized 2026-05-28", inBundle: true,
      source: { file: "OEPA_PTI_P0138965.pdf", badge: "CBI", pages: "§ B.1 emissions table", collection: "Ohio EPA · public notice" },
      read: [
        ["Emissions units", "115", "verified"], ["Matched groups", "3 × identical", "verified"],
        ["Per-engine power", "▮▮▮ CBI", "gap"], ["Total backup power", "~ 313 MW", "inference"],
        ["Annual run hours", "▮▮▮ CBI", "gap"], ["NOₓ basis", "draft only", "open"],
      ],
      figures: [
        { label: "Backup generation", value: "~313", unit: "MW (modeled)", evidence: "inference", basis: "modeled", sub: "114 data-hall units × draft per-engine kW", warn: true },
      ],
      reveals: ["The final permit lists ", { b: "115 emissions units" }, " (114 data-hall generators + 1 HUBGEN) in three matched groups, but knocks out per-engine power and run hours as confidential business information. The ~313 MW total survives only because the ", { b: "draft" }, " carried the figure before it was redacted — the record reassembles what the final filing hid."],
      check: [["verified", "unit count"], ["↗", "Open permit · OEPA"], ["→", "Compare draft vs. final"]],
      gaps: ["Per-engine power and run hours are claimed as CBI in the final permit — shown here as redaction bars, not omitted. The modeled total is labeled inference until the draft figure is independently confirmed."],
      connect: [["record", "Draft PTI · pre-redaction", false], ["concept", "[[CBI-redaction]]", false], ["measure", "313 MW · power", false], ["timeline", "2026-05-28 · finalized", false]],
    },
    water: {
      tab: "NPDES · water", eyebrow: "Record · NPDES discharge permit", title: "Cooling-water screen — Ottawa River",
      meta: "NPDES + USGS 04187100 · the 7Q10 low-flow test", inBundle: false,
      source: { file: "NPDES_OH_cooling.pdf", badge: "SCAN", pages: "outfall 001 · cooling", collection: "Ohio EPA · NPDES file" },
      read: [
        ["Consumptive draw", "4.85 cfs", "inference"], ["Design low flow (7Q10)", "0.2 cfs", "verified"],
        ["Intake of record", "~ not named", "open"], ["Dilution at 7Q10", "below 1:1", "inference"],
        ["Thermal limit", "draft only", "open"],
      ],
      figures: [
        { label: "Cooling draw ÷ 7Q10", value: "24.3×", unit: "design low flow", evidence: "inference", basis: "modeled", sub: "4.85 cfs consumptive ÷ 0.2 cfs", warn: true },
        { label: "Design low flow · 7Q10", value: "0.2", unit: "cfs", evidence: "verified", basis: "grounded", sub: "USGS 04187100 gage" },
      ],
      reveals: ["At the river's ", { b: "design low flow of 0.2 cfs" }, ", the modeled consumptive draw is ", { b: "24.3× the whole stream" }, ". The permit never names the intake of record, so the screen is built from the gage and the draft — the figure the record keeps trying to make thin."],
      check: [["verified", "7Q10 gage"], ["↗", "Open USGS 04187100"], ["→", "Read the dilution method"]],
      gaps: ["The intake of record isn't named in the NPDES file; the draw is modeled from the draft permit. The 24.3× ratio is inference until the operator's own withdrawal figure is on the record."],
      connect: [["concept", "[[7Q10]]", false], ["place", "Ottawa River", false], ["measure", "4.85 cfs · discharge", false], ["entity", "USGS", false]],
    },
  };

  const v = teach ? VARIANTS[variant] : VARIANTS.cost;
  // The five beats, in impl order (① source ② read ③ reveals ④ check ⑤ connects) — the rail's
  // scroll-spy targets + the annotated layout's margin pins.
  const BEATS = [["①", "The source"], ["②", "What we read"], ["③", "What it reveals"], ["④", "How to check"], ["⑤", "Where it connects"]];
  const LAYOUTS = [["split", "Split"], ["scroll", "Scroll"], ["annotated", "Annotated"]];

  const mono11 = { fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "1px", textTransform: "uppercase", color: "var(--ink-faint)" };
  const beatHead = (n, label) => (
    <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 10 }}><AnnotationPin n={n} size={20} /><span style={mono11}>{label}</span></div>
  );

  // --- the five beats as reusable blocks -------------------------------------------------------
  const SourceBeat = () => (
    <div>{beatHead("①", "The source")}<SourceCard file={v.source.file} badge={v.source.badge} pages={v.source.pages} collection={v.source.collection} style={{ maxWidth: "100%" }} /></div>
  );
  const ReadBeat = () => (
    <div>{beatHead("②", "What we read from it")}
      <div style={{ border: "1px solid var(--line-hair)", background: "var(--surface-card)" }}>
        {v.read.map(([label, value, ev], i) => (
          <div key={label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, padding: "8px 13px", borderBottom: i < v.read.length - 1 ? "1px solid var(--line-faint)" : "none" }}>
            <span style={{ fontSize: 13, color: "var(--ink-muted)" }}>{label}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {ev !== "verified" ? <EvidenceTag kind={ev} size="sm" /> : null}
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600, color: (ev === "open" || ev === "gap") ? "var(--ev-gap-fg)" : "var(--ink)" }}>{value}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
  const Figures = () => v.figures.length ? (
    <div style={{ display: "grid", gridTemplateColumns: v.figures.length > 1 ? "1fr 1fr" : "1fr", gap: 14 }}>{v.figures.map((f, i) => <FigureStat key={i} {...f} />)}</div>
  ) : null;
  const RevealsBeat = () => (
    <div style={{ border: "1px solid var(--line-hair)", background: "var(--surface-card)", padding: "16px 18px" }}>{beatHead("③", "What it reveals")}
      <div style={{ fontSize: 15, lineHeight: 1.55, color: "var(--ink-prose)" }}>
        {v.reveals.map((seg, i) => typeof seg === "string" ? <React.Fragment key={i}>{seg}</React.Fragment> : <b key={i} style={{ fontFamily: "var(--font-mono)" }}>{seg.b}</b>)}
      </div>
    </div>
  );
  const CheckBeat = () => (
    <div style={{ border: "1px solid var(--line-hair)", background: "var(--bone-sunk)", padding: "16px 18px" }}>{beatHead("④", "How to check it")}
      <div style={{ display: "flex", flexDirection: "column", gap: 9, fontSize: 13.5 }}>
        {v.check.map(([mark, text], i) => (
          mark === "verified"
            ? <span key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}><EvidenceTag kind="verified" brackets size="sm" /> {text}</span>
            : <a key={i} style={{ color: mark === "↗" ? "var(--forest)" : "var(--ink-muted)", textDecoration: "none", fontWeight: mark === "↗" ? 600 : 400, cursor: "pointer" }}>{mark} {text}</a>
        ))}
      </div>
    </div>
  );
  const GapsBeat = () => v.gaps ? (
    <div style={{ border: "1px solid var(--ev-gap-border)", background: "var(--ev-gap-bg)", padding: "13px 16px" }}>
      <div style={{ fontSize: 11, letterSpacing: "0.8px", textTransform: "uppercase", color: "var(--ev-gap-fg)", fontWeight: 700, marginBottom: 5 }}>⚠ Gaps in the record</div>
      {v.gaps.map((g, i) => <div key={i} style={{ fontSize: 13.5, color: "#6a3b34", lineHeight: 1.5 }}>{g}</div>)}
    </div>
  ) : null;
  const ConnectsBeat = () => (
    <div>{beatHead("⑤", "Where it connects")}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {v.connect.map(([kind, label, isEntity], i) => (
          <ConnectChip key={i} kind={kind} tone={kind === "map" || kind === "measure" ? "neutral" : "forest"} onClick={isEntity ? onOpenProfile : undefined}>{label}</ConnectChip>
        ))}
      </div>
    </div>
  );

  // --- the three layouts -----------------------------------------------------------------------
  const body = () => {
    if (layout === "scroll") {
      // Vertical scrollytelling — every beat full-width, in order (also the small-screen reflow).
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: 18, maxWidth: 640 }}>
          <SourceBeat /><ReadBeat /><Figures /><RevealsBeat /><CheckBeat /><GapsBeat /><ConnectsBeat />
        </div>
      );
    }
    if (layout === "annotated") {
      // Numbered margin pins keyed to the beats (redaction-heavy records).
      return (
        <div style={{ display: "grid", gridTemplateColumns: "44px 1fr", gap: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 26, paddingTop: 4 }}>
            {BEATS.map(([n]) => <AnnotationPin key={n} n={n} size={26} />)}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <SourceBeat /><ReadBeat /><Figures /><RevealsBeat /><CheckBeat /><GapsBeat /><ConnectsBeat />
          </div>
        </div>
      );
    }
    // split (default) — source ↔ read across the gutter, then reveals ↔ check.
    return (
      <>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}><SourceBeat /><ReadBeat /></div>
        {v.figures.length ? <div style={{ marginTop: 18 }}><Figures /></div> : null}
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 18, marginTop: 22 }}><RevealsBeat /><CheckBeat /></div>
        {v.gaps ? <div style={{ marginTop: 18 }}><GapsBeat /></div> : null}
        <div style={{ marginTop: 22 }}><ConnectsBeat /></div>
      </>
    );
  };

  return (
    <div style={{ color: "var(--ink)", display: "grid", gridTemplateColumns: "210px 1fr", gap: 0 }}>
      {/* rail — the 5-beat scroll-spy (ships); the record-type switcher is flag-gated (comp-only) */}
      <aside style={{ borderRight: "1px solid var(--line-hair)", padding: "26px 18px", background: "var(--bone-raised)" }}>
        <a onClick={onBack} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, fontWeight: 600, color: "var(--forest)", textDecoration: "none", marginBottom: 18, cursor: "pointer" }}>← The record</a>
        <Eyebrow tone="faint" style={{ marginBottom: 10 }}>On this record</Eyebrow>
        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          {BEATS.map(([mark, label], i) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 9px", background: i === 0 ? "var(--forest-tint)" : "transparent", cursor: "pointer" }}>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600, color: i === 0 ? "var(--forest)" : "var(--ink-ghost)", width: 14, textAlign: "center" }}>{mark}</span>
              <span style={{ fontSize: 12.5, color: i === 0 ? "var(--ink)" : "var(--ink-muted)", fontWeight: i === 0 ? 700 : 400 }}>{label}</span>
            </div>
          ))}
        </div>

        {teach && (
          <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px dashed var(--line-2)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 9 }}>
              <Eyebrow tone="faint" style={{ margin: 0 }}>Record type</Eyebrow>
              <span title="Comp-only teaching device — the shipped page renders one record per page and never shows this switcher." style={{ fontFamily: "var(--font-mono)", fontSize: 9, fontWeight: 700, letterSpacing: "0.5px", color: "var(--ev-inference-fg)", background: "var(--ev-inference-bg)", padding: "1px 5px" }}>⚑ COMP-ONLY</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {Object.entries(VARIANTS).map(([k, vv]) => {
                const on = variant === k;
                return (
                  <span key={k} onClick={() => setVariant(k)} style={{ fontSize: 12.5, fontWeight: on ? 700 : 500, color: on ? "var(--ink)" : "var(--ink-muted)", background: on ? "var(--surface-card)" : "transparent", border: `1px solid ${on ? "var(--line-2)" : "transparent"}`, padding: "6px 9px", cursor: "pointer" }}>{vv.tab}</span>
                );
              })}
            </div>
          </div>
        )}
      </aside>

      {/* body */}
      <div style={{ padding: "28px 32px 36px" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <div>
            <Eyebrow tone="forest">{v.eyebrow}</Eyebrow>
            <h2 style={{ fontSize: 28, fontWeight: 800, letterSpacing: "-0.6px", margin: "6px 0 3px" }}>{v.title}</h2>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--ink-faint)" }}>{v.meta}</div>
            {v.inBundle && (
              <a href="#" title="This record is in the published content bundle — the same row the library renders." style={{ display: "inline-flex", alignItems: "center", gap: 6, marginTop: 8, fontSize: 11.5, fontWeight: 700, color: "var(--forest)", textDecoration: "none" }}><span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--forest)" }} />in the published bundle</a>
            )}
          </div>
          {/* layout switch (ships — the page renders all three; a toggle previews each on canvas) */}
          <div style={{ display: "flex", gap: 1, border: "1px solid var(--line-2)" }}>
            {LAYOUTS.map(([k, label]) => {
              const on = layout === k;
              return <span key={k} onClick={() => setLayout(k)} style={{ fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.4px", textTransform: "uppercase", fontWeight: 600, color: on ? "#f5f2ea" : "var(--ink-muted)", background: on ? "var(--ink)" : "transparent", padding: "5px 11px", cursor: "pointer" }}>{label}</span>;
            })}
          </div>
        </div>

        <div style={{ marginTop: 22 }}>{body()}</div>

        <div style={{ marginTop: 26, paddingTop: 18, borderTop: "1px solid var(--line-faint)", display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.5px", textTransform: "uppercase", color: "var(--ink)", border: "1px solid var(--ink)", padding: "4px 11px" }}><span style={{ width: 7, height: 7, background: "var(--forest)" }} />provenance-first</span>
          {/* canvas-only: preview the comp-only teaching switcher (feature flag `teaching`) */}
          <button onClick={() => setTeach((t) => !t)} style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, letterSpacing: "0.5px", textTransform: "uppercase", color: "var(--ink-faint)", background: "var(--bone-sunk)", border: "1px dashed var(--line-2)", padding: "5px 10px", cursor: "pointer" }}>⚑ teaching: {teach ? "on" : "off"} ⇄</button>
          <span style={{ marginLeft: "auto" }} />
          <Button variant="forest" size="sm">✎ Submit a tip or correction</Button>
        </div>
      </div>
    </div>
  );
}
Object.assign(window, { RecordScreen });
