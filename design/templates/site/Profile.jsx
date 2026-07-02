// Watermark — a wiki profile screen (site tier). ProfileHeader + the records that
// mention this entity + a back link. The header mirrors the shipped `ProfileHeader.astro`
// (rendered by the wiki/{entities,concepts,people} pages): it carries a **seen-in-story**
// backlink and a **suggest-correction** foot (plus a graph link + per-relationship hrefs).
// The "records that mention this" list is page-composed, not part of the header comp.
function ProfileScreen({ onBack }) {
  const { Eyebrow, ProfileHeader, RecordBlock } = window.WatermarkDesignSystem_dbe30a;
  const PROFILE = {
    kindLabel: "Entity · shell company", name: "Bistrozzi LLC", variants: ["Bistrozzi Addition LLC", "DE 7•••214"],
    descriptor: "Delaware LLC; grantee on the seven-parcel deed chain. Shares a registered agent and PMB with two sibling shells — the common-control plumbing the story traces in Chapter 1.",
    evidence: "inference", graphHref: "#graph", relLabel: "Graph neighborhood",
    // The story backlink — surfaces where this entity is first read in the narrative.
    seenIn: { href: "#who", ch: 1, label: "Who is actually building this?" },
    stats: [
      { label: "Parcels controlled", value: "7", evidence: "verified", sub: "340.2 ac" },
      { label: "Public price", value: "$600k", evidence: "verified", sub: "1 of 7 parcels" },
      { label: "Sibling shells", value: "3", evidence: "inference", sub: "shared agent / PMB" },
      { label: "Records", value: "12", evidence: "verified", sub: "across 4 groups" },
    ],
    attrs: [
      { label: "State of formation", value: "Delaware", tag: "verified" },
      { label: "Registered agent", value: "shared · CT Corp", tag: "verified" },
      { label: "First recorded", value: "2025-08-13" },
      { label: "Ultimate control", value: "Google (AEDG)", tag: "inference" },
    ],
    relationships: [
      { kind: "grantor", label: "Brenneman Trusts", href: "#brenneman" },
      { kind: "sibling", label: "Tilted Gate LLC", href: "#tilted-gate" },
      { kind: "contractor", label: "Tetra Tech", href: "#tetra-tech" },
    ],
    // The suggest-correction foot — every profile is correctable, like every record.
    correctHref: "#correct",
  };
  const records = [
    { title: "Limited Warranty Deed", recordId: "instr. 202508130008300", source: { collection: "Allen County Recorder" }, evidence: "verified", headlineValue: "$600,000", seenIn: { href: "#who", ch: 1, label: "Who is actually building this?" } },
    { title: "Sibling-shell agent match", recordId: "SOS · CT Corp", source: { collection: "OH Sec. of State" }, evidence: "inference", headlineValue: "3 shells", headlineWarn: true },
    { title: "AEDG offtaker disclosure", recordId: "AEDG-2026-03", source: { collection: "Econ. dev. release" }, evidence: "verified", headlineValue: "Google" },
  ];
  return (
    <div style={{ color: "var(--ink)", padding: "28px 32px 40px" }}>
      <a onClick={onBack} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, fontWeight: 600, color: "var(--forest)", textDecoration: "none", marginBottom: 16, cursor: "pointer" }}>← The record</a>
      <ProfileHeader profile={PROFILE} />
      <div style={{ marginTop: 24 }}>
        <Eyebrow tone="faint" style={{ marginBottom: 12 }}>Records that mention this entity · 12</Eyebrow>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {records.map((r, i) => <RecordBlock key={i} density="compact" record={r} />)}
        </div>
      </div>
    </div>
  );
}
Object.assign(window, { ProfileScreen });
