// Watermark — network-tier chrome (the ink bar). Wordmark home + "All sites" selector
// opener + network tabs (Directory / Research / About▾) + platform tools. Submit is a
// right-cluster "+" pill (present on both tiers), not a left tab.
function Icon({ d, size = 14, stroke = "#bcd2c4", fill = "none", sw = 1.8, children }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill={fill} stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
      {children || <path d={d} />}
    </svg>
  );
}

function DirectoryChrome({ active = "directory", onNav, onToggleSelector, selectorOpen }) {
  const tab = (key, label, isLink) => {
    const on = active === key;
    return (
      <span
        key={key}
        onClick={() => onNav && onNav(key)}
        style={{
          color: on ? "#f5f2ea" : "#bcd2c4", fontSize: 14, fontWeight: on ? 600 : 400,
          padding: "0 13px", height: "100%", display: "flex", alignItems: "center", cursor: "pointer",
          boxShadow: on ? "inset 0 -3px 0 #f5f2ea" : "none",
        }}
      >
        {label}{isLink ? <span style={{ fontSize: 9, color: "#9aa890", marginLeft: 6 }}>▾</span> : null}
      </span>
    );
  };
  return (
    <div style={{ background: "var(--ink)", padding: "0 16px", height: 56, display: "flex", alignItems: "center", gap: 13 }}>
      <span onClick={() => onNav && onNav("directory")} style={{ display: "flex", alignItems: "center", cursor: "pointer", color: "#f5f2ea" }}>
        <span style={{ fontWeight: 800, fontSize: 16, letterSpacing: "-0.2px" }}>Watermark<span style={{ color: "#7fb89a" }}>.</span></span>
      </span>
      <span style={{ color: "#566159", fontSize: 15 }}>/</span>
      <span onClick={onToggleSelector} style={{ display: "flex", alignItems: "center", gap: 7, background: "rgba(255,255,255,0.16)", border: `1px solid ${selectorOpen ? "rgba(150,200,170,0.55)" : "rgba(255,255,255,0.26)"}`, boxShadow: selectorOpen ? "0 0 0 2px rgba(31,111,74,0.3)" : "none", padding: "6px 10px", cursor: "pointer" }}>
        <Icon size={13} stroke="#bcd2c4" sw={2}><rect x="3.5" y="4.5" width="17" height="6" rx="1" /><rect x="3.5" y="13.5" width="17" height="6" rx="1" /></Icon>
        <span style={{ color: "#f5f2ea", fontSize: 13.5, fontWeight: 700 }}>All sites</span>
        <span style={{ color: "#9aa890", fontSize: 9 }}>{selectorOpen ? "▴" : "▾"}</span>
      </span>
      <span style={{ width: 1, height: 22, background: "rgba(255,255,255,0.2)" }} />
      <span style={{ display: "flex", alignItems: "center", gap: 1, height: "100%" }}>
        {tab("directory", "Directory")}
        {tab("research", "Research")}
        {tab("about", "About", true)}
      </span>
      <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 1 }}>
          <span style={{ color: "#bcd2c4", fontSize: 14, padding: "0 11px", cursor: "pointer" }}>Docs</span>
          <span style={{ color: "#bcd2c4", fontSize: 14, padding: "0 11px", cursor: "pointer" }}>Wiki</span>
        </span>
        <span style={{ width: 1, height: 22, background: "rgba(255,255,255,0.2)" }} />
        <span onClick={() => onNav && onNav("submit")} style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(255,255,255,0.16)", border: "1px solid rgba(255,255,255,0.26)", padding: "6px 10px", cursor: "pointer" }}>
          <Icon size={13} stroke="#f5f2ea" sw={2.2}><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></Icon>
          <span style={{ color: "#f5f2ea", fontSize: 13, fontWeight: 600 }}>Submit</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 7, background: "rgba(255,255,255,0.16)", border: "1px solid rgba(255,255,255,0.26)", padding: "6px 10px", cursor: "pointer" }}>
          <Icon size={14} stroke="#f5f2ea" d="M4 6.5 A2.2 2.2 0 0 1 6.2 4.3 H17.8 A2.2 2.2 0 0 1 20 6.5 V13 A2.2 2.2 0 0 1 17.8 15.2 H9.5 L5.5 18.7 V15.2 A2.2 2.2 0 0 1 4 13 Z" />
          <span style={{ color: "#f5f2ea", fontSize: 13, fontWeight: 600 }}>Ask</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 7, background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.2)", padding: "6px 10px", width: 150 }}>
          <Icon size={14} stroke="#bcd2c4" sw={2}><circle cx="11" cy="11" r="6.5" /><line x1="16" y1="16" x2="21" y2="21" /></Icon>
          <span style={{ color: "#bcd2c4", fontSize: 13 }}>Search…</span>
          <span style={{ marginLeft: "auto", color: "#9aa890", fontSize: 11, fontFamily: "var(--font-mono)", border: "1px solid rgba(255,255,255,0.25)", padding: "0 5px" }}>⌘K</span>
        </span>
      </span>
    </div>
  );
}

Object.assign(window, { DirectoryChrome, WmIcon: Icon });
