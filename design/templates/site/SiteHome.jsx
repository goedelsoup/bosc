// Watermark — the site home. Lima is the live reference build, so the shipped front door
// (`src/pages/network/american-sugar-creek-allen-co/index.astro`) renders the Live composition only:
// hero + a facility chip + a real open-leads pointer, two co-equal doors (the record / the story),
// the six-chapter story grid, the corpus strip, a "just ask the record" door, and the provenance
// footer. The design's dual-state `phase` (Investigation ↔ Live) is a deliberate cut — the other
// phases need per-site leads / contributor feeds Lima doesn't have, and building them would mean
// fabricating. Real feeds throughout; values here are a representative snapshot.
function SiteHome({ onOpenRecord }) {
  const { Eyebrow } = window.WatermarkDesignSystem_dbe30a;

  // Lima's facility clock (separate from the site-build clock) — the campus is under construction.
  const fac = { label: "Under construction", color: "#9a6a14", bg: "#efe6d0" };

  const chapters = [
    ["1", "Who is actually building this?", "Reading a deed · entity resolution"],
    ["2", "How it was assembled & hidden", "Options-to-assignment · confidentiality-first"],
    ["3", "How big is it — and what won't they tell you?", "Reading an air permit · CBI redaction"],
    ["4", "What it does to the water", "NPDES permit · the 7Q10 low-flow screen"],
    ["5", "What it costs the public", "A cost estimate · a contract clause"],
    ["6", "How to read it yourself", "Citations · confidence tags · where it's silent"],
  ];
  const corpus = [["1,615", "source files"], ["55", "records"], ["174", "timeline events"], ["72", "entities & places"], ["13", "essays"]];

  return (
    <div style={{ color: "var(--ink)" }}>
      <div style={{ padding: "34px 44px 30px" }}>
        {/* hero — single column; the facility chip + open-leads pill replace the dual-state bar */}
        <div style={{ maxWidth: 700 }}>
          <Eyebrow tone="forest" style={{ color: "var(--forest)" }}>Public record · Lima, Allen County, Ohio</Eyebrow>
          <h1 style={{ fontSize: 38, fontWeight: 800, letterSpacing: "-0.9px", lineHeight: 1.05, margin: "11px 0 0" }}>A 340-acre data center,<br />built to be invisible.</h1>
          <p style={{ fontSize: 16.5, lineHeight: 1.55, color: "var(--ink-prose)", margin: "15px 0 0", textWrap: "pretty" }}>A Delaware shell. Withheld land prices. <b>114 backup generators.</b> A consumptive cooling loss that dwarfs a river running at <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--forest)" }}>0.2 cfs</span>. The record was made thin on purpose — here it's reassembled in the open, and <b>every figure is checkable.</b></p>
          <div style={{ display: "flex", alignItems: "center", gap: 13, marginTop: 18, flexWrap: "wrap" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, fontWeight: 700, color: fac.color, background: fac.bg, padding: "5px 12px", borderRadius: 999 }}>
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="4" y="4.5" width="16" height="6.5" rx="1.4" /><rect x="4" y="13" width="16" height="6.5" rx="1.4" /><line x1="7" y1="7.75" x2="7.2" y2="7.75" /><line x1="7" y1="16.25" x2="7.2" y2="16.25" /></svg>
              Facility · {fac.label}
            </span>
            <a href="#" style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12.5, fontWeight: 600, color: "var(--ev-inference-fg)", background: "var(--ev-inference-bg)", border: "1px solid var(--ev-inference-border)", padding: "5px 12px", borderRadius: 999, textDecoration: "none" }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--ev-inference-fg)" }} />12 open leads · help close them
            </a>
          </div>
        </div>

        {/* the entry fork — two co-equal doors: the researcher's library + the newcomer's story */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 28 }}>
          <a onClick={onOpenRecord} style={{ display: "flex", flexDirection: "column", textDecoration: "none", color: "var(--ink)", border: "1.5px solid var(--forest-line)", padding: 22, background: "var(--surface-card)", cursor: "pointer" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}><span style={{ fontSize: 11, letterSpacing: "1px", textTransform: "uppercase", color: "#3a4a3e", fontWeight: 700 }}>For the researcher</span><span style={{ marginLeft: "auto", fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-faint)" }}>1,615 files</span></div>
            <div style={{ fontSize: 23, fontWeight: 800, letterSpacing: "-0.4px", margin: "9px 0 6px" }}>Browse the record</div>
            <div style={{ fontSize: 14.5, color: "var(--ink-muted)", lineHeight: 1.5 }}>Straight to the documents, records, timeline, and entities. Provenance-first; follow any citation to its source.</div>
            <div style={{ marginTop: 16, display: "inline-flex", alignItems: "center", gap: 8, alignSelf: "flex-start", background: "var(--surface-card)", border: "1.5px solid var(--line-2)", color: "#3a4036", fontWeight: 700, fontSize: 14, padding: "10px 18px" }}>Enter the library →</div>
          </a>
          <a style={{ display: "flex", flexDirection: "column", textDecoration: "none", color: "#f5f2ea", border: "1.5px solid var(--forest)", padding: 22, background: "var(--forest)", cursor: "pointer" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}><span style={{ fontSize: 11, letterSpacing: "1px", textTransform: "uppercase", color: "#bcd2c4", fontWeight: 700 }}>For the newcomer</span><span style={{ marginLeft: "auto", fontSize: 11, fontFamily: "var(--font-mono)", color: "#9aa890" }}>6 chapters · ~18 min</span></div>
            <div style={{ fontSize: 23, fontWeight: 800, letterSpacing: "-0.4px", margin: "9px 0 6px" }}>Read the story</div>
            <div style={{ fontSize: 14.5, color: "#d4dccf", lineHeight: 1.5 }}>A path that teaches you to read the record one document at a time — no jargon, no prior knowledge.</div>
            <div style={{ marginTop: 16, display: "inline-flex", alignItems: "center", gap: 8, alignSelf: "flex-start", background: "#f5f2ea", color: "var(--forest)", fontWeight: 700, fontSize: 14, padding: "10px 18px" }}>▶ Start the story →</div>
          </a>
        </div>

        {/* the story · six chapters */}
        <div style={{ marginTop: 26, paddingTop: 22, borderTop: "1px solid var(--line-faint)" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 15, flexWrap: "wrap" }}>
            <Eyebrow tone="faint">The story · in six chapters</Eyebrow>
            <span style={{ fontSize: 12.5, color: "var(--ink-faint)" }}>— one project, read one document at a time.</span>
            <a href="#" style={{ marginLeft: "auto", fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--ink-muted)", fontWeight: 600, textDecoration: "none" }}>Table of contents →</a>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {chapters.map(([n, title, method]) => (
              <a key={n} onClick={n === "1" ? onOpenRecord : undefined} style={{ display: "flex", gap: 13, alignItems: "flex-start", textDecoration: "none", color: "var(--ink)", background: "var(--surface-card)", border: "1px solid var(--line-hair)", padding: "14px 15px", cursor: "pointer" }}>
                <span style={{ flex: "0 0 auto", width: 26, height: 26, background: "var(--forest)", color: "#f5f2ea", fontSize: 13, fontWeight: 800, fontFamily: "var(--font-mono)", display: "flex", alignItems: "center", justifyContent: "center" }}>{n}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 700, lineHeight: 1.25 }}>{title}</div>
                  <div style={{ fontSize: 12, color: "var(--forest)", fontWeight: 600, marginTop: 3 }}>{method}</div>
                </div>
              </a>
            ))}
          </div>
        </div>

        {/* the corpus at a glance */}
        <div style={{ marginTop: 24, paddingTop: 20, borderTop: "1px solid var(--line-faint)" }}>
          <Eyebrow tone="faint" style={{ marginBottom: 14 }}>The corpus at a glance</Eyebrow>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 20 }}>
            {corpus.map(([n, l]) => (
              <div key={l}><div style={{ fontSize: 26, fontWeight: 800, fontFamily: "var(--font-mono)", letterSpacing: "-1px" }}>{n}</div><div style={{ fontSize: 12, color: "var(--ink-faint)" }}>{l}</div></div>
            ))}
          </div>
        </div>

        {/* the third way in — a question, not a path. Answers are cited and drawn only from the corpus. */}
        <a href="#" style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 24, textDecoration: "none", color: "var(--ink)", background: "var(--bone-sunk)", border: "1px solid var(--line-hair)", borderLeft: "3px solid var(--forest)", padding: "16px 20px" }}>
          <span aria-hidden="true" style={{ flex: "0 0 auto", fontSize: 20, color: "var(--forest)" }}>✦</span>
          <span style={{ flex: "1 1 auto", fontSize: 14.5, lineHeight: 1.5, color: "var(--ink-prose)" }}><b>Or just ask the record a question.</b> Answers are drawn only from the corpus, every claim cited — and where the record is silent, it says so.</span>
          <span style={{ flex: "0 0 auto", fontSize: 13.5, fontWeight: 700, color: "var(--forest)" }}>Ask the corpus →</span>
        </a>
      </div>

      {/* provenance footer */}
      <div style={{ padding: "14px 44px", background: "var(--bone-sunk)", borderTop: "1px solid var(--line-faint)", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, color: "var(--forest)", background: "var(--forest-tint)", padding: "3px 11px" }}><span style={{ width: 6, height: 6, background: "var(--forest)" }} />provenance-first</span>
        <div style={{ fontSize: 13, color: "var(--ink-muted)", lineHeight: 1.5 }}><b style={{ color: "#3a4036" }}>Pre-launch.</b> Assembled from public records the developer didn't write. Sourced figures carry citations; open leads stay labeled as inference until corroborated. Nothing here is a verdict — verify every figure against its cited source.</div>
      </div>
    </div>
  );
}
Object.assign(window, { SiteHome });
