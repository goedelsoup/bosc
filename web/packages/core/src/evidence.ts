// The single source of truth for the evidence-discipline tag taxonomy (#579).
//
// Two related types, both canonical:
//  - `TagKind`    — the *data* vocabulary the corpus actually carries on a figure/record/event
//    (`verified` read from a cited record, `inference` a labelled reading, `open` withheld/
//    unresolved). This is what the feeds/teardown/end-use/defense-nexus/leads modules tag with.
//  - `EvidenceKind` — the *render* taxonomy `EvidenceTag` knows how to tint: `TagKind` plus the
//    three annotation-only kinds (`filename` provenance, `gap` scope-gap, `key` key-figure) that
//    are added at the presentation layer, never stored as a data tag.
//
// The uncertainty engine uses `assumption` where this vocabulary uses `inference` (its inputs are
// cited *bounds*, not a single reading) — a deliberate dialect, kept distinct in `uncertainty.ts`.

/** The data vocabulary: what a corpus figure/record/event is actually tagged with. */
export type TagKind = "verified" | "inference" | "open";

/** The render taxonomy `EvidenceTag` tints — `TagKind` + `reference` + the annotation-only kinds.
 *
 *  `reference` is the fourth canonical evidence class (an outside-published spec/dataset, not a
 *  record about this site). Most feeds cite external datasets in prose rather than as a stored tag,
 *  so it lives here and not in `TagKind` — which lets the documented four-tag vocabulary and the UI
 *  agree without forcing every chart/feed `Record<TagKind>` to carry a value those feeds lack. The
 *  feeds that DO store all four (`FactStatus` in `feeds.ts` — the facts feed, and the defense
 *  registers added in #1663) type against `FactStatus` and render through this taxonomy; that pair
 *  is the intended seam, not a drift. */
export type EvidenceKind = TagKind | "reference" | "filename" | "gap" | "key";

/** The four canonical evidence classes, in reading order — what a legend should explain. */
export const EVIDENCE_PRIMARY: readonly EvidenceKind[] = ["verified", "inference", "reference", "open"];

/** Kinds whose printed label differs from the kind name (design-system labels). */
export const EVIDENCE_LABELS: Partial<Record<EvidenceKind, string>> = {
  gap: "scope gap",
  key: "key figure",
};

/** A one-line reader gloss per kind — the default `EvidenceTag` tooltip and the legend copy. */
export const EVIDENCE_GLOSS: Record<EvidenceKind, string> = {
  verified: "Read from a cited record or a live source — confirmed and reproducible.",
  inference: "A labelled reading or derivation from cited inputs — reasoning, not a record.",
  reference:
    "An outside published specification or dataset — authoritative, but not a record about this site.",
  open: "Withheld, unresolved, or not yet checked — a question, not a verdict.",
  filename: "Provenance — the source file this figure was read from.",
  gap: "A scope gap — something the record does not cover.",
  key: "A key figure — the load-bearing number in this finding.",
};
