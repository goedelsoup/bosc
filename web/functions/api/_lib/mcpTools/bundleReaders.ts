// Bundle reader MCP tool handlers (#914): get_timeline, get_entities,
// get_hypotheses, get_documents.
//
// Each handler fetches its feed from a root-absolute static JSON endpoint emitted at
// build time (src/pages/feeds/*.json.ts), so there is no database or model call —
// these are pure deterministic JSON readers. Tool descriptions embed the evidentiary
// contract: clients must cite sources and must not fabricate missing fields.
//
// Response-size governance (#1581): each reader fits its filtered feed to an explicit
// budget (max_results / max_tokens / max_tokens_per_result, or an `intent` preset) and
// returns the uniform `{ results, token_estimate, truncated, next_cursor }` envelope. The
// cursor pages the deterministic ordered feed; over-cap items shed their heaviest optional
// fields (prose detail, variant lists, assessment internals, entry lists) before counting.

import { fetchWithTimeout } from "../http";
import {
  type BudgetKnobs,
  decodeCursorOffset,
  dropKeysUntilUnderCap,
  estimateTokens,
  govern,
  governedContent,
  resolveKnobs,
} from "../mcpGovern";

type McpContent = { type: "text"; text: string };

function feedUrl(name: string, requestUrl: string): string {
  return new URL(`/feeds/${name}.json`, requestUrl).toString();
}

async function fetchFeed<T>(name: string, requestUrl: string): Promise<T> {
  const res = await fetchWithTimeout(feedUrl(name, requestUrl));
  if (!res.ok) throw new Error(`feed ${name} returned ${res.status}`);
  return res.json() as Promise<T>;
}

/** Resolve the governance knobs + cursor offset shared by every reader. */
function governanceOf(p: Record<string, unknown>): { knobs: BudgetKnobs; offset: number } {
  return { knobs: resolveKnobs(p), offset: decodeCursorOffset(p.cursor) };
}

/** Page `items` (the reader's ordered result list) through the budget and wrap the envelope. */
function paginate<T>(
  items: T[],
  knobs: BudgetKnobs,
  offset: number,
  shrink?: (item: T, capTokens: number) => T,
): McpContent[] {
  const window = items.slice(offset, offset + knobs.maxResults + 1);
  return governedContent(govern(window, { knobs, baseOffset: offset, shrink }));
}

// --- get_timeline ----------------------------------------------------------------

interface TimelineEntry {
  date: string;
  category: string;
  title: string;
  ref?: string;
  parties?: string[];
  detail?: string;
  source?: string;
  citation?: { verified?: boolean; confidence?: string; source_kind?: string; page?: number | null };
}

interface GetTimelineParams {
  since?: unknown;
  until?: unknown;
  category?: unknown;
}

export async function handleGetTimeline(params: unknown, requestUrl: string): Promise<McpContent[]> {
  const p = (params ?? {}) as GetTimelineParams;
  const since = typeof p.since === "string" ? p.since : null;
  const until = typeof p.until === "string" ? p.until : null;
  const category = typeof p.category === "string" && p.category ? p.category : null;
  const { knobs, offset } = governanceOf(p as Record<string, unknown>);

  let entries = await fetchFeed<TimelineEntry[]>("timeline", requestUrl);

  if (since) entries = entries.filter((e) => e.date >= since);
  if (until) entries = entries.filter((e) => e.date <= until);
  if (category) entries = entries.filter((e) => e.category === category);

  // Return ascending (oldest-first); clients may reverse as needed.
  entries = [...entries].sort((a, b) => a.date.localeCompare(b.date));

  return paginate(entries, knobs, offset, (e, cap) => dropKeysUntilUnderCap(e, ["detail", "parties"], cap));
}

// --- get_entities ----------------------------------------------------------------

interface EntityNode {
  key: string;
  display: string;
  kind: string;
  classification?: string | null;
  variants?: string[];
  roles?: Record<string, number>;
  parcels?: string[];
  addresses?: string[];
  sources?: string[];
  signals?: string[];
}

interface GetEntitiesParams {
  type?: unknown;
}

export async function handleGetEntities(params: unknown, requestUrl: string): Promise<McpContent[]> {
  const p = (params ?? {}) as GetEntitiesParams;
  const typeFilter = typeof p.type === "string" && p.type ? p.type : null;
  const { knobs, offset } = governanceOf(p as Record<string, unknown>);

  let entities = await fetchFeed<EntityNode[]>("entities", requestUrl);

  if (typeFilter) {
    entities = entities.filter((e) => e.kind === typeFilter);
  }

  return paginate(entities, knobs, offset, (e, cap) =>
    dropKeysUntilUnderCap(e, ["variants", "addresses", "signals", "parcels", "roles"], cap),
  );
}

// --- get_hypotheses --------------------------------------------------------------

interface HypothesisItem {
  id: string;
  number: string;
  name: string;
  claim: string;
  thesis: string;
  status: string;
  signals: string[];
  groups: string[];
}

interface HypothesisAssessmentItem {
  site: string;
  hypothesis: string;
  signal: string;
  tag: string;
  sub_thesis?: string | null;
  group?: string;
  fields?: Record<string, unknown>;
  citations?: unknown[];
}

interface HypothesesPayload {
  hypotheses: HypothesisItem[];
  assessments: HypothesisAssessmentItem[];
}

interface JoinedHypothesis extends HypothesisItem {
  assessments: HypothesisAssessmentItem[];
}

interface GetHypothesesParams {
  site?: unknown;
}

/** Shed a joined hypothesis's heaviest payload: assessment internals first, then cap the list. */
function shrinkHypothesis(h: JoinedHypothesis, capTokens: number): JoinedHypothesis {
  if (estimateTokens(h) <= capTokens) return h;
  // Strip each assessment to its identity + tag (drop fields/citations/sub_thesis).
  const lean: JoinedHypothesis = {
    ...h,
    assessments: h.assessments.map((a) => ({
      site: a.site,
      hypothesis: a.hypothesis,
      signal: a.signal,
      tag: a.tag,
      group: a.group,
    })),
  };
  if (estimateTokens(lean) <= capTokens) return lean;
  // Still over: keep as many assessments as fit (count preserved via the array length).
  const kept: HypothesisAssessmentItem[] = [];
  for (const a of lean.assessments) {
    const trial = { ...lean, assessments: [...kept, a] };
    if (kept.length > 0 && estimateTokens(trial) > capTokens) break;
    kept.push(a);
  }
  return { ...lean, assessments: kept };
}

export async function handleGetHypotheses(params: unknown, requestUrl: string): Promise<McpContent[]> {
  const p = (params ?? {}) as GetHypothesesParams;
  const siteFilter = typeof p.site === "string" && p.site ? p.site : null;
  const { knobs, offset } = governanceOf(p as Record<string, unknown>);

  const payload = await fetchFeed<HypothesesPayload>("hypotheses", requestUrl);
  const { hypotheses, assessments } = payload;

  let filteredAssessments = assessments;
  if (siteFilter) {
    filteredAssessments = assessments.filter((a) => a.site === siteFilter);
  }

  const joined: JoinedHypothesis[] = hypotheses.map((h) => ({
    ...h,
    assessments: filteredAssessments.filter((a) => a.hypothesis === h.id),
  }));

  return paginate(joined, knobs, offset, shrinkHypothesis);
}

// --- get_documents ---------------------------------------------------------------

interface DocumentEntry {
  rel: string;
  name: string;
  suffix: string;
  media_type: string;
  published: boolean;
  available: boolean;
}

interface DocumentCollectionItem {
  slug: string;
  title: string;
  description: string;
  entries: DocumentEntry[];
}

interface ReducedEntry {
  rel: string;
  name: string;
  media_type: string;
  published: boolean;
  available: boolean;
}

interface ReducedCollection {
  slug: string;
  title: string;
  description: string;
  entry_count: number;
  entries: ReducedEntry[];
}

interface GetDocumentsParams {
  collection?: unknown;
}

/** Cap a collection's entry list until it fits; `entry_count` stays the true total. */
function shrinkCollection(c: ReducedCollection, capTokens: number): ReducedCollection {
  if (estimateTokens(c) <= capTokens) return c;
  const kept: ReducedEntry[] = [];
  for (const e of c.entries) {
    const trial = { ...c, entries: [...kept, e] };
    if (kept.length > 0 && estimateTokens(trial) > capTokens) break;
    kept.push(e);
  }
  return { ...c, entries: kept };
}

export async function handleGetDocuments(params: unknown, requestUrl: string): Promise<McpContent[]> {
  const p = (params ?? {}) as GetDocumentsParams;
  const collectionFilter = typeof p.collection === "string" && p.collection ? p.collection : null;
  const { knobs, offset } = governanceOf(p as Record<string, unknown>);

  let collections = await fetchFeed<DocumentCollectionItem[]>("documents", requestUrl);

  if (collectionFilter) {
    collections = collections.filter((c) => c.slug === collectionFilter);
  }

  // Strip full entry details for brevity; return metadata only.
  const reduced: ReducedCollection[] = collections.map((c) => ({
    slug: c.slug,
    title: c.title,
    description: c.description,
    entry_count: c.entries.length,
    entries: c.entries.map((e) => ({
      rel: e.rel,
      name: e.name,
      media_type: e.media_type,
      published: e.published,
      available: e.available,
    })),
  }));

  return paginate(reduced, knobs, offset, shrinkCollection);
}
