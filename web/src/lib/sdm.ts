/**
 * The Story Document Model (SDM) — the shared render/output contract (#1092) both Story owners
 * resolve into. It is a normalized block tree that is **data, not code**: a closed vocabulary of
 * prose blocks (a markdown subset) plus `atom` blocks that reference catalog handles. That is the
 * safety line versus executable Remote-MDX — an untrusted user Story can never introduce a new
 * component or expression, only arrange the preordained ones.
 *
 * Both paths lower into the SDM: the editorial path (trusted, build-time MDX) and the user path
 * (untrusted, runtime DSL) share everything downstream of the parse. Borrowing Nextra's
 * *compile-once-store-run-many*: a Story is parsed, sanitized, handle-resolved, and lowered to SDM
 * at **write time** (authenticated, rate-limited) under `SDM_CONTRACT_VERSION`; the public read
 * path only renders pre-validated SDM. #1094 builds the write path, #1097 the renderer, #1095 the
 * store — all against these types. Resolution stays a **live pointer** into the catalog (chain of
 * custody): the SDM stores a handle, never a copy of the cited atom.
 */
import {
  type Catalog,
  type CatalogAtom,
  CATALOG_KINDS,
  type CatalogKind,
  type ResolveFailure,
  resolveHandle,
} from "./catalog";

/**
 * The SDM vocabulary revision. A stored Story records the version it was lowered under; a bump
 * means stored docs may need revalidation (the write-once/validate-once discipline, #1094/#1099).
 */
export const SDM_CONTRACT_VERSION = "1.0.0";

// --- inline: the markdown-subset span vocabulary (no raw HTML, no expressions) --------------
export type SdmInline =
  | { type: "text"; value: string }
  | { type: "strong"; children: SdmInline[] }
  | { type: "emphasis"; children: SdmInline[] }
  | { type: "code"; value: string }
  | { type: "link"; href: string; children: SdmInline[] };

export const SDM_INLINE_TYPES = ["text", "strong", "emphasis", "code", "link"] as const;

// --- block: the closed block vocabulary -----------------------------------------------------
/** Reader-prose heading levels. `h1` is the Story title (chrome), never body content, so it is not
 *  a block type — a user can't forge a page-level heading. */
export type SdmHeadingLevel = 2 | 3 | 4;

export type SdmBlock =
  | { type: "heading"; level: SdmHeadingLevel; children: SdmInline[] }
  | { type: "paragraph"; children: SdmInline[] }
  | { type: "blockquote"; children: SdmBlock[] }
  | { type: "list"; ordered: boolean; items: SdmBlock[][] }
  /**
   * A cited catalog atom (`:::atom[<kind>:<site>:<localId>]`). The **only** way a Story pulls in
   * platform content — a live pointer, resolved against the catalog at render time. Reader prose
   * (the blocks above) is rendered visually distinct from these cited atoms (#1090).
   */
  | { type: "atom"; handle: string };

export const SDM_BLOCK_TYPES = ["heading", "paragraph", "blockquote", "list", "atom"] as const;

/** A lowered, persistable Story body — the write path's output and the read path's input. */
export interface StoryDocument {
  /** The `SDM_CONTRACT_VERSION` this document was lowered under (compile-once-store-run-many). */
  version: string;
  blocks: SdmBlock[];
}

/**
 * The **preordained component vocabulary** (#1092): exactly one render slot per catalog kind, so
 * the runtime renderer (#1097) has a closed, exhaustive dispatch table and a user Story can grab
 * any kind but never introduce a new render component. Slot ids are stable (`atom:<kind>`); the
 * actual components land with #1097.
 */
export type AtomRenderSlot = `atom:${CatalogKind}`;
export const ATOM_RENDER_SLOTS: Record<CatalogKind, AtomRenderSlot> = Object.fromEntries(
  CATALOG_KINDS.map((kind) => [kind, `atom:${kind}` as AtomRenderSlot]),
) as Record<CatalogKind, AtomRenderSlot>;

// --- structural validation: the "data, not code" guard --------------------------------------
const INLINE_SET: ReadonlySet<string> = new Set(SDM_INLINE_TYPES);
const BLOCK_SET: ReadonlySet<string> = new Set(SDM_BLOCK_TYPES);

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function isValidInline(node: unknown): node is SdmInline {
  if (!isRecord(node) || typeof node.type !== "string" || !INLINE_SET.has(node.type)) return false;
  switch (node.type) {
    case "text":
    case "code":
      return typeof node.value === "string";
    case "link":
      return typeof node.href === "string" && isInlineArray(node.children);
    default: // strong | emphasis
      return isInlineArray(node.children);
  }
}

function isInlineArray(v: unknown): v is SdmInline[] {
  return Array.isArray(v) && v.every(isValidInline);
}

function isValidBlock(node: unknown): node is SdmBlock {
  if (!isRecord(node) || typeof node.type !== "string" || !BLOCK_SET.has(node.type)) return false;
  switch (node.type) {
    case "heading":
      return (node.level === 2 || node.level === 3 || node.level === 4) && isInlineArray(node.children);
    case "paragraph":
      return isInlineArray(node.children);
    case "blockquote":
      return isBlockArray(node.children);
    case "list":
      return typeof node.ordered === "boolean" && Array.isArray(node.items) && node.items.every(isBlockArray);
    default: // atom
      return typeof node.handle === "string";
  }
}

function isBlockArray(v: unknown): v is SdmBlock[] {
  return Array.isArray(v) && v.every(isValidBlock);
}

/**
 * Structurally validate an untrusted value as a `StoryDocument` — the guard that a parsed/persisted
 * body is **data, not code**: every node is in the closed vocabulary, so there is nowhere for a
 * script/expression/raw-HTML node to hide. Returns the typed document or `null`. Note this does not
 * check that atom handles *resolve* (that is `resolveSdmAtoms`) — only that the shape is legal.
 */
export function validateStoryDocument(value: unknown): StoryDocument | null {
  if (!isRecord(value) || typeof value.version !== "string") return null;
  if (!isBlockArray(value.blocks)) return null;
  return { version: value.version, blocks: value.blocks };
}

// --- the resolver seam: SDM × catalog -------------------------------------------------------
/** The `depth`-first list of every catalog handle an SDM references, in document order (with
 *  duplicates). The write-path validation (#1094) and handle-drift revalidation (#1099) read it. */
export function sdmHandles(doc: StoryDocument): string[] {
  const handles: string[] = [];
  const walkBlock = (block: SdmBlock): void => {
    switch (block.type) {
      case "atom":
        handles.push(block.handle);
        break;
      case "blockquote":
        block.children.forEach(walkBlock);
        break;
      case "list":
        for (const item of block.items) item.forEach(walkBlock);
        break;
      // heading | paragraph carry only inline spans — no atoms.
    }
  };
  doc.blocks.forEach(walkBlock);
  return handles;
}

export type ResolvedAtom =
  | { ok: true; atom: CatalogAtom }
  | { ok: false; handle: string; reason: ResolveFailure };

/**
 * Resolve every atom handle an SDM references against a catalog — the seam the runtime renderer
 * (#1097) and the write-path validator (#1094) share. Live pointer resolution (chain of custody):
 * returns the catalog atom, or the `resolveHandle` failure reason, keyed by handle (deduplicated).
 */
export function resolveSdmAtoms(doc: StoryDocument, catalog: Catalog): Map<string, ResolvedAtom> {
  const out = new Map<string, ResolvedAtom>();
  for (const handle of sdmHandles(doc)) {
    if (out.has(handle)) continue;
    const r = resolveHandle(handle, catalog);
    out.set(handle, r.ok ? { ok: true, atom: r.atom } : { ok: false, handle, reason: r.reason });
  }
  return out;
}

/** Whether every atom the SDM cites resolves live — the write-time gate (#1094) before persist, and
 *  the health signal a stored Story is re-checked against on catalog change (#1099). */
export function sdmIsResolvable(doc: StoryDocument, catalog: Catalog): boolean {
  for (const resolved of resolveSdmAtoms(doc, catalog).values()) {
    if (!resolved.ok) return false;
  }
  return true;
}
