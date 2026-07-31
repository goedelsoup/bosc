// Structured citations on MCP results (#1584, epic #1579 Phase 1).
//
// Every result-bearing tool returns provenance as ONE uniform `citation` object rather than a
// scatter of flat fields and prose. The point is that a caller can cite a fact **without pulling
// the document it came from**: the discovery card already carries the addressable document, the
// page, the evidence class and a paste-ready human string, so the follow-up `get_document` /
// `search_passages` call is a choice, not a prerequisite for an honest citation.
//
// Three rules the shape encodes, all downstream of the root CLAUDE.md evidence discipline:
//
//   1. **Nothing is invented.** A field is present only where the source genuinely carries it —
//      a page-less connector value yields no `page`, not a guessed one. Absent fields are
//      OMITTED rather than emitted as null, which also keeps the object cheap enough to ride on
//      every compact discovery card (the whole point of #1580).
//   2. **`quote` means verbatim.** It is populated only from real source text (a `search_passages`
//      page excerpt). A `search_corpus` snippet is a window over the record's FLATTENED FIELDS
//      ("key value · key value"), not source prose, and calling that a quote would manufacture a
//      verbatim-ness the bundle does not have. It is also BOUNDED (`QUOTE_MAX_CHARS`): the object
//      must stand alone once a client lifts it out of the response envelope, but a whole page of
//      text alongside the hit's own `text` field would double the response of the one tool that
//      can fill it — so the citation carries a lead excerpt and the hit carries the full page.
//   3. **Free-text provenance survives.** A projected fact usually has no path and no page — a
//      `ProvenancedValue` carries one free-text citation (#1587) — so that text rides in `note`
//      and becomes the label. Dropping it in the name of "structured" would lose the only
//      provenance those rows have.

import { formatCitedPages } from "@watermark/core/feeds";

/** The evidence-discipline tag a citation renders as, mirroring `evidenceKind` in
 * `@watermark/core/feeds`: `source_kind` document/connector are `[verified]`, the rest asserted. */
type EvidenceTag = "verified" | "inference";

/** The uniform provenance object attached to every result that has provenance to report. */
export interface McpCitation {
  /** The addressable source document — a `data/documents` rel. Pass it to `get_document` or
   * `search_passages.document_ids`. Absent when the item isn't grounded in a catalogued file. */
  document_id?: string;
  /** The citable artifact the claim was read from: a repo-relative `data/` path (usually the
   * reviewed extraction), a dataset label, or an instrument number. */
  source?: string;
  /** Provenance class — document | connector | reference | assumption | derived. */
  source_kind?: string;
  /** 1-based FIRST page within the source. Absent where the source carries no page. */
  page?: number;
  /** Every 1-based page the claim was read from, when the read spanned more than one. A list,
   * not a range: extraction reads are often non-contiguous. */
  pages?: number[];
  /** Sub-page heading within the source, where one is recorded. */
  section?: string;
  /** Absolute URL at which the cited source can be inspected. */
  source_url?: string;
  /** VERBATIM source text, capped at `QUOTE_MAX_CHARS` and ellipsized when trimmed — set only
   * where the result carries real source text (a page excerpt), never a flattened-field snippet. */
  quote?: string;
  /** Free-text provenance the source records instead of (or beside) a path — a projected fact's
   * `ProvenancedValue` citation, or a record's citation note. */
  note?: string;
  /** Evidence confidence band recorded on the source (high | medium | low). */
  confidence?: string;
  /** True when grounded in a record or a live gauge — `[verified]` in prose. */
  verified: boolean;
  /** The evidence tag this citation renders as. */
  evidence: EvidenceTag;
  /** One-line human-readable rendering — the string to paste into prose. */
  label: string;
}

/** The normalized bag each tool maps its own row into. Every field is optional; whatever is
 * genuinely known gets set, and the builder drops the rest. */
export interface CitationInput {
  document_id?: string | null;
  source?: string | null;
  source_kind?: string | null;
  page?: number | null;
  pages?: number[] | null;
  section?: string | null;
  /** Root-absolute or absolute; resolved against `baseUrl` when one is supplied. */
  source_url?: string | null;
  quote?: string | null;
  note?: string | null;
  confidence?: string | null;
  verified?: boolean | null;
}

/** `source_kind`s that ground a claim in a record or a live gauge — mirrors
 * `bosc.provenance.source_is_verified`, the single vocabulary the bundle's `verified` flag uses. */
const VERIFIED_KINDS: ReadonlySet<string> = new Set(["document", "connector"]);

/** Cap on `quote`. A citation must stand alone once lifted out of the envelope, but the excerpt
 * is supporting evidence for the cite, not the payload — the full text stays on the result. */
export const QUOTE_MAX_CHARS = 320;

const str = (v: string | null | undefined): string | undefined => {
  const s = typeof v === "string" ? v.trim() : "";
  return s === "" ? undefined : s;
};

const posInt = (v: number | null | undefined): number | undefined =>
  typeof v === "number" && Number.isInteger(v) && v > 0 ? v : undefined;

/** Ascending, deduped, positive integers — or undefined when the span says nothing `page` doesn't. */
function pageSpan(pages: number[] | null | undefined): number[] | undefined {
  if (!Array.isArray(pages)) return undefined;
  const clean = [...new Set(pages.filter((p) => posInt(p) !== undefined))].sort((a, b) => a - b);
  return clean.length > 1 ? clean : undefined;
}

/** Resolve a root-absolute site path to an absolute URL, so a client can follow the cite. An
 * already-absolute URL passes through; an unresolvable value is dropped rather than guessed. */
function absoluteUrl(url: string | undefined, baseUrl: string | undefined): string | undefined {
  if (url === undefined) return undefined;
  if (baseUrl === undefined) return url;
  try {
    return new URL(url, baseUrl).toString();
  } catch {
    return undefined;
  }
}

/**
 * Build the uniform `citation` object from whatever provenance a result actually has.
 *
 * `baseUrl` (the handler's `requestUrl`) resolves a root-absolute `source_url` to an absolute one.
 * `verified` is taken verbatim when the row records it and otherwise derived from `source_kind`,
 * so the flag never has to be re-computed by a consumer — and never disagrees with the bundle.
 */
export function buildCitation(input: CitationInput, baseUrl?: string): McpCitation {
  const source = str(input.source);
  const documentId = str(input.document_id);
  const sourceKind = str(input.source_kind);
  const page = posInt(input.page);
  const pages = pageSpan(input.pages);
  const section = str(input.section);
  const note = str(input.note);
  const verified =
    typeof input.verified === "boolean"
      ? input.verified
      : sourceKind !== undefined && VERIFIED_KINDS.has(sourceKind);

  const cite: McpCitation = { verified, evidence: verified ? "verified" : "inference", label: "" };
  if (documentId !== undefined) cite.document_id = documentId;
  if (source !== undefined) cite.source = source;
  if (sourceKind !== undefined) cite.source_kind = sourceKind;
  if (page !== undefined) cite.page = page;
  if (pages !== undefined) cite.pages = pages;
  if (section !== undefined) cite.section = section;
  const url = absoluteUrl(str(input.source_url), baseUrl);
  if (url !== undefined) cite.source_url = url;
  const quote = str(input.quote);
  if (quote !== undefined) {
    cite.quote = quote.length > QUOTE_MAX_CHARS ? `${quote.slice(0, QUOTE_MAX_CHARS).trimEnd()}…` : quote;
  }
  if (note !== undefined) cite.note = note;
  const confidence = str(input.confidence);
  if (confidence !== undefined) cite.confidence = confidence;

  cite.label = renderLabel(cite, note);
  return cite;
}

/**
 * The paste-ready one-liner: `<artifact> <pages> (<section>) [<evidence>]`.
 *
 * Leads with the citable artifact — `source` when there is one, else the document id. When there
 * is neither (a projected fact, whose provenance is one free-text string), the free text IS the
 * citation and stands in as the lead rather than being dropped; a row with no provenance at all
 * says so, because a blank label would read as an uncited claim rather than an unciteable one.
 */
function renderLabel(cite: McpCitation, note: string | undefined): string {
  const lead = cite.source ?? cite.document_id ?? note ?? "uncited";
  const parts = [lead];
  // The one page-span renderer, shared with the site's own Provenance component.
  const pages = formatCitedPages(cite.page, cite.pages);
  if (pages !== null) parts.push(pages);
  if (cite.section !== undefined) parts.push(`(${cite.section})`);
  return `${parts.join(" ")} [${cite.evidence}]`;
}
