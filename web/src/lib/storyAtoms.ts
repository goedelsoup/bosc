/**
 * The Story render layer (#1096 / #1097) — the pure, framework-free half that the authoring UX and
 * the runtime renderer island both build on.
 *
 * The runtime renderer is a **client island** (React), so it can't reach the Astro presentation
 * components (`RecordBlock.astro`, `ProfileHeader.astro`, …). Instead it resolves each SDM `atom`
 * handle to a **`HydratedAtom`** — the embedded-scale render payload for that kind — and dispatches
 * on the atom's *family* (the 3 shared card families + the standalone kinds). This module owns:
 *
 *  - `HydratedAtom` + the per-kind payload shapes (a superset that echoes each kind's canonical
 *    on-site presentation at embedded scale);
 *  - the closed **family** dispatch map (`KIND_FAMILY`) — the peer of `sdm.ATOM_RENDER_SLOTS`, one
 *    render branch per kind, grouping record/doc, entity/person/place, timeline/meeting the same way
 *    the real site already shares `RecordBlock`/`ProfileHeader`/`Timeline`;
 *  - the editor's block model + the **block ⇄ DSL** serializers, so the block editor round-trips
 *    through `storyCompile`'s DSL front-end (the store persists `source_text`, never client SDM);
 *  - `hydrateFromThin` — the minimal `CatalogAtom` → `HydratedAtom` bridge used when only the thin
 *    catalog pointer is known (a dangling handle, or a kind whose live feed row isn't fetched yet).
 *
 * No React, no `node:fs` — safe to import in a build step, a page, or an island.
 */
import type { CatalogAtom, CatalogKind } from "./catalog";
import type { SdmBlock, SdmInline, StoryDocument } from "./sdm";

// --- evidence -------------------------------------------------------------------------------
/** The evidence grammar the whole platform is held to. `gap` is the oxblood "withheld" tag. */
export type EvidenceKind = "verified" | "inference" | "open" | "gap";

/** Evidence palette lookup — the ONLY place a Story chip may spend the evidence colors (the design
 *  system reserves them for evidence, never chrome). Values are CSS custom-property references. */
export const EVIDENCE_META: Record<EvidenceKind, { fg: string; bg: string; border: string; label: string }> =
  {
    verified: {
      fg: "var(--ev-verified-fg)",
      bg: "var(--ev-verified-bg)",
      border: "var(--ev-verified-border)",
      label: "verified",
    },
    inference: {
      fg: "var(--ev-inference-fg)",
      bg: "var(--ev-inference-bg)",
      border: "var(--ev-inference-border)",
      label: "inference",
    },
    open: {
      fg: "var(--ev-open-fg)",
      bg: "var(--ev-open-bg)",
      border: "var(--ev-open-border)",
      label: "open",
    },
    gap: { fg: "var(--ev-gap-fg)", bg: "var(--ev-gap-bg)", border: "var(--ev-gap-border)", label: "gap" },
  };

export function evidenceOf(value: unknown): EvidenceKind {
  return value === "verified" || value === "inference" || value === "gap" ? value : "open";
}

// --- the 14-kind dispatch: one family per kind ----------------------------------------------
/** The render families (the peer of `sdm.ATOM_RENDER_SLOTS`). record/doc, entity/person/place, and
 *  timeline/meeting share a family (and a card component) exactly as the live site already does; the
 *  rest are standalone. Every kind still maps to its own slot — some slots render via one family. */
export type AtomFamily =
  | "record"
  | "profile"
  | "event"
  | "exhibit"
  | "concept"
  | "lead"
  | "dataset"
  | "teardown"
  | "chapter"
  | "figure";

export const KIND_FAMILY: Record<CatalogKind, AtomFamily> = {
  record: "record",
  doc: "record",
  entity: "profile",
  person: "profile",
  place: "profile",
  timeline: "event",
  meeting: "event",
  exhibit: "exhibit",
  concept: "concept",
  lead: "lead",
  dataset: "dataset",
  teardown: "teardown",
  chapter: "chapter",
  figure: "figure",
};

/** A human "Kind · variant" label per kind, used when the hydrated payload doesn't carry its own. */
export const KIND_LABEL: Record<CatalogKind, string> = {
  record: "Record",
  doc: "Document",
  entity: "Entity",
  person: "Person",
  place: "Place",
  timeline: "Timeline · event",
  meeting: "Meeting",
  exhibit: "Exhibit · scan",
  concept: "Concept",
  lead: "Lead · open thread",
  dataset: "Dataset",
  teardown: "Teardown",
  chapter: "Chapter",
  figure: "Figure · deck.gl chart",
};

// --- per-kind render payloads (embedded scale) ----------------------------------------------
export interface FieldPair {
  label: string;
  value: string;
}

export interface RecordPayload {
  kind: string;
  title: string;
  recordId?: string;
  evidence: EvidenceKind;
  fields: FieldPair[];
  source?: { file: string; pages: string; collection: string };
}
export interface ProfilePayload {
  kindLabel: string;
  name: string;
  variants?: string[];
  descriptor?: string;
  evidence: EvidenceKind;
}
export interface EventPayload {
  year?: string;
  date: string;
  kind: string;
  title: string;
  summary?: string;
  evidence: EvidenceKind;
  connect?: { kind: string; label: string }[];
}
export interface SourcePayload {
  file: string;
  badge?: string;
  pages: string;
  collection: string;
  fields?: FieldPair[];
}
export interface ConceptPayload {
  term: string;
  descriptor: string;
  evidence: EvidenceKind;
}
export interface LeadPayload {
  kind: string;
  confidence: string;
  title: string;
  detail: string;
  action?: string;
  count?: string;
}
export interface DatasetPayload {
  label: string;
  value: string;
  unit?: string;
  evidence: EvidenceKind;
  basis?: string;
  sub?: string;
  bars: { label: string; value: number; highlight?: boolean }[];
}
export interface TeardownPayload {
  title: string;
  beats: number;
  headline: string;
}
export interface ChapterPayload {
  n: string;
  name: string;
  claim: string;
  status: string;
}
export interface FigurePayload {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  spark: number[];
}

/**
 * A resolved atom, hydrated with everything its render slot needs. The `handle`/`kind`/`title` are
 * always present (the thin snapshot); the kind-specific payload (`record`, `profile`, …) is present
 * when the live feed row was hydrated. `dangling` marks a handle that resolved once but no longer
 * does — the renderer shows the snapshot as a struck-through placeholder, never a broken card.
 */
export interface HydratedAtom {
  id?: string;
  handle: string;
  kind: CatalogKind;
  kindLabel: string;
  title: string;
  evidence: EvidenceKind;
  dangling?: boolean;
  record?: RecordPayload;
  profile?: ProfilePayload;
  event?: EventPayload;
  source?: SourcePayload;
  concept?: ConceptPayload;
  lead?: LeadPayload;
  dataset?: DatasetPayload;
  teardown?: TeardownPayload;
  chapter?: ChapterPayload;
  figure?: FigurePayload;
}

/** A catalog keyed by handle — what an island fetches (the `/stories-atoms.json` asset) and resolves
 *  each SDM `atom` handle against. Missing key ⇒ dangling. */
export type HydratedCatalog = Record<string, HydratedAtom>;

/**
 * Bridge a thin `CatalogAtom` pointer to a `HydratedAtom` with no kind payload — the minimal card
 * (kind label + title + evidence). Used for a dangling snapshot and as the floor when the live feed
 * row isn't hydrated. Never fabricates fields: a kind whose rich payload is absent renders compact.
 */
export function hydrateFromThin(atom: Pick<CatalogAtom, "handle" | "kind" | "title">): HydratedAtom {
  return {
    handle: atom.handle,
    kind: atom.kind,
    kindLabel: KIND_LABEL[atom.kind] ?? atom.kind,
    title: atom.title,
    evidence: "open",
  };
}

// --- the editor block model + block ⇄ DSL serialization -------------------------------------
/** The authoring canvas's block model — a flat, WYSIWYG-friendly shape. Inline runs are held as
 *  plain strings (markdown markers) at this tier; the DSL compiler parses them back into SDM inline
 *  spans, so the editor never has to model the inline tree. */
export type EditorBlock =
  | { type: "heading"; level: 2 | 3 | 4; text: string }
  | { type: "paragraph"; text: string }
  | { type: "blockquote"; text: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "callout"; variant: "note" | "info" | "warning"; text: string }
  | { type: "atom"; handle: string };

const DSL_HEADING_PREFIX: Record<2 | 3 | 4, string> = { 2: "## ", 3: "### ", 4: "#### " };

/**
 * Serialize the editor's block list to the **DSL source** the store persists and the server
 * recompiles (`storyCompile.dslFormat`). This is the write direction of compile-once-store-run-many:
 * the client edits blocks, but never ships SDM — it ships source the server re-validates.
 */
export function serializeBlocksToDsl(blocks: EditorBlock[]): string {
  const chunks: string[] = [];
  for (const b of blocks) {
    switch (b.type) {
      case "heading":
        chunks.push(`${DSL_HEADING_PREFIX[b.level]}${b.text}`);
        break;
      case "paragraph":
        chunks.push(b.text);
        break;
      case "blockquote":
        chunks.push(
          b.text
            .split("\n")
            .map((l) => `> ${l}`)
            .join("\n"),
        );
        break;
      case "list":
        chunks.push(b.items.map((it, i) => (b.ordered ? `${i + 1}. ${it}` : `- ${it}`)).join("\n"));
        break;
      case "callout":
        chunks.push(`:::callout{variant=${b.variant}}\n${b.text}\n:::`);
        break;
      case "atom":
        chunks.push(`:::atom{handle="${b.handle}"}\n:::`);
        break;
    }
  }
  return `${chunks.join("\n\n")}\n`;
}

/** Flatten an SDM inline run to editor text (markdown markers). Best-effort — the DSL compiler is the
 *  authority on parse; this is only to re-populate the editor when opening a stored Story. */
export function inlineToText(inline: SdmInline[]): string {
  return inline.map(inlineNodeToText).join("");
}

function inlineNodeToText(n: SdmInline): string {
  switch (n.type) {
    case "text":
      return n.value;
    case "code":
      return `\`${n.value}\``;
    case "strong":
      return `**${inlineToText(n.children)}**`;
    case "emphasis":
      return `*${inlineToText(n.children)}*`;
    case "link":
      return `[${inlineToText(n.children)}](${n.href})`;
  }
}

/**
 * Lower a stored `StoryDocument` back into the editor's block model, so a saved Story can be
 * re-opened for editing. Nested blocks (a callout's / blockquote's children) are flattened to their
 * text; atoms inside a callout surface as top-level cited atoms (the editor is a flat canvas).
 */
export function sdmToEditorBlocks(doc: StoryDocument): EditorBlock[] {
  const out: EditorBlock[] = [];
  const pushBlock = (block: SdmBlock): void => {
    switch (block.type) {
      case "heading":
        out.push({ type: "heading", level: block.level, text: inlineToText(block.children) });
        break;
      case "paragraph":
        out.push({ type: "paragraph", text: inlineToText(block.children) });
        break;
      case "blockquote":
        out.push({ type: "blockquote", text: blockText(block.children) });
        break;
      case "list":
        out.push({ type: "list", ordered: block.ordered, items: block.items.map((item) => blockText(item)) });
        break;
      case "callout":
        out.push({ type: "callout", variant: block.variant, text: blockText(block.children) });
        block.children.filter((c) => c.type === "atom").forEach(pushBlock);
        break;
      case "atom":
        out.push({ type: "atom", handle: block.handle });
        break;
    }
  };
  doc.blocks.forEach(pushBlock);
  return out;
}

/** The plain-text projection of a run of blocks (paragraph/heading text, joined) — for re-opening. */
function blockText(blocks: SdmBlock[]): string {
  return blocks
    .map((b) => {
      if (b.type === "paragraph" || b.type === "heading") return inlineToText(b.children);
      if (b.type === "blockquote" || b.type === "callout") return blockText(b.children);
      if (b.type === "list") return b.items.map(blockText).join("\n");
      return "";
    })
    .filter(Boolean)
    .join("\n");
}
