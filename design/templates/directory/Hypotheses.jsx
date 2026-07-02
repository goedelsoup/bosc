// Watermark — the Hypotheses index (network tier). One network, read three ways: pick a lens
// and the SAME sites reorganize under that thesis as a grouped, provenance-first scorecard.
//
// Shipped page (`src/pages/research/hypotheses.astro` + `lib/directory.ts`) is no-JS: the lens
// switch is radio + :checked, the lens config (name/claim/blurb/status) reads the `hypotheses`
// feed, and the per-site cells read the `hypothesis-assessments` feed (each cell a real fact or a
// tagged inference — never a fabricated nexus; un-assessed sites fall to a "not yet assessed" chip
// tail, never a zero). This canvas mirrors that model with a representative bundle snapshot; the
// lens switch is React state here only because a design canvas can't ship the radio CSS.
function Hypotheses() {
  const { Eyebrow } = window.WatermarkDesignSystem_dbe30a;
  const [lens, setLens] = React.useState("water");
  const forest = "#1f6f4a", muted = "#566159", faint = "#8c9389";

  // Swatches mirror lib/directory.ts — PHASE_PILL (build phase), SIGNAL_META (H2/H3 standing),
  // FACILITY_STATUS_META (the second clock). { label, color, bg, dot }.
  const PHASE = {
    live: { label: "Live", color: forest, bg: "#e4ece4", dot: forest },
    building: { label: "Building", color: forest, bg: "#e4ece4", dot: forest },
    queued: { label: "Queued", color: "#9a6a14", bg: "#efe6d0", dot: "#9a6a14" },
    tracking: { label: "Tracking", color: muted, bg: "#e8e4d8", dot: faint },
  };
  const SIGNAL = {
    anchor: { label: "Anchor case", color: forest, bg: "#e4ece4", dot: forest },
    strong: { label: "Strong signal", color: forest, bg: "#e4ece4", dot: "#3f8a63" },
    moderate: { label: "Moderate", color: muted, bg: "#e8e4d8", dot: faint },
    watch: { label: "Under investigation", color: faint, bg: "#faf8f1", dot: "#cdc8b8" },
  };
  const FAC = {
    investigation: { label: "Under investigation", color: muted, bg: "#e8e4d8", dot: faint },
    confirmed: { label: "Confirmed", color: forest, bg: "#e4ece4", dot: forest },
    construction: { label: "Under construction", color: "#9a6a14", bg: "#efe6d0", dot: "#9a6a14" },
  };

  // Per-lens presentation + column spec (mirror of LENSES / cfg.fr in lib/directory.ts).
  const LENSES = {
    water: {
      n: "H1", name: "Water & Power", accent: forest, accentBg: "#e4ece4", accentBd: "#bcd2c4",
      status: "Reference build", statusKind: "live",
      claim: "Where compute meets the watershed.",
      blurb: "The original thesis: hyperscale compute lands where it can pull power and water, and a data center's intake, discharge, and downstream effects are basin facts. Sites nest by drainage — two divides, nine basins. Lima is the live, fully-assembled reference.",
      axisTitle: "Two divides · nine basins", scoreTitle: "Every point, by drainage",
      scoreNote: "Build phase and facility status are two clocks — kept distinct.",
      footNote: "A dash means the section isn't assembled yet — never a zero, which would read as a finding.",
      cols: ["Site", "Watershed point", "Build phase", "Documents▸", "Records▸", "Facility status"],
      fr: "1.5fr 1.4fr 0.95fr 0.78fr 0.78fr 1.15fr",
      link: "Open the drainage tree & basin scorecard ›",
      count: "33 sites · 8 basins",
    },
    defense: {
      n: "H2", name: "Defense & Federal Enclave", accent: "#16201a", accentBg: "#ece8dc", accentBd: "#cdc8b8",
      status: "Emerging hypothesis", statusKind: "new",
      claim: "Where the build-out meets federal land and the defense base.",
      blurb: "A second reading: the same map tracks arsenals, air bases, federal research and the CHIPS build — enclaves where federal jurisdiction, clearance, and defense supply chains concentrate. Newly opened; most sites are not yet assessed, and a federal nexus is a signal, not a verdict.",
      axisTitle: "Assessment so far", scoreTitle: "Every site, by federal nexus",
      scoreNote: "Signal is inference until a federal nexus is documented.",
      footNote: "Sites without an entry are not yet assessed under this thesis — that is not the same as cleared.",
      cols: ["Site", "Federal / defense nexus", "Linkage", "Signal", "Facility status"],
      fr: "1.4fr 1.8fr 1.0fr 1.05fr 1.15fr",
      count: "2 assessed · 31 to review",
    },
    surveillance: {
      n: "H3", name: "Corporate & Economic Surveillance", accent: "#566159", accentBg: "#e8e4d8", accentBd: "#cdc8b8",
      status: "Emerging hypothesis", statusKind: "new",
      claim: "Who owns it, who's watching, and where the money moves.",
      blurb: "A third reading: the operators behind shell LLCs, the public-subsidy stack that pulls them in, and the capital and data flows the facilities sit on. The corporate-and-economic-surveillance thesis — opening now, mostly under investigation, with Lima's abatement on record.",
      axisTitle: "Assessment so far", scoreTitle: "Every site, by operator & capital",
      scoreNote: "Operators behind LLCs; public subsidy is on the public record.",
      footNote: "Sites without an entry are not yet assessed under this thesis — that is not the same as cleared.",
      cols: ["Site", "Operator (inferred)", "Capital & public subsidy", "Signal", "Facility status"],
      fr: "1.4fr 1.5fr 1.6fr 1.05fr 1.15fr",
      count: "2 assessed · 31 to review",
    },
  };

  // Cell helpers (mirror siteCell/textCell/numCell/pillCell). live → forest badge, else plain.
  const site = (badge, place, live) => ({ t: "site", badge, place, live });
  const txt = (text, m) => ({ t: "text", text: text || "—", muted: m || !text || text === "—" });
  const num = (text) => ({ t: "num", text, muted: text === "—" });
  const pill = (sw) => ({ t: "pill", sw });

  // Representative VIEW per lens — the shape buildLens() produces from the bundle.
  const VIEWS = {
    water: {
      axisGroups: [
        { label: "Lake Erie drainage", chips: [["Maumee", 4]] },
        { label: "Ohio River drainage", chips: [["Great Miami", 1], ["Scioto", 2]] },
      ],
      groups: [
        { abbr: "MAU", label: "Maumee", count: 4, kind: "rows",
          divide: { label: "Lake Erie drainage", note: "north — into Lake Erie" },
          rows: [
            { live: true, cells: [site("BOSC", "Lima", true), txt("Maumee · Ottawa River"), pill(PHASE.live), num("63"), num("18"), pill(FAC.construction)] },
            { cells: [site("GCP", "Fort Wayne"), txt("Maumee headwaters"), pill(PHASE.building), num("—"), num("—"), pill(FAC.confirmed)] },
            { cells: [site("DEF", "Defiance"), txt("Maumee mainstem"), pill(PHASE.queued), num("—"), num("—"), pill(FAC.investigation)] },
            { cells: [site("TOL", "Toledo"), txt("Maumee mouth · Lake Erie"), pill(PHASE.queued), num("—"), num("—"), pill(FAC.investigation)] },
          ] },
        { abbr: "GMI", label: "Great Miami", count: 1, kind: "rows",
          divide: { label: "Ohio River drainage", note: "south — into the Ohio & Mississippi" },
          rows: [
            { cells: [site("DAY", "Dayton"), txt("Great Miami · Mad River"), pill(PHASE.queued), num("—"), num("—"), pill(FAC.investigation)] },
          ] },
        { abbr: "SCI", label: "Scioto", count: 2, kind: "rows",
          rows: [
            { cells: [site("NAL", "New Albany"), txt("Scioto · Licking"), pill(PHASE.tracking), num("—"), num("—"), pill(FAC.investigation)] },
            { cells: [site("COL", "Columbus"), txt("Scioto mainstem"), pill(PHASE.tracking), num("—"), num("—"), pill(FAC.investigation)] },
          ] },
      ],
    },
    defense: {
      axisGroups: [{ chips: [["Arsenals", 1], ["Federal semiconductor", 1], ["Not yet assessed", 6]] }],
      groups: [
        { abbr: "MIL", label: "Arsenals & air bases", count: 1, kind: "rows",
          rows: [
            { cells: [site("DAY", "Dayton"), txt("Wright-Patterson AFB"), txt("adjacency · 12 mi", true), pill(SIGNAL.strong), pill(FAC.investigation)] },
          ] },
        { abbr: "FED", label: "Federal semiconductor & research", count: 1, kind: "rows",
          rows: [
            { cells: [site("NAL", "New Albany"), txt("Intel CHIPS megasite"), txt("federal incentive", true), pill(SIGNAL.moderate), pill(FAC.investigation)] },
          ] },
        { abbr: "—", label: "Not yet assessed under this thesis", count: 6, kind: "chips",
          chips: [["Lima", forest], ["Fort Wayne", forest], ["Defiance", "#9a6a14"], ["Toledo", "#9a6a14"], ["Columbus", faint], ["Lordstown", faint]] },
      ],
    },
    surveillance: {
      axisGroups: [{ chips: [["Operator on record", 1], ["Public-subsidy signal", 1], ["Not yet assessed", 6]] }],
      groups: [
        { abbr: "OPR", label: "Operator & subsidy on record", count: 1, kind: "rows",
          rows: [
            { live: true, cells: [site("BOSC", "Lima", true), txt("Google (AEDG)"), txt("15-yr abatement on record"), pill(SIGNAL.anchor), pill(FAC.construction)] },
          ] },
        { abbr: "SUB", label: "Public-subsidy signal only", count: 1, kind: "rows",
          rows: [
            { cells: [site("LDT", "Lordstown"), txt("—", true), txt("Voltage Valley incentive stack"), pill(SIGNAL.moderate), pill(FAC.investigation)] },
          ] },
        { abbr: "—", label: "Not yet assessed under this thesis", count: 6, kind: "chips",
          chips: [["Fort Wayne", forest], ["Defiance", "#9a6a14"], ["Toledo", "#9a6a14"], ["Dayton", "#9a6a14"], ["New Albany", faint], ["Columbus", faint]] },
      ],
    },
  };

  const order = ["water", "defense", "surveillance"];
  const cfg = LENSES[lens], view = VIEWS[lens];
  const statusSw = (kind) => kind === "live"
    ? { color: forest, bg: "#e4ece4", dot: forest }
    : { color: faint, bg: "#e8e4d8", dot: faint };

  const Pill = ({ sw }) => (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700, color: sw.color, background: sw.bg, borderRadius: 999, padding: "3px 9px" }}>
      <span style={{ width: 5, height: 5, borderRadius: "50%", background: sw.dot }} />{sw.label}
    </span>
  );

  return (
    <div style={{ color: "var(--ink)", padding: "34px 28px 40px", maxWidth: 1240, margin: "0 auto" }}>
      <Eyebrow tone="forest">Watermark · directory · the three hypotheses</Eyebrow>
      <h1 style={{ fontSize: 38, fontWeight: 800, letterSpacing: "-1px", margin: "8px 0 6px", lineHeight: 1.03 }}>One network, three hypotheses.</h1>
      <p style={{ fontSize: 16, lineHeight: 1.55, color: "var(--ink-prose)", margin: 0, maxWidth: 700, textWrap: "pretty" }}>The platform-level index holds <b>{cfg.count}</b>. The watershed lens — where compute meets water and power — is the live reference build (Lima / BOSC). Two further theses open alongside it. The directory reads the same network through whichever lens you pick.</p>

      {/* lens cards — the no-JS radio switch (state here on the canvas) */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 13, marginTop: 26 }}>
        {order.map((k) => {
          const L = LENSES[k], on = lens === k, sw = statusSw(L.statusKind);
          return (
            <div key={k} onClick={() => setLens(k)} style={{ display: "flex", flexDirection: "column", cursor: "pointer", background: on ? L.accentBg : "var(--bone-sunk)", border: `1.5px solid ${on ? L.accent : "var(--line-hair)"}`, borderRadius: 14, padding: "15px 17px", boxShadow: on ? "0 8px 22px rgba(20,24,40,0.12)" : "0 1px 3px rgba(20,24,40,0.05)", transition: "border-color .12s, box-shadow .12s" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 800, color: "#f5f2ea", background: L.accent, borderRadius: 6, padding: "2px 8px" }}>{L.n}</span>
                <Pill sw={{ ...sw, label: L.status }} />
                {on && <span style={{ marginLeft: "auto", fontWeight: 800, fontSize: 14, color: L.accent }}>✓</span>}
              </div>
              <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: "-0.3px", marginTop: 11 }}>{L.name}</div>
              <div style={{ fontSize: 13, color: muted, lineHeight: 1.45, marginTop: 4 }}>{L.claim}</div>
              <div style={{ marginTop: 11, paddingTop: 10, borderTop: "1px solid var(--line-faint)", fontFamily: "var(--font-mono)", fontSize: 11.5, color: faint }}>{L.count}</div>
            </div>
          );
        })}
      </div>
      <p style={{ fontSize: 12.5, color: faint, lineHeight: 1.5, margin: "11px 0 0" }}>Not mutually exclusive — a single site can sit in all three. <b>Lima (BOSC)</b> is the worked example under each.</p>

      {/* lens framing panel */}
      <div style={{ marginTop: 21, border: `1px solid ${cfg.accentBd}`, background: cfg.accentBg, borderRadius: 14, padding: "20px 22px", display: "flex", gap: 26, flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 380px", minWidth: 300 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "1px", textTransform: "uppercase", fontWeight: 800, color: cfg.accent }}>{cfg.n} · {cfg.name}</span>
            <Pill sw={{ ...statusSw(cfg.statusKind), label: cfg.status }} />
          </div>
          <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: "-0.3px", marginTop: 9 }}>{cfg.claim}</div>
          <p style={{ fontSize: 13.5, lineHeight: 1.55, color: "#3a4036", margin: "10px 0 0", maxWidth: "36rem" }}>{cfg.blurb}</p>
          {cfg.link && <a href="#" style={{ display: "inline-block", marginTop: 12, fontSize: 13, fontWeight: 700, color: forest, textDecoration: "none" }}>{cfg.link}</a>}
        </div>
        <div style={{ flex: "1 1 300px", minWidth: 280 }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "1px", textTransform: "uppercase", color: faint, fontWeight: 700, marginBottom: 12 }}>{cfg.axisTitle}</div>
          {view.axisGroups.map((ag, i) => (
            <div key={i} style={{ marginBottom: 11 }}>
              {ag.label && <div style={{ fontSize: 12, fontWeight: 700, color: muted, marginBottom: 7 }}>{ag.label}</div>}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
                {ag.chips.map(([name, n]) => (
                  <span key={name} style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12, fontWeight: 600, color: "#3a4036", background: "#f5f2ea", border: "1px solid var(--line-hair)", borderRadius: 999, padding: "3px 11px" }}>{name}<span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: faint }}>{n}</span></span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* cross-site scorecard */}
      <div style={{ marginTop: 30 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, marginBottom: 13, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "1px", textTransform: "uppercase", fontWeight: 700, color: cfg.accent }}>Cross-site scorecard</div>
            <h2 style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-0.5px", margin: "5px 0 0" }}>{cfg.scoreTitle}</h2>
          </div>
          <span style={{ fontSize: 12.5, color: faint, maxWidth: "24rem", textAlign: "right" }}>{cfg.scoreNote}</span>
        </div>

        <div style={{ border: "1px solid var(--line-hair)", borderRadius: 14, overflow: "hidden" }}>
          {/* thead */}
          <div style={{ display: "grid", gridTemplateColumns: cfg.fr, columnGap: 16, alignItems: "center", background: "var(--bone-sunk)", borderBottom: "1px solid var(--line-hair)", padding: "9px 17px", fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.5px", textTransform: "uppercase", color: faint, fontWeight: 700 }}>
            {cfg.cols.map((c) => <span key={c} style={c.endsWith("▸") ? { textAlign: "right" } : undefined}>{c.replace("▸", "")}</span>)}
          </div>

          {view.groups.map((g, gi) => (
            <div key={gi}>
              {g.divide && (
                <div style={{ display: "flex", alignItems: "baseline", gap: 11, padding: "13px 17px 9px", background: "#ece8dc" }}>
                  <span style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.5px", textTransform: "uppercase", color: cfg.accent }}>{g.divide.label}</span>
                  <span style={{ fontSize: 11.5, color: faint }}>{g.divide.note}</span>
                </div>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "9px 17px", background: "var(--bone-sunk)", borderBottom: "1px solid var(--line-faint)" }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 9.5, fontWeight: 800, background: "#ece8dc", border: "1px solid #cdc8b8", borderRadius: 5, padding: "2px 7px", color: cfg.accent }}>{g.abbr}</span>
                <span style={{ fontSize: 11.5, fontWeight: 800, letterSpacing: "0.5px", textTransform: "uppercase", color: muted }}>{g.label}</span>
                <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 11, color: faint }}>{g.count}</span>
              </div>
              {g.kind === "rows" ? g.rows.map((r, ri) => (
                <div key={ri} style={{ display: "grid", gridTemplateColumns: cfg.fr, columnGap: 16, alignItems: "center", padding: "10px 17px", borderBottom: "1px solid var(--line-faint)", background: r.live ? "#eef1e8" : "#f5f2ea" }}>
                  {r.cells.map((c, ci) => {
                    if (c.t === "site") return (
                      <span key={ci} style={{ display: "flex", alignItems: "center", gap: 9, minWidth: 0 }}>
                        <span style={{ flex: "0 0 auto", width: 30, height: 30, borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-mono)", fontSize: 9.5, fontWeight: 800, background: c.live ? forest : "#e8e4d8", color: c.live ? "#f5f2ea" : muted }}>{c.badge}</span>
                        <span style={{ fontSize: 14, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.place}</span>
                      </span>
                    );
                    if (c.t === "num") return <span key={ci} style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600, color: c.muted ? "#cdc8b8" : "var(--ink)" }}>{c.text}</span>;
                    if (c.t === "pill") return <span key={ci}><Pill sw={c.sw} /></span>;
                    return <span key={ci} style={{ fontSize: 12.5, lineHeight: 1.35, color: c.muted ? faint : muted }}>{c.text}</span>;
                  })}
                </div>
              )) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 7, padding: "12px 17px 15px" }}>
                  {g.chips.map(([place, dot]) => (
                    <span key={place} style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 13, color: muted, background: "var(--bone-sunk)", border: "1px solid var(--line-hair)", borderRadius: 999, padding: "4px 11px" }}><span style={{ width: 6, height: 6, borderRadius: "50%", background: dot }} />{place}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
          <div style={{ padding: "11px 17px", background: "var(--bone-sunk)", fontSize: 12.5, color: faint, lineHeight: 1.45 }}>{cfg.footNote}</div>
        </div>
      </div>
    </div>
  );
}
Object.assign(window, { Hypotheses });
