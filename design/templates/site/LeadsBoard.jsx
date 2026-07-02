// Watermark — the leads board. Every gap we're chasing on a site, in the open, filterable by kind.
//
// Mirrors the shipped `network/american-sugar-creek-allen-co/leads.astro` + the curated `lib/leads.ts`:
// a two-column board (filtered list + a right rail), a stats strip, and — per lead — a status chip,
// an evidence tag (`[open]` = a documented gap / `[inference]` = a labeled reading; never
// `[verified]`), an optional GitHub tracking-issue link, and a stable mono id. PROVENANCE DISCIPLINE:
// every lead traces to a real committed source; the design comp's fabricated contributor avatars +
// "updated 2h ago" / "3 looking" standing counts are deliberately dropped. Filtering is no-JS radio +
// `:checked` in the impl; React state here (a design canvas can't ship the radio CSS).
function LeadsBoard({ onBack }) {
  const { Eyebrow } = window.WatermarkDesignSystem_dbe30a;
  const [filter, setFilter] = React.useState("all");

  // Presentation vocab (mirror KIND_META / STATUS_META). chip/tag swatches use the evidence palette.
  const KIND = {
    signal: { label: "Signal", action: "Help confirm" },
    question: { label: "Open question", action: "Answer this" },
    redaction: { label: "Redaction", action: "Fill the gap" },
    claim: { label: "Claim", action: "Corroborate" },
  };
  const STATUS = {
    low: { label: "Low confidence", fg: "var(--ev-inference-fg)", bg: "var(--ev-inference-bg)" },
    unanswered: { label: "Unanswered", fg: "var(--ev-open-fg)", bg: "var(--ev-open-bg)" },
    withheld: { label: "Withheld", fg: "var(--ev-open-fg)", bg: "var(--ev-open-bg)" },
    review: { label: "Under review", fg: "var(--ev-inference-fg)", bg: "var(--ev-inference-bg)" },
  };
  const TAG = {
    open: { fg: "var(--ev-open-fg)", bg: "var(--ev-open-bg)" },
    inference: { fg: "var(--ev-inference-fg)", bg: "var(--ev-inference-bg)" },
  };

  // The real curated leads (lib/leads.ts) — every one traces to a committed source.
  const LEADS = [
    { id: "PRR-04", kind: "redaction", status: "withheld", tag: "open", title: "The project's cost-benefit analysis is withheld", detail: "Item 4 of the BOSC public-records request — the projected tax-revenue impact and public-ROI inputs — is held by county legal counsel under R.C. 149.43 and the §9.66(D) data-center exemption. Not produced.", source: "Allen County PRR · item 4", note: "the one to watch" },
    { id: "PTI-313MW", kind: "redaction", status: "withheld", tag: "open", title: "The per-engine output behind the 313 MW figure is trade-secret-redacted", detail: "The final air permit-to-install confirms the generator count and three-hall emission-unit grouping, but the per-engine ekW behind the disclosed 313 MW is redacted as trade secret.", source: "OEPA PTI · eDoc 4132514" },
    { id: "ASWCD-PLANS", kind: "redaction", status: "withheld", tag: "open", title: "The site plan sets are withheld twice over", detail: "The County withholds the BOSC-1A plan sets; the Soil & Water district shields the same documents again under R.C. 149.433 and R.C. 1333.61 (trade secret), a ground that reaches even the plan-share links inside produced emails.", source: "Allen SWCD · §149.433 / §1333.61" },
    { id: "PRR-16", kind: "redaction", status: "withheld", tag: "open", title: "The county website's edit history is disclaimed, not absent", detail: "Item 16 was answered “no records — we don't manage the website,” yet the WordPress /revisions endpoint returns HTTP 401 (gated, not 404). The version history exists; custody sits with the host.", source: "Allen County PRR · item 16 · contested" },
    { id: "ASWCD-03", kind: "question", status: "review", tag: "open", title: "Wetland determination: “no records” — but a produced inspection says otherwise", detail: "The SWCD answered “no records” for the 0.7-acre forested wetland, yet a produced site inspection records that “the existing wetland was mitigated.” A produced record contradicts the answer.", source: "Allen SWCD · item 3" },
    { id: "ASWCD-04", kind: "question", status: "review", tag: "open", title: "Farm-tile drainage impact: “no records” — yet a failure is photographed", detail: "The SWCD answered “no records” on tile / agricultural-drainage impact, but the 2026-06-05 inspection documents an east farm-tile diversion-swale failure.", source: "Allen SWCD · item 4" },
    { id: "FORCEMAIN-MGD", kind: "question", status: "unanswered", tag: "open", title: "Nobody owns the forcemain's MGD design capacity", detail: "The Hume / Shawnee forcemain's design capacity is disclaimed by every county body — each points to Ohio EPA or the townships. Batch 2 produced the financing and the engineering contract, not the MGD figure.", source: "Cross-production referral · item 9" },
    { id: "CORRIDOR-NPDES", kind: "signal", status: "low", tag: "open", title: "The corridor environmental permits are owned by no county body", detail: "The NPDES construction-stormwater / SWPPP records for the forcemain corridors sit with no county custodian — each “no records” answer refers onward to Ohio EPA or the townships.", source: "Cross-production referral map", issue: 151 },
    { id: "PRR-02", kind: "question", status: "unanswered", tag: "open", title: "County ⇄ DoD / federal-contractor comms — narrowed to nothing", detail: "Item 2 sought County communications with DoD or federal contractors (GDIT, GDLS) about the American Township facility. The county narrowed the ask and returned “no records.”", source: "Allen County PRR · item 2 · narrowed" },
    { id: "PRR-19", kind: "question", status: "unanswered", tag: "open", title: "County ⇄ engineer-of-record (EMH&T) comms not produced", detail: "Item 19 sought County communications with EMH&T. None produced as to the Commissioners; the SWCD produced its own EMH&T emails, but the County's are still owed.", source: "Allen County PRR · item 19 · owed" },
    { id: "GLRI-INSTRUMENT", kind: "question", status: "unanswered", tag: "open", title: "The grant instrument behind the $650k Lost Creek project", detail: "The funding source is verified — a GLRI subaward through Ohio EPA, OSU portion $327,450 — but the signed award instrument (deliverables, match, reporting) is still owed.", source: "Ohio EPA GLRI subaward files · owed" },
    { id: "OSU-MONITORING", kind: "signal", status: "low", tag: "open", title: "The OSU monitoring data quantifying the Maumee-headwater load", detail: "Continuous flow and water-quality from three ISCO6712 sites would quantify the actual nutrient / flow reduction on Lost Creek. The load-reduction table is referenced on the captured SWCD page but not transcribed.", source: "Allen SWCD capture · untranscribed" },
    { id: "H2-AUTH", kind: "question", status: "unanswered", tag: "inference", title: "The campus's federal authorization posture is undisclosed", detail: "The Lima Army Tank Plant is co-located with the campus — documented geography under hypothesis H2 — but the campus's authorization posture (FedRAMP / DoD impact level) is undisclosed, so the causal link remains an inference.", source: "Hypothesis H2 · defense nexus" },
    { id: "H1-DRAW", kind: "claim", status: "low", tag: "inference", title: "The consumptive cooling draw against the river's cited 7Q10", detail: "The Ottawa's design low flow is about 0.2 cfs (cited); the campus's consumptive cooling loss is the keystone of hypothesis H1. The measured draw against that 7Q10 is predicted evidence the record still needs to close.", source: "Hypothesis H1 · water & power" },
  ];

  const FILTERS = [["all", "All"], ["signal", "Signals"], ["question", "Questions"], ["redaction", "Redactions"], ["claim", "Claims"]];
  const count = (k) => (k === "all" ? LEADS.length : LEADS.filter((l) => l.kind === k).length);
  const shown = filter === "all" ? LEADS : LEADS.filter((l) => l.kind === filter);

  // Stats strip — all derived from the real leads (leadStats()).
  const nWithheld = LEADS.filter((l) => l.status === "withheld").length;
  const nReview = LEADS.filter((l) => l.status === "review").length;
  const STATS = [
    [LEADS.length, "open leads", "var(--ev-inference-fg)"],
    [nWithheld, "withheld / sealed", "var(--ev-open-fg)"],
    [nReview, "under review", "var(--ev-inference-fg)"],
    [3, "closed recently", "var(--forest)"],
  ];

  const LIFECYCLE = [
    ["1", "Logged as open", "It joins this queue immediately, labeled as unverified inference."],
    ["2", "Picked up", "Contributors gather sources; the record team reviews them."],
    ["3", "Corroborated", "If a source checks out, the lead enters the record with its citation."],
    ["✓", "The bar moves", "A closed lead nudges the site up the completeness curve."],
  ];
  const CLOSED = [
    ["NPDES construction-stormwater coverage located — 2GC08468*AG", "closes #143 + #154 · sourced 2026-06-16"],
    ["County wastewater universe (PRR items 5–15) produced", "PRR batch 2 · sourced 2026-06-12"],
    ["GLRI funding source resolved — OSU $327,450, 2023–2025", "Shedekar CV · sourced 2026-06-06"],
  ];

  const railKicker = (text, forest) => (
    <div style={{ fontSize: 10.5, letterSpacing: "1px", textTransform: "uppercase", fontWeight: 800, color: forest ? "var(--forest)" : "var(--ink-faint)", marginBottom: 11 }}>{text}</div>
  );

  return (
    <div style={{ color: "var(--ink)", padding: "30px 36px 40px" }}>
      <a onClick={onBack} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, fontWeight: 600, color: "var(--forest)", textDecoration: "none", marginBottom: 14, cursor: "pointer" }}>← Back to the site</a>

      {/* header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 20, flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 540px", maxWidth: 680 }}>
          <Eyebrow tone="forest" style={{ color: "var(--ev-inference-fg)" }}>Open investigation · Lima, Ohio</Eyebrow>
          <h1 style={{ fontSize: 32, fontWeight: 800, letterSpacing: "-0.8px", margin: "8px 0 6px" }}>Open leads</h1>
          <p style={{ fontSize: 15.5, lineHeight: 1.55, color: "var(--ink-prose)", margin: 0 }}>Every gap we're chasing on this site, in the open. Each lead is <b>unverified inference</b> until a source corroborates it — and every one traces to the <a href="#" style={{ color: "var(--forest)", fontWeight: 600 }}>corpus-completeness audit</a> or a working hypothesis. Pick one up, answer it, or bring the document that closes it.</p>
        </div>
        <a href="#" style={{ flex: "0 0 auto", display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13.5, fontWeight: 700, color: "#f5f2ea", background: "var(--forest)", border: "1.5px solid var(--forest)", padding: "10px 16px", textDecoration: "none" }}>
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
          Submit a lead
        </a>
      </div>

      {/* stats strip */}
      <div style={{ display: "flex", gap: 32, flexWrap: "wrap", margin: "22px 0 6px", paddingBottom: 20, borderBottom: "1px solid var(--line-faint)" }}>
        {STATS.map(([n, l, c]) => (
          <div key={l}><div style={{ fontSize: 28, fontWeight: 800, fontFamily: "var(--font-mono)", letterSpacing: "-1px", color: c }}>{n}</div><div style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 2 }}>{l}</div></div>
        ))}
      </div>

      {/* layout: filtered list + rail */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 26, alignItems: "start", marginTop: 18 }}>
        {/* main */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
            {FILTERS.map(([k, label]) => {
              const on = filter === k;
              return (
                <span key={k} onClick={() => setFilter(k)} style={{ display: "inline-flex", alignItems: "center", gap: 7, fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, letterSpacing: "0.4px", textTransform: "uppercase", color: on ? "#f5f2ea" : "var(--ink-muted)", background: on ? "var(--ink)" : "transparent", border: `1px solid ${on ? "var(--ink)" : "var(--line-2)"}`, padding: "5px 11px", cursor: "pointer" }}>{label}<span style={{ fontSize: 11, opacity: 0.7 }}>{count(k)}</span></span>
              );
            })}
          </div>
          <div style={{ fontSize: 11.5, fontFamily: "var(--font-mono)", letterSpacing: "0.4px", textTransform: "uppercase", color: "var(--ink-faint)", marginBottom: 12 }}>{shown.length} open leads · unverified</div>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {shown.map((l) => {
              const k = KIND[l.kind], s = STATUS[l.status], t = TAG[l.tag];
              return (
                <article key={l.id} style={{ display: "flex", gap: 16, alignItems: "stretch", background: "var(--surface-card)", border: "1px solid var(--line-hair)", borderLeft: `3px solid ${l.tag === "open" ? "var(--ev-open-fg)" : "var(--ev-inference-fg)"}`, padding: "15px 17px" }}>
                  <div style={{ flex: "1 1 auto", minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap", marginBottom: 7 }}>
                      <span style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.4px", textTransform: "uppercase", color: "var(--ink-muted)" }}>{k.label}</span>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 700, color: s.fg, background: s.bg, padding: "2px 9px", borderRadius: 999 }}><span style={{ width: 5, height: 5, borderRadius: "50%", background: s.fg }} />{s.label}</span>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700, color: t.fg, background: t.bg, padding: "1px 6px" }}>[{l.tag}]</span>
                      <span style={{ fontSize: 11.5, color: "var(--ink-faint)" }}>{l.source}</span>
                    </div>
                    <h2 style={{ fontSize: 16, fontWeight: 700, letterSpacing: "-0.2px", lineHeight: 1.3, margin: "0 0 5px" }}>{l.title}</h2>
                    <p style={{ fontSize: 13.5, lineHeight: 1.5, color: "var(--ink-muted)", margin: 0 }}>{l.detail}</p>
                    {(l.note || l.issue) && (
                      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 9 }}>
                        {l.note && <span style={{ fontSize: 12, fontStyle: "italic", color: "var(--ink-faint)" }}>{l.note}</span>}
                        {l.issue && <a href="#" style={{ display: "inline-flex", alignItems: "center", gap: 5, fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--ink-muted)", textDecoration: "none" }} title="Linked tracking issue">▣ #{l.issue}</a>}
                      </div>
                    )}
                  </div>
                  <div style={{ flex: "0 0 auto", display: "flex", flexDirection: "column", alignItems: "flex-end", justifyContent: "space-between", gap: 12 }}>
                    <a href="#" style={{ whiteSpace: "nowrap", fontSize: 13, fontWeight: 700, color: "var(--forest)", textDecoration: "none" }}>{k.action} →</a>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-ghost)" }}>{l.id}</span>
                  </div>
                </article>
              );
            })}
          </div>

          <p style={{ fontSize: 12.5, color: "var(--ink-faint)", marginTop: 16 }}>Showing all {shown.length} open leads. Closed leads move into <a href="#" style={{ color: "var(--forest)", fontWeight: 600 }}>the record →</a></p>
        </div>

        {/* rail */}
        <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ background: "var(--ink)", padding: "18px 19px", color: "#f5f2ea" }}>
            <div style={{ fontSize: 10.5, letterSpacing: "1.1px", textTransform: "uppercase", color: "#a7b0a3", fontWeight: 700 }}>Build the record</div>
            <div style={{ fontSize: 18, fontWeight: 800, marginTop: 5, letterSpacing: "-0.3px" }}>Know something we don't?</div>
            <p style={{ fontSize: 13, color: "#bcd2c4", lineHeight: 1.5, margin: "7px 0 14px" }}>A document, a name, a correction. We log every submission as a lead — not a verdict — and review before the record changes.</p>
            <a href="#" style={{ display: "inline-block", fontSize: 13, fontWeight: 700, color: "var(--ink)", background: "#f5f2ea", padding: "9px 15px", textDecoration: "none" }}>Submit a lead →</a>
          </div>

          <div style={{ background: "var(--surface-card)", border: "1px solid var(--line-hair)", padding: "18px 19px" }}>
            {railKicker("How a lead closes")}
            {LIFECYCLE.map(([num, title, desc], i) => (
              <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start", paddingBottom: i < LIFECYCLE.length - 1 ? 14 : 0 }}>
                <div style={{ flex: "0 0 auto", display: "flex", flexDirection: "column", alignItems: "center", alignSelf: "stretch" }}>
                  <span style={{ width: 22, height: 22, background: "var(--forest-tint)", border: "2px solid var(--forest-line)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 800, color: "var(--forest)", fontFamily: "var(--font-mono)" }}>{num}</span>
                  {i < LIFECYCLE.length - 1 ? <span style={{ flex: "1 1 auto", width: 2, background: "var(--bone-page)", marginTop: 3, minHeight: 5 }} /> : null}
                </div>
                <div style={{ paddingTop: 1 }}><div style={{ fontSize: 13, fontWeight: 700 }}>{title}</div><div style={{ fontSize: 11.5, color: "var(--ink-faint)", lineHeight: 1.45, marginTop: 2 }}>{desc}</div></div>
              </div>
            ))}
          </div>

          <div style={{ background: "var(--surface-card)", border: "1px solid var(--line-hair)", padding: "18px 19px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 12 }}>
              {railKicker("Recently closed", true)}
              <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 700, color: "var(--forest)", marginBottom: 11 }}><span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--forest)" }} />sourced</span>
            </div>
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 12 }}>
              {CLOSED.map(([title, meta]) => (
                <li key={title} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <span style={{ flex: "0 0 auto", width: 16, height: 16, marginTop: 2, borderRadius: "50%", background: "var(--forest)", color: "#f5f2ea", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9, fontWeight: 800 }}>✓</span>
                  <span><span style={{ display: "block", fontSize: 12.5, fontWeight: 600, lineHeight: 1.35 }}>{title}</span><span style={{ display: "block", fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--ink-faint)", marginTop: 2 }}>{meta}</span></span>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
Object.assign(window, { LeadsBoard });
