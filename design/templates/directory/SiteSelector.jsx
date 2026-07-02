// Watermark — the grouped site selector. Drops from the "All sites" chip / site chip.
// Filter + a State⇄Basin group-by toggle (Basin default); the basin lens nests basins
// under regions (region band). Each row carries the build-phase status (PhaseDot), the
// facility lifecycle clock (a SEPARATE clock from the build), the tracking issue, and a
// lock affordance (a locked row routes to its request-access page; see the foot legend).
function SiteSelector({ active, onPick }) {
  const { PhaseDot } = window.WatermarkDesignSystem_dbe30a;
  const [groupBy, setGroupBy] = React.useState("basin");

  // The facility lifecycle — a separate clock from the build phase (FACILITY_STATUS_META).
  const FAC = {
    investigation: { short: "Investigating",    color: "#566159" },
    confirmed:     { short: "Confirmed",         color: "#1f6f4a" },
    construction:  { short: "Under construction",   color: "#9a6a14" },
    live:          { short: "Operational",       color: "#1f6f4a" },
  };
  const BASIN_ABBR = { Maumee: "MAU", "Great Miami": "GMI", "Little Miami": "LMI", Scioto: "SCI", Mahoning: "MAH" };

  // Illustrative sample — the live panel reads the 32-site registry (bosc.sites / lib/sites.ts).
  const SITES = [
    { code: "BOSC", place: "Lima",       basin: "Maumee",       region: "Maumee Basin",       rtag: "MAU", state: "Ohio",    status: "live",     fac: "construction" },
    { code: "GCP",  place: "Fort Wayne", basin: "Maumee",       region: "Maumee Basin",       rtag: "MAU", state: "Indiana", status: "building", fac: "confirmed",     issue: "235" },
    { code: "DEF",  place: "Defiance",   basin: "Maumee",       region: "Maumee Basin",       rtag: "MAU", state: "Ohio",    status: "queued",   fac: "investigation", issue: "237" },
    { code: "DAY",  place: "Dayton",     basin: "Great Miami",  region: "The Two Miamis",     rtag: "2MI", state: "Ohio",    status: "queued",   fac: "investigation", issue: "363" },
    { code: "XEN",  place: "Xenia",      basin: "Little Miami", region: "The Two Miamis",     rtag: "2MI", state: "Ohio",    status: "queued",   fac: "investigation", issue: "442" },
    { code: "NAL",  place: "New Albany", basin: "Scioto",       region: "Southeastern Basins",rtag: "SE",  state: "Ohio",    status: "tracking", fac: "confirmed",     issue: "485" },
    { code: "COL",  place: "Columbus",   basin: "Scioto",       region: "Southeastern Basins",rtag: "SE",  state: "Ohio",    status: "tracking", fac: "investigation", issue: "486" },
    { code: "LDT",  place: "Lordstown",  basin: "Mahoning",     region: "Northeast Basins",   rtag: "NE",  state: "Ohio",    status: "tracking", fac: "investigation", issue: "493" },
  ];

  // Group by the active lens, preserving registry order. The basin lens marks the first
  // basin group of each region so a region band renders before it; the state lens has none.
  const groups = [];
  const idx = {};
  for (const s of SITES) {
    const key = groupBy === "state" ? s.state : s.basin;
    let g = idx[key];
    if (!g) {
      g = groupBy === "state"
        ? { key, label: s.state, tag: s.state === "Ohio" ? "OH" : "IN", region: null, sites: [] }
        : { key, label: s.basin, tag: BASIN_ABBR[s.basin] || s.basin.slice(0, 3).toUpperCase(), region: s.region, rtag: s.rtag, sites: [] };
      idx[key] = g;
      groups.push(g);
    }
    g.sites.push(s);
  }
  if (groupBy === "basin") {
    const seen = {};
    for (const g of groups) {
      if (!seen[g.region]) {
        g.showRegion = true;
        seen[g.region] = true;
        g.regionCount = groups.filter((x) => x.region === g.region).reduce((n, x) => n + x.sites.length, 0);
      }
    }
  }

  const tog = (k, label) => (
    <span onClick={() => setGroupBy(k)} style={{ fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 700, letterSpacing: "0.5px", textTransform: "uppercase", color: groupBy === k ? "var(--forest)" : "var(--ink-faint)", background: groupBy === k ? "var(--forest-tint)" : "transparent", border: `1px solid ${groupBy === k ? "var(--forest-line)" : "var(--line-hair)"}`, padding: "3px 9px", cursor: "pointer" }}>{label}</span>
  );

  return (
    <div style={{ background: "var(--surface-card)", border: "1px solid var(--line-2)", borderTop: "3px solid var(--forest)", boxShadow: "none" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px", borderBottom: "1px solid var(--line-hair)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: "1 1 auto", background: "var(--bone-sunk)", border: "1px solid var(--line-hair)", padding: "7px 11px" }}>
          <window.WmIcon size={14} stroke="var(--ink-faint)" sw={2}><circle cx="11" cy="11" r="6.5" /><line x1="16" y1="16" x2="21" y2="21" /></window.WmIcon>
          <span style={{ fontSize: 13, color: "var(--ink-faint)" }}>Filter sites…</span>
        </div>
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 9.5, letterSpacing: "0.6px", textTransform: "uppercase", color: "var(--ink-ghost)" }}>Group by</span>
          {tog("state", "State")}
          {tog("basin", "Basin")}
        </span>
      </div>
      <div style={{ maxHeight: 380, overflow: "auto", padding: "6px 0" }}>
        {groups.map((g) => (
          <div key={g.key}>
            {g.showRegion ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "11px 16px 4px" }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, fontWeight: 700, letterSpacing: "0.5px", color: "var(--bone-surface)", background: "var(--ink)", padding: "1px 5px" }}>{g.rtag}</span>
                <span style={{ fontSize: 11.5, fontWeight: 800, letterSpacing: "0.3px", textTransform: "uppercase", color: "var(--ink-muted)" }}>{g.region}</span>
                <span style={{ fontSize: 10.5, color: "var(--ink-ghost)" }}>{g.regionCount} sites</span>
                <span style={{ flex: "1 1 auto", height: 1, background: "var(--line-hair)" }} />
              </div>
            ) : null}
            <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "7px 16px 4px" }}>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 9.5, fontWeight: 700, letterSpacing: "0.5px", color: "var(--ink-faint)" }}>{g.tag}</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.8px", textTransform: "uppercase", color: "var(--ink-faint)" }}>{g.label}{groupBy === "basin" ? " basin" : ""}</span>
              <span style={{ fontSize: 10.5, color: "var(--ink-ghost)" }}>{g.sites.length}</span>
            </div>
            {g.sites.map((s) => {
              const on = active === s.place;
              const fac = FAC[s.fac];
              return (
                <div key={s.code} onClick={() => onPick && onPick(s)} style={{ display: "flex", alignItems: "center", gap: 12, padding: "9px 16px", cursor: "pointer", background: on ? "var(--forest-tint)" : "transparent" }}>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 700, letterSpacing: "0.4px", color: on ? "var(--forest)" : "var(--ink-muted)", background: on ? "transparent" : "var(--bone-sunk)", border: `1px solid ${on ? "var(--forest-line)" : "var(--line-hair)"}`, padding: "3px 6px", width: 44, textAlign: "center" }}>{s.code}</span>
                  <span style={{ flex: "1 1 auto", minWidth: 0 }}>
                    <span style={{ display: "block", fontSize: 14, fontWeight: 700 }}>{s.place}</span>
                    <span style={{ display: "block", fontSize: 11.5, color: "var(--ink-faint)" }}>{s.basin} basin</span>
                  </span>
                  <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 3 }}>
                    <PhaseDot phase={s.status} size="sm" />
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 10, fontWeight: 700, color: fac.color }}>
                        <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4.5" width="16" height="6.5" rx="1.4" /><rect x="4" y="13" width="16" height="6.5" rx="1.4" /></svg>
                        {fac.short}
                      </span>
                      {s.issue ? <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--ink-ghost)" }}>#{s.issue}</span> : null}
                    </span>
                  </span>
                  {on ? <span style={{ color: "var(--forest)", fontWeight: 800 }}>✓</span> : <span style={{ color: "var(--ink-ghost)" }}>›</span>}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 16px", borderTop: "1px solid var(--line-hair)", background: "var(--bone-sunk)", flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "var(--ink-muted)" }}><b>32</b> sites · pivoted by {groupBy === "basin" ? "9 basins" : "2 states"}</span>
        <span style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 10, color: "var(--ink-faint)" }}>
          <span>Live</span><span>Building</span><span>Queued</span><span>Tracking</span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
            <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><rect x="5" y="11" width="14" height="9" rx="1" /><path d="M8 11 V7.5 A4 4 0 0 1 16 7.5 V11" /></svg>Locked
          </span>
        </span>
        <span style={{ marginLeft: "auto", fontSize: 12.5, fontWeight: 700, color: "var(--forest)", cursor: "pointer" }}>Open the full directory →</span>
      </div>
    </div>
  );
}
Object.assign(window, { SiteSelector });
