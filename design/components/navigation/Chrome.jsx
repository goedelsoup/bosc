import React, { useState } from "react";

/**
 * Watermark Chrome — the global ink bar. Two tiers:
 * - "network": the directory's own tabs (Directory · Research · About).
 * - "site": inside a site, the same bar becomes that site's tabs
 *   (The site · The story · The record) plus a site chip breadcrumb
 *   (e.g. "Lima · BOSC") and an optional phase pill (Live, Building…).
 *
 * Lifted from the Watermark platform template (templates/watermark-platform/Chrome.dc.html) —
 * keep the two in sync if you evolve the nav here.
 */

const DEFAULT_NETWORK_TABS = [
  { key: "report", label: "Directory", href: "#" },
  { key: "research", label: "Research", href: "#", children: [
    { key: "hypotheses", label: "Hypotheses", sub: "All three, on one map", href: "#" },
    { key: "h1", label: "H1 · Water & Power", href: "#" },
    { key: "h2", label: "H2 · Defense & Federal", href: "#" },
    { key: "h3", label: "H3 · Corporate & Capital", href: "#" },
    { rule: true },
    { key: "methodology", label: "Methodology", href: "#" },
  ] },
  { key: "about", label: "About", href: "#", children: [
    { key: "about-site", label: "About this site", href: "#" },
    { key: "sustainability", label: "Sustainability", sub: "GreenOps & the usage report", href: "#" },
  ] },
];

const DEFAULT_SITE_TABS = [
  { key: "site", label: "The site", href: "#" },
  { key: "story", label: "The story", href: "#" },
  { key: "record", label: "The record", href: "#" },
];

export function Chrome({
  tier = "site",
  active,
  brandHref = "#",
  tabs,
  site = "Lima",
  codename = "BOSC",
  phase = "Live",
  submitHref = "#",
  rightSlot,
  selector,
  style,
  ...rest
}) {
  const isNetwork = tier === "network";
  const [openMenu, setOpenMenu] = useState(null);
  const [selOpen, setSelOpen] = useState(false);
  const tabList = tabs || (isNetwork ? DEFAULT_NETWORK_TABS : DEFAULT_SITE_TABS);
  const activeKey = active ?? (isNetwork ? "report" : "site");

  return (
    <div className="wm-chrome" style={{ fontFamily: "var(--font-sans)", ...style }} {...rest}>
      {openMenu != null && (
        <div onClick={() => setOpenMenu(null)} style={{ position: "fixed", inset: 0, zIndex: 55 }} />
      )}
      <div style={{
        background: "var(--ink)", padding: "0 16px", minHeight: 56,
        display: "flex", alignItems: "center", gap: 13, flexWrap: "wrap",
      }}>
        <a href={brandHref} style={{ display: "flex", alignItems: "center", textDecoration: "none", color: "var(--bone-surface)", padding: "7px 0" }}>
          <span style={{ fontWeight: 800, fontSize: 16, letterSpacing: "-0.2px" }}>
            Watermark<span style={{ color: "var(--forest-bright)" }}>.</span>
          </span>
        </a>
        <span style={{ color: "#566159", fontSize: 15 }}>/</span>

        <span
          onClick={() => setSelOpen((v) => !v)}
          style={{
            display: "flex", alignItems: "center", gap: 7, background: "rgba(255,255,255,0.16)",
            border: `1px solid ${selOpen ? "rgba(150,200,170,0.55)" : "rgba(255,255,255,0.26)"}`,
            boxShadow: selOpen ? "0 0 0 2px rgba(31,111,74,0.3)" : "none",
            padding: "6px 10px", cursor: "pointer",
          }}
        >
          {isNetwork && (
            <span style={{ display: "flex", alignItems: "center", color: "#bcd2c4" }}>
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3.5" y="4.5" width="17" height="6" rx="1"/><rect x="3.5" y="13.5" width="17" height="6" rx="1"/></svg>
            </span>
          )}
          <span style={{ color: "var(--bone-surface)", fontSize: 13.5, fontWeight: 700 }}>{isNetwork ? "All sites" : site}</span>
          {!isNetwork && (
            <span style={{ color: "#bcd2c4", fontSize: 9.5, fontWeight: 700, letterSpacing: "0.5px", textTransform: "uppercase", fontFamily: "var(--font-mono)", background: "rgba(255,255,255,0.14)", border: "1px solid rgba(255,255,255,0.26)", padding: "1px 5px" }}>{codename}</span>
          )}
          <span style={{ color: "#9aa890", fontSize: 9 }}>{selOpen ? "▴" : "▾"}</span>
        </span>

        <span style={{ display: "flex", alignItems: "center", gap: 1, alignSelf: "stretch", marginLeft: 1 }}>
          {tabList.map((t) => {
            const kids = t.children || [];
            const hasChildren = kids.length > 0;
            const isActive = t.key === activeKey || kids.some((c) => c.key === activeKey);
            const menuOpen = openMenu === t.key;
            return (
              <span key={t.key} style={{ position: "relative", zIndex: 56, alignSelf: "stretch", display: "flex", alignItems: "center" }}>
                <a
                  href={hasChildren ? "#" : t.href}
                  onClick={hasChildren ? (e) => { e.preventDefault(); setOpenMenu(menuOpen ? null : t.key); } : undefined}
                  style={{
                    color: isActive ? "var(--bone-surface)" : "#bcd2c4",
                    fontSize: 14, fontWeight: isActive ? 600 : 400, padding: "0 13px",
                    alignSelf: "stretch", display: "flex", alignItems: "center", gap: 5,
                    boxShadow: isActive ? "inset 0 -3px 0 var(--bone-surface)" : "none",
                    textDecoration: "none", cursor: "pointer", whiteSpace: "nowrap",
                  }}
                >
                  {t.label}
                  {hasChildren && <span style={{ fontSize: 8, color: "#9aa890" }}>{menuOpen ? "▴" : "▾"}</span>}
                </a>
                {menuOpen && hasChildren && (
                  <div style={{ position: "absolute", top: "calc(100% - 1px)", left: 0, minWidth: 250, maxHeight: "74vh", overflow: "auto", background: "#1c2822", border: "1px solid #33423a", boxShadow: "0 18px 38px -16px rgba(0,0,0,0.6)", zIndex: 60, padding: 5 }}>
                    {kids.map((c, i) => c.rule ? (
                      <div key={i} style={{ height: 1, background: "#33423a", margin: "5px 9px" }} />
                    ) : (
                      <a key={c.key || i} href={c.href || "#"} style={{ display: "flex", alignItems: "baseline", gap: 8, padding: "9px 11px", textDecoration: "none", color: "#cdd6cd", fontSize: 13.5, fontWeight: 500, lineHeight: 1.3 }}>
                        <span style={{ flex: "1 1 auto", minWidth: 0 }}>
                          {c.label}
                          {c.sub && <span style={{ display: "block", fontSize: 11, color: "#8c9789", fontWeight: 400, marginTop: 2 }}>{c.sub}</span>}
                        </span>
                        {c.meta && <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.3px", textTransform: "uppercase", color: "#8c9789", whiteSpace: "nowrap" }}>{c.meta}</span>}
                      </a>
                    ))}
                  </div>
                )}
              </span>
            );
          })}
        </span>

        {!isNetwork && phase && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11.5, fontWeight: 700, color: "var(--bone-surface)", background: "rgba(31,111,74,0.32)", border: "1px solid rgba(150,200,170,0.5)", padding: "3px 10px" }}>
            <span style={{ width: 6, height: 6, background: "var(--forest-bright)" }} />{phase}
          </span>
        )}

        <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
          {rightSlot || (
            <>
              <span style={{ display: "flex", alignItems: "center", gap: 1 }}>
                <a href="#" style={{ color: "#bcd2c4", fontSize: 14, padding: "0 11px", textDecoration: "none" }}>Docs</a>
                <a href="#" style={{ color: "#bcd2c4", fontSize: 14, padding: "0 11px", textDecoration: "none" }}>Wiki</a>
              </span>
              <span style={{ width: 1, height: 22, background: "rgba(255,255,255,0.2)" }} />
              <a href={submitHref} style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(127,184,154,0.16)", border: "1px solid rgba(150,200,170,0.55)", padding: "6px 11px", cursor: "pointer", textDecoration: "none" }}>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--forest-bright)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                <span style={{ color: "var(--bone-surface)", fontSize: 13, fontWeight: 600 }}>Submit</span>
              </a>
              <span style={{ display: "flex", alignItems: "center", gap: 7, background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.2)", padding: "6px 10px", width: 160, cursor: "pointer" }}>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#bcd2c4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="6.5"/><line x1="16" y1="16" x2="21" y2="21"/></svg>
                <span style={{ color: "#bcd2c4", fontSize: 13 }}>Search…</span>
                <span style={{ marginLeft: "auto", color: "#9aa890", fontSize: 11, fontFamily: "var(--font-mono)", border: "1px solid rgba(255,255,255,0.25)", padding: "0 5px" }}>⌘K</span>
              </span>
            </>
          )}
        </span>
      </div>

      {selOpen && selector}
    </div>
  );
}
