// Watermark — the directory home (network tier). Hero + network ledger, three lenses,
// "start here" doors, and the across-the-network table.
function DirectoryHome({ onEnterSite }) {
  const { Eyebrow, Button, PhaseDot } = window.WatermarkDesignSystem_dbe30a;
  const ink = "#16201a", muted = "#566159", faint = "#8c9389", forest = "#1f6f4a";
  // Stats are DERIVED from the site registry on the live home (SITES.length · groupSites("basin")
  // · the live filter · groupSites("state")) — never hardcoded. The 4th is States, not Contributors.
  // The values below are a current snapshot; the shipped page recomputes them at build time.
  const stats = [["33", "SITES"], ["08", "BASINS"], ["01", "LIVE REFERENCE"], ["02", "STATES"]];
  const phaseSegs = [["6%", forest], ["3%", ink], ["45%", muted], ["46%", faint]];
  const phaseLegend = [[forest, "2 live"], [ink, "1 building"], [muted, "15 queued"], [faint, "15 tracking"]];
  const lenses = [
    { n: "H1", name: "Water & Power", claim: "Where compute meets the watershed.", status: "Reference build", live: true },
    { n: "H2", name: "Defense & Federal Enclave", claim: "Where it meets federal land & the defense base.", status: "Emerging", live: false },
    { n: "H3", name: "Corporate & Economic Surveillance", claim: "Who owns it, and where the money moves.", status: "Emerging", live: false },
  ];
  const doors = [
    { nn: "01", title: "The reference build", meta: "LIMA (BOSC) · LIVE", desc: "The one fully-assembled site — and the best place to start. New here? Its story teaches you to read the record.", cta: "Enter the site", act: true },
    { nn: "02", title: "How the record is built", meta: "PROVENANCE-FIRST", desc: "Sources, labeled inference, and the two-clock model — what Watermark is, and how to read it.", cta: "Read the method" },
    { nn: "03", title: "Contribute a lead", meta: "NO ACCOUNT NEEDED", desc: "A document, a name, a correction — every confirmed figure started as a lead.", cta: "Submit a lead" },
  ];
  const featured = [
    ["BOSC", "Lima", "Maumee · Ottawa River", "live"],
    ["GCP", "Fort Wayne", "Maumee headwaters", "building"],
    ["DEF", "Defiance", "Maumee mainstem", "queued"],
    ["DAY", "Dayton", "Great Miami · WPAFB", "queued"],
    ["TOL", "Toledo", "Maumee mouth · Lake Erie", "queued"],
    ["NAL", "New Albany", "Scioto · CHIPS megasite", "tracking"],
    ["LDT", "Lordstown", "Mahoning · Voltage Valley", "tracking"],
    ["COL", "Columbus", "Scioto mainstem", "tracking"],
  ];
  return (
    <div style={{ color: "var(--ink)" }}>
      {/* hero */}
      <div style={{ display: "flex", gap: 40, padding: "42px 28px 34px", borderBottom: "1px solid var(--line-hair)", flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 520px", maxWidth: 600 }}>
          <Eyebrow>The Watermark network</Eyebrow>
          <h1 style={{ fontSize: 52, fontWeight: 800, letterSpacing: "-2px", lineHeight: 0.98, margin: "14px 0 0" }}>The build-out, on the public record.</h1>
          <p style={{ fontSize: 16.5, lineHeight: 1.55, margin: "18px 0 0", maxWidth: 560, textWrap: "pretty" }}>Watermark assembles the public record behind the hyperscale data-center build-out — <b>33 sites across 8 basins</b>, each a point where compute meets ground, water, and power. Provenance-first, and built in the open.</p>
          <div style={{ display: "flex", gap: 12, marginTop: 26, flexWrap: "wrap" }}>
            <Button variant="solid" iconRight="→">Explore the hypotheses</Button>
            <Button variant="ghost" onClick={onEnterSite} iconRight="→">See the reference build</Button>
          </div>
        </div>
        <div style={{ flex: "1 1 320px", maxWidth: 356, border: "1px solid var(--ink)" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "1.5px", textTransform: "uppercase", color: muted, padding: "11px 14px", borderBottom: "1px solid var(--ink)" }}>Network at a glance</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", margin: "-1px 0 0 -1px" }}>
            {stats.map(([n, l]) => (
              <div key={l} style={{ borderLeft: "1px solid var(--line-hair)", borderTop: "1px solid var(--line-hair)", padding: "15px 16px" }}>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 30, fontWeight: 600, letterSpacing: "-1px", lineHeight: 1 }}>{n}</div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "1px", textTransform: "uppercase", color: faint, marginTop: 6 }}>{l}</div>
              </div>
            ))}
          </div>
          <div style={{ padding: 14, borderTop: "1px solid var(--ink)" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "1.5px", textTransform: "uppercase", color: muted, marginBottom: 9 }}>Build phase</div>
            <div style={{ display: "flex", height: 10, border: "1px solid var(--ink)" }}>
              {phaseSegs.map(([w, c], i) => <span key={i} style={{ width: w, background: c, borderRight: "1px solid #f5f2ea" }} />)}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "5px 14px", marginTop: 11 }}>
              {phaseLegend.map(([c, l], i) => (
                <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "var(--font-mono)", fontSize: 11, color: muted }}><span style={{ width: 8, height: 8, background: c }} />{l}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* lenses */}
      <div style={{ padding: "28px 28px 30px", borderBottom: "1px solid var(--line-hair)" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 11, marginBottom: 20, flexWrap: "wrap" }}>
          <h2 style={{ fontSize: 19, fontWeight: 800, letterSpacing: "-0.4px", margin: 0 }}>Read the network three ways</h2>
          <span style={{ fontSize: 13, color: faint }}>— one map, three hypotheses.</span>
          <a href="#" style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.5px", color: ink, fontWeight: 600, textDecoration: "none" }}>Open the scorecard →</a>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", marginLeft: -1 }}>
          {lenses.map((L) => (
            <div key={L.n} style={{ borderLeft: "1px solid var(--line-hair)", padding: "4px 22px", cursor: "pointer" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, color: L.live ? forest : ink, border: `1px solid ${L.live ? forest : ink}`, padding: "1px 7px" }}>{L.n}</span>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "1px", textTransform: "uppercase", color: L.live ? forest : faint }}>{L.status}</span>
              </div>
              <div style={{ fontSize: 17, fontWeight: 700, letterSpacing: "-0.3px", marginTop: 13 }}>{L.name}</div>
              <div style={{ fontSize: 13, color: muted, lineHeight: 1.45, marginTop: 5 }}>{L.claim}</div>
            </div>
          ))}
        </div>
      </div>

      {/* start here */}
      <div style={{ padding: "26px 28px 30px", borderBottom: "1px solid var(--line-hair)" }}>
        <Eyebrow tone="faint" style={{ marginBottom: 18 }}>Start here</Eyebrow>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", marginLeft: -1 }}>
          {doors.map((d) => (
            <div key={d.nn} onClick={d.act ? onEnterSite : undefined} style={{ borderLeft: "1px solid var(--line-hair)", padding: "2px 22px", cursor: d.act ? "pointer" : "default", display: "flex", flexDirection: "column" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 600, color: faint }}>{d.nn}</div>
              <div style={{ fontSize: 17, fontWeight: 700, letterSpacing: "-0.3px", marginTop: 8 }}>{d.title}</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.5px", color: faint, marginTop: 5 }}>{d.meta}</div>
              <div style={{ fontSize: 13, color: muted, lineHeight: 1.5, marginTop: 9, flex: "1 1 auto" }}>{d.desc}</div>
              <div style={{ fontSize: 13, fontWeight: 700, marginTop: 14, color: d.act ? forest : ink }}>{d.cta} →</div>
            </div>
          ))}
        </div>
      </div>

      {/* table */}
      <div style={{ padding: "26px 28px 30px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 14, flexWrap: "wrap" }}>
          <Eyebrow tone="faint">Across the network</Eyebrow>
          <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.5px", color: ink, fontWeight: 600, cursor: "pointer" }}>See all 32 →</span>
        </div>
        <div style={{ borderTop: "1px solid var(--ink)", borderBottom: "1px solid var(--ink)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "42px 70px 200px 1fr 130px", fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "1px", textTransform: "uppercase", color: faint, padding: "8px 6px", borderBottom: "1px solid var(--line-hair)" }}>
            <span>#</span><span>Code</span><span>Place</span><span>Basin</span><span style={{ textAlign: "right" }}>Phase</span>
          </div>
          {featured.map(([code, place, basin, phase], i) => (
            <div key={code} onClick={code === "BOSC" ? onEnterSite : undefined} style={{ display: "grid", gridTemplateColumns: "42px 70px 200px 1fr 130px", alignItems: "center", padding: "9px 6px", color: ink, background: i % 2 ? "var(--bone-band)" : "transparent", borderBottom: "1px solid var(--line-hair)", cursor: code === "BOSC" ? "pointer" : "default" }}>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: faint }}>{String(i + 1).padStart(2, "0")}</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600 }}>{code}</span>
              <span style={{ fontSize: 14, fontWeight: 600 }}>{place}</span>
              <span style={{ fontSize: 12.5, color: muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{basin}</span>
              <span style={{ display: "flex", justifyContent: "flex-end" }}><PhaseDot phase={phase} size="sm" /></span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
Object.assign(window, { DirectoryHome });
