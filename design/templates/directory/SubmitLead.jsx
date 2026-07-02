// Watermark — Submit a Lead (network tier). The participation form: pick a lead type,
// state the claim, point to evidence, optional contact — plus the "what happens next" rail.
//
// Two states mirror the shipped `src/components/SubmitForm.astro`: the form goes LIVE only when
// the Turnstile site key is present at build time; until the endpoint is bootstrapped the page is
// honest and renders a "not live yet" fallback with a manual GitHub-issue link. The canvas toggle
// (top-right) previews both. Reached from a record's "✎ Suggest a correction" deep-link, the
// **ref-context banner** surfaces which record you're correcting (filled client-side from the
// query string; here it's shown populated). The right rail / 4 lead types / attach / credit
// checkbox are spec-ahead extras the live form doesn't carry yet (a separate reconcile).
function SubmitLead() {
  const { Eyebrow, TextField, RadioCard, Checkbox, Button } = window.WatermarkDesignSystem_dbe30a;
  const [type, setType] = React.useState("correction");
  const [credit, setCredit] = React.useState(true);
  const [enabled, setEnabled] = React.useState(true);
  const TYPES = [
    ["correction", "Correction", "A figure or fact in the record is wrong."],
    ["source", "New source", "A document we don't have yet."],
    ["answer", "Answer a question", "Resolve an open lead or unknown."],
    ["tip", "Tip / signal", "Something to look into — no source yet."],
  ];
  const pipeline = [
    ["1", "Logged as an open lead", "It joins the site's lead queue immediately, labeled as unverified."],
    ["2", "Reviewed by the record team", "We check it against the source you gave — or go find one."],
    ["3", "Corroborated → sourced", "If it checks out, it enters the record with its citation."],
    ["✓", "The bar moves", "A confirmed lead nudges the site up the completeness curve."],
  ];
  return (
    <div style={{ color: "var(--ink)", padding: "34px 28px 44px" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 520px" }}>
          <Eyebrow tone="forest">Participate · build the record</Eyebrow>
          <h1 style={{ fontSize: 38, fontWeight: 800, letterSpacing: "-0.7px", margin: "7px 0 10px", lineHeight: 1.05 }}>Submit a lead</h1>
          <p style={{ maxWidth: 760, fontSize: 16.5, lineHeight: 1.55, color: "var(--ink-muted)", margin: 0 }}>Every confirmed figure in this record started as a lead someone brought in. Tell us what you know — a document, a name, a number that's wrong — and <b>how we can check it.</b> A submission opens a public, labeled GitHub issue a maintainer reviews; it never changes the record itself.</p>
        </div>
        {/* canvas-only: preview the live form vs the not-yet-live fallback (the build-time `enabled` gate) */}
        <button onClick={() => setEnabled((v) => !v)} style={{ flex: "0 0 auto", marginTop: 6, fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.5px", textTransform: "uppercase", color: "var(--ink-faint)", background: "var(--bone-sunk)", border: "1px dashed var(--line-2)", padding: "7px 12px", cursor: "pointer" }}>
          canvas: {enabled ? "live ✓" : "not live yet"} ⇄
        </button>
      </div>

      {/* Ref-context banner — shown when reached from a record's "✎ Suggest a correction"
          deep-link (?ref_kind&ref_id&ref_label). Lives OUTSIDE the enabled/disabled branch so the
          context survives in both states; here it's rendered populated. */}
      <div style={{ display: "flex", alignItems: "center", gap: 13, border: "1px solid var(--forest-line)", borderLeft: "3px solid var(--forest)", background: "var(--forest-tint)", padding: "12px 15px", marginTop: 22 }}>
        <span aria-hidden="true" style={{ fontSize: 18, color: "var(--forest)" }}>✎</span>
        <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: "1 1 auto" }}>
          <span style={{ fontSize: 10.5, letterSpacing: "0.7px", textTransform: "uppercase", fontWeight: 800, color: "var(--forest)" }}>You're correcting a specific record</span>
          <span style={{ fontSize: 14, fontWeight: 700 }}>Limited Warranty Deed · Brenneman → Bistrozzi</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--ink-faint)" }}>recorder · instr. 202508130008300</span>
        </div>
        <button style={{ flex: "0 0 auto", fontSize: 12, fontWeight: 600, color: "var(--ink-muted)", background: "transparent", border: "1px solid var(--line-2)", padding: "6px 11px", cursor: "pointer" }}>Not this record? <span aria-hidden="true">✕</span></button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 22, alignItems: "start", marginTop: 18 }}>
        {/* form / fallback */}
        {enabled ? (
          <div style={{ background: "var(--surface-card)", border: "1px solid var(--line-hair)", padding: "20px 22px 24px", display: "flex", flexDirection: "column", gap: 20 }}>
            <div>
              <div style={{ fontSize: 11, letterSpacing: "0.6px", textTransform: "uppercase", color: "var(--ink-faint)", fontWeight: 800, marginBottom: 9 }}>1 · What kind of lead?</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 9 }}>
                {TYPES.map(([k, t, d]) => <RadioCard key={k} title={t} desc={d} selected={type === k} onSelect={() => setType(k)} />)}
              </div>
            </div>
            <TextField label="2 · What's the claim or correction?" multiline placeholder='e.g. "Parcel 4’s price wasn’t blank — the auditor’s transfer record lists it at $1.95M. The deed just omitted it."' hint={<><span style={{ color: "var(--ink-ghost)" }}>ⓘ</span> Be specific. One checkable claim per lead works best.</>} />
            <div>
              <div style={{ fontSize: 11, letterSpacing: "0.6px", textTransform: "uppercase", color: "var(--ink-faint)", fontWeight: 800, marginBottom: 9 }}>3 · Where can we verify it?</div>
              <div style={{ display: "flex", gap: 9, flexWrap: "wrap" }}>
                <TextField style={{ flex: "1 1 240px" }} placeholder="Link to a public record…" icon={<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M9 15 L15 9" /><path d="M11 6 l1.5 -1.5 a3.5 3.5 0 0 1 5 5 L17 11" /><path d="M13 18 l-1.5 1.5 a3.5 3.5 0 0 1 -5 -5 L7 13" /></svg>} />
                <span style={{ flex: "0 0 auto", display: "flex", alignItems: "center", gap: 8, border: "1px dashed var(--line-2)", padding: "11px 15px", background: "#f2efe6", cursor: "pointer", color: "var(--ink-muted)", fontSize: 13, fontWeight: 600 }}>
                  <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M12 16 V4" /><path d="M7 9 l5 -5 l5 5" /><path d="M5 20 h14" /></svg>Attach a file
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 11, border: "1px solid var(--bone-page)", padding: "10px 13px", background: "var(--bone-sunk)", marginTop: 9 }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 700, color: "var(--ev-inference-fg)", background: "var(--ev-inference-bg)", padding: "2px 9px" }}><span style={{ width: 5, height: 5, background: "var(--ev-inference-fg)" }} />no source yet?</span>
                <span style={{ fontSize: 12.5, color: "var(--ink-muted)", lineHeight: 1.45 }}>Send it anyway — we'll log it as an <b>open lead</b> and try to corroborate it ourselves.</span>
              </div>
            </div>
            <TextField label="4 · Your contact" optional="optional, if you're open to follow-up" placeholder="email or Signal — kept private" hint="Kept private; never shown on the public issue." />
            <Checkbox checked={credit} onChange={setCredit}>Credit me as a contributor (a handle, not your name)</Checkbox>

            {/* The real (unverified) Cloudflare Turnstile managed widget — NOT a pre-checked
                "verified" box. The widget challenges on submit; the script loads from
                challenges.cloudflare.com when the build carries PUBLIC_TURNSTILE_SITE_KEY. */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, width: 300, maxWidth: "100%", border: "1px solid var(--line-2)", borderRadius: 4, padding: "11px 14px", background: "#fafafa" }}>
              <span style={{ width: 24, height: 24, border: "2px solid var(--line-2)", borderRadius: 4, background: "#fff", flex: "0 0 auto" }} />
              <span style={{ fontSize: 14, color: "var(--ink-prose)", flex: "1 1 auto" }}>Verify you are human</span>
              <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", lineHeight: 1.2 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: "#f38020" }}>CLOUDFLARE</span>
                <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--ink-ghost)" }}>Privacy · Terms</span>
              </span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
              <Button variant="forest" size="lg">Send to the record team →</Button>
              <div style={{ fontSize: 12, color: "var(--ink-faint)", lineHeight: 1.45, flex: "1 1 160px" }}>No account needed. Reviewed before anything in the record changes. The issue is <b>public</b> — keep private details out of the description.</div>
            </div>
          </div>
        ) : (
          /* not-yet-live fallback — honest in every environment until the endpoint is bootstrapped */
          <div style={{ background: "var(--surface-card)", border: "1px solid var(--line-2)", borderLeft: "3px solid var(--ev-inference-fg)", padding: "20px 22px" }}>
            <div style={{ fontSize: 15, fontWeight: 800, marginBottom: 8 }}>Submissions aren't live yet</div>
            <p style={{ fontSize: 14, lineHeight: 1.6, color: "var(--ink-muted)", margin: 0 }}>
              The submissions endpoint isn't enabled in this build. In the meantime you can <a href="#" style={{ color: "var(--forest)", fontWeight: 600 }}>open a GitHub issue</a> directly (a GitHub account is required) — if you arrived here from a record, that issue is pre-filled with which record you're correcting. The anonymous form will appear here once the endpoint is live.
            </p>
          </div>
        )}

        {/* rail (spec-ahead — not in the live form yet) */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ background: "var(--surface-card)", border: "1px solid var(--line-hair)", padding: "18px 19px" }}>
            <Eyebrow tone="faint" style={{ marginBottom: 14 }}>What happens to your lead</Eyebrow>
            {pipeline.map(([num, title, desc], i) => (
              <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start", paddingBottom: i < pipeline.length - 1 ? 15 : 0 }}>
                <div style={{ flex: "0 0 auto", display: "flex", flexDirection: "column", alignItems: "center", alignSelf: "stretch" }}>
                  <span style={{ width: 24, height: 24, background: "var(--forest-tint)", border: "2px solid var(--forest-line)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10.5, fontWeight: 800, color: "var(--forest)", fontFamily: "var(--font-mono)" }}>{num}</span>
                  {i < pipeline.length - 1 ? <span style={{ flex: "1 1 auto", width: 2, background: "var(--bone-page)", marginTop: 3, minHeight: 6 }} /> : null}
                </div>
                <div style={{ paddingTop: 2 }}><div style={{ fontSize: 13.5, fontWeight: 700 }}>{title}</div><div style={{ fontSize: 12, color: "var(--ink-faint)", lineHeight: 1.45, marginTop: 2 }}>{desc}</div></div>
              </div>
            ))}
          </div>
          <div style={{ background: "var(--ink)", padding: "18px 19px", color: "#f5f2ea" }}>
            <div style={{ fontSize: 11, letterSpacing: "1px", textTransform: "uppercase", color: "#a7b0a3", fontWeight: 700 }}>This site right now</div>
            <div style={{ display: "flex", gap: 20, marginTop: 11 }}>
              {[["12", "open leads"], ["41", "contributors"], ["14%", "assembled"]].map(([n, l]) => (
                <div key={l}><div style={{ fontSize: 24, fontWeight: 800, fontFamily: "var(--font-mono)", letterSpacing: "-1px" }}>{n}</div><div style={{ fontSize: 11.5, color: "#9aa890" }}>{l}</div></div>
              ))}
            </div>
            <div style={{ fontSize: 12, color: "#bcd2c4", lineHeight: 1.5, marginTop: 12, paddingTop: 12, borderTop: "1px solid rgba(255,255,255,0.12)" }}>Your lead could be the one that moves the bar.</div>
          </div>
        </div>
      </div>
    </div>
  );
}
Object.assign(window, { SubmitLead });
