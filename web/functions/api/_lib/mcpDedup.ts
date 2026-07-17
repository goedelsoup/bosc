// Shared duplicate-cluster collapse for retrieval (#1590, epic #1579 Phase 3).
//
// Search returns a filing's final permit, its draft public notice, and its fact sheet as separate
// hits with no signal they are one filing's versions. The `documents` feed now carries version /
// duplicate-cluster metadata (projected from the curated custody manifest by
// watermark.site.docversions); this kernel reads that map (docVersionsLoad) and collapses a cluster
// to its canonical (authoritative) member — WITHOUT losing the distinct evidence a superseded
// version carries (e.g. a draft's CBI-unredacted figure the final redacts).
//
// The collapse runs over the FULL ranked pool before the cursor window is sliced, so a cluster's
// canonical member is chosen from every hit (not just the current page) and pagination stays
// stable. It is rel-based (not item-based) so it serves both search_corpus (one hit per document)
// and search_passages (many page hits per document): the unit of collapse is the document `rel`.

import { tokenize } from "./retrieval";
import type { VersionInfo } from "./docVersionsLoad";

export type Deduplicate = "none" | "canonical";
export type VersionPolicy = "all" | "latest_only" | "latest_with_relevant_older_evidence";

export const DEDUPLICATE_MODES: readonly Deduplicate[] = ["none", "canonical"];
export const VERSION_POLICIES: readonly VersionPolicy[] = [
  "all",
  "latest_only",
  "latest_with_relevant_older_evidence",
];

export const DEFAULT_DEDUPLICATE: Deduplicate = "canonical";
export const DEFAULT_VERSION_POLICY: VersionPolicy = "latest_with_relevant_older_evidence";

/** Parse the `deduplicate` arg; unknown/absent → the default. */
export function parseDeduplicate(v: unknown): Deduplicate {
  return typeof v === "string" && (DEDUPLICATE_MODES as readonly string[]).includes(v)
    ? (v as Deduplicate)
    : DEFAULT_DEDUPLICATE;
}

/** Parse the `version_policy` arg; unknown/absent → the default. */
export function parseVersionPolicy(v: unknown): VersionPolicy {
  return typeof v === "string" && (VERSION_POLICIES as readonly string[]).includes(v)
    ? (v as VersionPolicy)
    : DEFAULT_VERSION_POLICY;
}

/** How to read the join key + comparison text off one pool item. */
export interface DedupAccess<T> {
  /** The `data/documents` rel this item resolves to; null/undefined ⇒ never collapsed. */
  relOf: (item: T) => string | null | undefined;
  /** The text used for the relevant-older-evidence term comparison. */
  textOf: (item: T) => string;
}

export interface DedupOptions<T> {
  deduplicate: Deduplicate;
  versionPolicy: VersionPolicy;
  query: string;
  versions: Map<string, VersionInfo>;
  access: DedupAccess<T>;
  /**
   * Restrict collapse to members whose `version` is in this set. `null` (search_corpus) collapses
   * every non-canonical member. search_passages passes `{"duplicate"}` so only byte-identical copies
   * collapse — draft/final page variants stay distinct (their pages legitimately differ).
   */
  collapsibleVersions?: ReadonlySet<string> | null;
}

interface Resolved {
  rel: string;
  info: VersionInfo;
}

/**
 * Collapse duplicate-cluster members in a ranked pool, preserving rank order.
 *
 * Per cluster, the representative rel is the canonical member if any pool item resolves to it, else
 * the best-ranked present member (so a cluster is never zeroed out). An item is kept when it belongs
 * to the representative rel, isn't collapse-eligible, or — under `latest_with_relevant_older_evidence`
 * — carries a query term the representative's text lacks. `deduplicate:"none"` and
 * `version_policy:"all"` both short-circuit to the pool unchanged.
 */
export function dedupeByCluster<T>(pool: T[], opts: DedupOptions<T>): T[] {
  const { deduplicate, versionPolicy, query, versions, access, collapsibleVersions = null } = opts;
  if (deduplicate === "none" || versionPolicy === "all" || versions.size === 0) return pool;

  const resolve = (item: T): Resolved | null => {
    const rel = access.relOf(item);
    if (!rel) return null;
    const info = versions.get(rel);
    return info ? { rel, info } : null;
  };

  // Pass 1 — per cluster, pick the representative rel (canonical if present, else best-ranked member).
  const canonicalRelByCluster = new Map<string, string>();
  const firstMemberRelByCluster = new Map<string, string>();
  const canonicalPresent = new Set<string>();
  for (const item of pool) {
    const r = resolve(item);
    if (!r) continue;
    canonicalRelByCluster.set(r.info.cluster, r.info.canonical);
    if (!firstMemberRelByCluster.has(r.info.cluster)) {
      firstMemberRelByCluster.set(r.info.cluster, r.rel);
    }
    if (r.info.isCanonical) canonicalPresent.add(r.info.cluster);
  }
  const representativeRel = (cluster: string): string =>
    canonicalPresent.has(cluster)
      ? (canonicalRelByCluster.get(cluster) as string)
      : (firstMemberRelByCluster.get(cluster) as string);

  // Pass 2 — representative text per cluster (concat of every item on the representative rel), so the
  // evidence comparison sees the whole canonical version even when it's spread over several hits.
  const repTokensByCluster = new Map<string, Set<string>>();
  if (versionPolicy === "latest_with_relevant_older_evidence") {
    const repTextByCluster = new Map<string, string[]>();
    for (const item of pool) {
      const r = resolve(item);
      if (!r || r.rel !== representativeRel(r.info.cluster)) continue;
      const bucket = repTextByCluster.get(r.info.cluster) ?? [];
      bucket.push(access.textOf(item));
      repTextByCluster.set(r.info.cluster, bucket);
    }
    for (const [cluster, parts] of repTextByCluster) {
      repTokensByCluster.set(cluster, new Set(tokenize(parts.join(" "))));
    }
  }
  const queryTerms = tokenize(query);

  const isEligible = (info: VersionInfo): boolean =>
    collapsibleVersions === null || (info.version !== null && collapsibleVersions.has(info.version));

  // Pass 3 — keep/drop in rank order.
  const out: T[] = [];
  for (const item of pool) {
    const r = resolve(item);
    if (!r) {
      out.push(item); // no cluster → untouched
      continue;
    }
    const repRel = representativeRel(r.info.cluster);
    if (r.rel === repRel || !isEligible(r.info)) {
      out.push(item); // the representative, or a non-collapsible variant
      continue;
    }
    if (versionPolicy === "latest_only") continue; // drop every non-representative member
    // latest_with_relevant_older_evidence: retain only when this member adds a query-relevant term
    // the representative lacks. No representative text to compare against ⇒ retain (never drop
    // unprovable-redundant evidence).
    const repTokens = repTokensByCluster.get(r.info.cluster);
    if (!repTokens || repTokens.size === 0) {
      out.push(item);
      continue;
    }
    const candTokens = new Set(tokenize(access.textOf(item)));
    const addsEvidence = queryTerms.some((t) => candTokens.has(t) && !repTokens.has(t));
    if (addsEvidence) out.push(item);
  }
  return out;
}
