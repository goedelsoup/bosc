/**
 * The Story write-path pipeline (#1094) — compiles a Story source into the SDM (`./sdm`).
 *
 *   parse → assertNoCode → sanitize → resolveHandles → lowerToSDM
 *
 * Only `parse`/`assertNoCode` are **format-specific** (the `StoryFormat` seam); everything
 * downstream is shared, so the two front-ends are an apples-to-apples bake-off on one rig:
 *
 *  - **DSL** (`dslFormat`) — a markdown *subset* (remark-parse, no GFM/HTML) plus container
 *    directives (`:::atom{handle="…"}`, `:::callout{variant=…}`) via remark-directive. The handle
 *    is a quoted attribute (colon-safe — a bracketed `[handle]` label would mis-parse its inner
 *    `:`s as nested directives). No JSX, imports, or `{expressions}` — UGC-safe *by construction*.
 *  - **MDX-as-data** (`mdxDataFormat`) — parse-only MDX (remark-mdx) that hard-rejects
 *    `mdxFlowExpression`/`mdxTextExpression`/`mdxjsEsm`, so `<Atom/>`/`<Callout>` JSX lowers to the
 *    *same* SDM. It compares the DSL against MDX-restricted-to-data on identical output.
 *
 * Borrowing Nextra's compile-once-store-run-many: this is the **write-time** step (authenticated,
 * rate-limited); the public read path only renders the pre-validated SDM. The compiler is **pure**
 * (source + catalog → SDM or author-facing errors), like `buildStory`.
 */
import remarkDirective from "remark-directive";
import remarkMdx from "remark-mdx";
import remarkParse from "remark-parse";
import { unified } from "unified";
import { type Catalog, resolveHandle } from "./catalog";
import {
  SDM_CONTRACT_VERSION,
  SDM_CALLOUT_VARIANTS,
  type SdmBlock,
  type SdmCalloutVariant,
  type SdmInline,
  type StoryDocument,
} from "./sdm";

// --- author-facing errors -------------------------------------------------------------------
export type StoryErrorKind =
  | "parse" // the source didn't parse
  | "code" // an executable node survived to assertNoCode (expression/import/raw HTML)
  | "unsupported" // a block/inline outside the safe subset
  | "unknown-directive" // a directive / component that isn't `atom` or `callout`
  | "invalid-handle" // an `atom` with a missing or malformed handle
  | "unknown-handle" // a well-formed handle that doesn't resolve against the catalog
  | "unsafe-link"; // a link with a disallowed URL protocol

export interface StoryError {
  kind: StoryErrorKind;
  message: string;
  /** The offending node's start line, when the parser gave one (author feedback). */
  line?: number;
}

export type CompileResult = { ok: true; doc: StoryDocument } | { ok: false; errors: StoryError[] };

// --- the format seam (the only format-specific stages) --------------------------------------
export interface StoryFormat {
  id: "dsl" | "mdx-data";
  /** Source → mdast. May throw on a hard syntax error (caught by `compileStory`). */
  parse(source: string): MdNode;
  /** Reject executable/unsafe node types this format could carry (the `assertNoCode` gate). */
  assertNoCode(tree: MdNode): StoryError[];
}

// A structural mdast node — we narrow on `type` and read fields defensively, so we don't take a
// hard dependency on @types/mdast across the DSL / MDX / directive node zoo.
interface MdNode {
  type: string;
  children?: MdNode[];
  value?: string;
  [key: string]: unknown;
}

const line = (node: MdNode): number | undefined => {
  const pos = node.position as { start?: { line?: number } } | undefined;
  return pos?.start?.line;
};

// --- parse (format-specific) ----------------------------------------------------------------
function parseWith(plugin: typeof remarkDirective | typeof remarkMdx, source: string): MdNode {
  // `.parse()` applies the registered micromark/fromMarkdown extensions but runs no transforms —
  // exactly the compile-once discipline (no plugin can execute or rewrite the tree here).
  return unified().use(remarkParse).use(plugin).parse(source) as unknown as MdNode;
}

// --- assertNoCode (format-specific) ---------------------------------------------------------
/** Collect nodes whose `type` is in `banned`, anywhere in the tree. */
function findBanned(tree: MdNode, banned: ReadonlySet<string>, why: string): StoryError[] {
  const errors: StoryError[] = [];
  const walk = (node: MdNode): void => {
    if (banned.has(node.type)) {
      errors.push({ kind: "code", message: `${why}: <${node.type}>`, line: line(node) });
    }
    node.children?.forEach(walk);
  };
  walk(tree);
  return errors;
}

// Raw HTML is a `html` node in markdown; the DSL forbids it. (MDX has no `html` node — HTML-like
// syntax parses as JSX, gated below.)
const DSL_BANNED = new Set(["html"]);
// MDX-as-data keeps JSX elements (they lower to atom/callout) but hard-rejects anything executable.
const MDX_BANNED = new Set(["mdxFlowExpression", "mdxTextExpression", "mdxjsEsm", "html"]);

export const dslFormat: StoryFormat = {
  id: "dsl",
  parse: (source) => parseWith(remarkDirective, source),
  assertNoCode: (tree) => findBanned(tree, DSL_BANNED, "raw HTML is not allowed"),
};

export const mdxDataFormat: StoryFormat = {
  id: "mdx-data",
  parse: (source) => parseWith(remarkMdx, source),
  assertNoCode: (tree) => findBanned(tree, MDX_BANNED, "executable MDX is not allowed"),
};

// --- sanitize (shared) ----------------------------------------------------------------------
/** Only relative, http(s), and mailto links survive — a `javascript:`/`data:` URL is rejected. */
function isSafeUrl(url: string): boolean {
  const u = url.trim();
  if (u.startsWith("/") || u.startsWith("#") || u.startsWith("./") || u.startsWith("../")) return true;
  return /^(https?:|mailto:)/i.test(u);
}

// --- resolveHandles + lowerToSDM (shared) ---------------------------------------------------
/** Attribute lookup that spans both directive (`Record`) and MDX-JSX (`{name,value}[]`) shapes. */
function attr(node: MdNode, name: string): string | undefined {
  const a = node.attributes;
  if (Array.isArray(a)) {
    const hit = a.find(
      (x): x is { name?: unknown; value?: unknown } =>
        typeof x === "object" && x !== null && (x as { name?: unknown }).name === name,
    );
    return typeof hit?.value === "string" ? hit.value : undefined;
  }
  if (a && typeof a === "object") {
    const v = (a as Record<string, unknown>)[name];
    return typeof v === "string" ? v : undefined;
  }
  return undefined;
}

/** The label of a directive (`:::atom[<label>]`) — mdast-util-directive stores it as a leading
 *  child paragraph flagged `data.directiveLabel`. */
function directiveLabel(node: MdNode): string | undefined {
  const label = node.children?.find((c) => (c.data as { directiveLabel?: boolean })?.directiveLabel);
  return label ? textContent(label) : undefined;
}

/** Flatten a node's descendant text (`value`s), for labels/handles. */
function textContent(node: MdNode): string {
  if (typeof node.value === "string") return node.value;
  return (node.children ?? []).map(textContent).join("");
}

class Lowerer {
  readonly errors: StoryError[] = [];
  constructor(private readonly catalog: Catalog) {}

  private err(kind: StoryErrorKind, message: string, node: MdNode): null {
    this.errors.push({ kind, message, line: line(node) });
    return null;
  }

  inline(nodes: MdNode[]): SdmInline[] {
    const out: SdmInline[] = [];
    for (const node of nodes) {
      switch (node.type) {
        case "text":
          out.push({ type: "text", value: node.value ?? "" });
          break;
        case "strong":
          out.push({ type: "strong", children: this.inline(node.children ?? []) });
          break;
        case "emphasis":
          out.push({ type: "emphasis", children: this.inline(node.children ?? []) });
          break;
        case "inlineCode":
          out.push({ type: "code", value: node.value ?? "" });
          break;
        case "break":
          out.push({ type: "text", value: " " });
          break;
        case "link": {
          const url = typeof node.url === "string" ? node.url : "";
          if (!isSafeUrl(url)) {
            this.err("unsafe-link", `link URL is not allowed: ${url}`, node);
            break;
          }
          out.push({ type: "link", href: url, children: this.inline(node.children ?? []) });
          break;
        }
        default:
          this.err("unsupported", `inline "${node.type}" is not in the Story vocabulary`, node);
      }
    }
    return out;
  }

  /** An `atom` reference → a resolved atom block. The handle comes from the `handle=` attribute
   *  (DSL `:::atom{handle="…"}` / JSX `<Atom handle="…"/>`), which is colon-safe; the `[label]`
   *  form is a fallback only, since a bracketed handle's inner `:`s parse as nested directives. */
  private atom(node: MdNode): SdmBlock | null {
    const handle = attr(node, "handle") ?? directiveLabel(node);
    if (!handle) return this.err("invalid-handle", "atom is missing a handle", node);
    const resolved = resolveHandle(handle, this.catalog);
    if (!resolved.ok) {
      return this.err("unknown-handle", `handle does not resolve (${resolved.reason}): ${handle}`, node);
    }
    // The thin snapshot is captured from the live atom at write time (graceful degradation).
    return { type: "atom", handle, kind: resolved.atom.kind, title: resolved.atom.title };
  }

  private callout(node: MdNode): SdmBlock | null {
    const raw = attr(node, "variant") ?? attr(node, "class");
    const variant: SdmCalloutVariant = (SDM_CALLOUT_VARIANTS as readonly string[]).includes(raw ?? "")
      ? (raw as SdmCalloutVariant)
      : "note"; // unknown/absent variant degrades to `note`, never errors
    // A callout's directive label (if any) is framing, not content — drop it before lowering.
    const kids = (node.children ?? []).filter(
      (c) => !(c.data as { directiveLabel?: boolean })?.directiveLabel,
    );
    return { type: "callout", variant, children: this.blocks(kids) };
  }

  /** A container directive (`:::name`) or MDX JSX element (`<Name>`) → atom/callout, else error. */
  private named(node: MdNode, name: string): SdmBlock | null {
    const lower = name.toLowerCase();
    if (lower === "atom") return this.atom(node);
    if (lower === "callout") return this.callout(node);
    return this.err("unknown-directive", `unknown directive/component "${name}"`, node);
  }

  blocks(nodes: MdNode[]): SdmBlock[] {
    const out: SdmBlock[] = [];
    for (const node of nodes) {
      const block = this.block(node);
      if (block) out.push(block);
    }
    return out;
  }

  private block(node: MdNode): SdmBlock | null {
    switch (node.type) {
      case "paragraph":
        return { type: "paragraph", children: this.inline(node.children ?? []) };
      case "heading": {
        const depth = typeof node.depth === "number" ? node.depth : 2;
        const level = Math.min(Math.max(depth, 2), 4) as 2 | 3 | 4; // h1 is chrome; clamp into [2,4]
        return { type: "heading", level, children: this.inline(node.children ?? []) };
      }
      case "blockquote":
        return { type: "blockquote", children: this.blocks(node.children ?? []) };
      case "list": {
        const ordered = node.ordered === true;
        const items = (node.children ?? []).map((li) => this.blocks(li.children ?? []));
        return { type: "list", ordered, items };
      }
      case "thematicBreak":
        return null; // a horizontal rule carries no content — drop it
      case "containerDirective":
      case "leafDirective":
        return this.named(node, typeof node.name === "string" ? node.name : "");
      case "mdxJsxFlowElement":
        return this.named(node, typeof node.name === "string" ? node.name : "");
      default:
        return this.err("unsupported", `block "${node.type}" is not in the Story vocabulary`, node);
    }
  }
}

// --- the pipeline ---------------------------------------------------------------------------
/**
 * Compile a Story source to the SDM against a catalog (#1094). Pure: `(source, format, catalog) →
 * SDM | author-facing errors`. Resolution is a live pointer into the catalog — the SDM stores the
 * handle plus a thin `{kind,title}` snapshot, never a copy (chain of custody).
 */
export function compileStory(source: string, format: StoryFormat, catalog: Catalog): CompileResult {
  let tree: MdNode;
  try {
    tree = format.parse(source);
  } catch (e) {
    return { ok: false, errors: [{ kind: "parse", message: (e as Error).message }] };
  }

  const codeErrors = format.assertNoCode(tree);
  if (codeErrors.length > 0) return { ok: false, errors: codeErrors };

  const lowerer = new Lowerer(catalog);
  const blocks = lowerer.blocks(tree.children ?? []);
  if (lowerer.errors.length > 0) return { ok: false, errors: lowerer.errors };

  return { ok: true, doc: { version: SDM_CONTRACT_VERSION, blocks } };
}

/** Convenience: compile with the DSL front-end (the user-facing default). */
export function compileDsl(source: string, catalog: Catalog): CompileResult {
  return compileStory(source, dslFormat, catalog);
}
