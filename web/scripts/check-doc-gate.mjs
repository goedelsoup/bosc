// The publish gate the build actually shipped must reach every site (#2149).
//
// `/published-documents.json` is the ONLY thing standing between a reader and a source byte: the
// `/api/doc` Function admits a rel if that asset names it and 404s it otherwise. The asset is
// network-global; the `documents` feed it is built from is per-site. So the asset is one place where
// "read the feed" silently means "read Lima's feed", and that is what shipped: the deployed gate
// carried 35 rels while the build offered 392, and 252 of them were unreachable at any deploy
// freshness with the bytes sitting in R2.
//
// ⚠️ This reads `dist/`, for the same reason `check-site-scope.mjs` does. `docGate.test.ts` already
// pins the union against the committed fixtures, and it would not have caught the failure this
// guards: the asset is assembled from whichever bundles the BUILD resolved, and a site whose export
// omitted its documents feed drops out of the union in silence — `hasFeed` is false, the loop
// continues, and the gate emerges smaller with nothing to show for it. Only the emitted asset knows
// what the build actually put in the reader's way.
//
// The assertion is deliberately tolerant of drift: every exported site whose committed bundle
// publishes any document must contribute AT LEAST ONE rel. A committed bundle that lags the corpus
// still satisfies that; a gate that fell back to one site cannot.
//
// Run after `astro build`:  node scripts/check-doc-gate.mjs  (pnpm run check:doc-gate)

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const DIST = process.env.CHECK_DOC_GATE_DIST || "dist";
const BUNDLES = process.env.CHECK_DOC_GATE_BUNDLES || "sites";
const GATE = join(DIST, "published-documents.json");
const REGISTRY = "packages/core/src/sites-registry.json";

const fail = (msg) => {
  console.error(`check-doc-gate: ${msg}`);
  process.exit(1);
};

if (!existsSync(GATE)) {
  fail(`no ${GATE} — run \`pnpm run build\` first.`);
}

const gate = JSON.parse(readFileSync(GATE, "utf-8"));
if (!Array.isArray(gate.rels)) {
  fail(`${GATE} carries no \`rels\` array — the Function fails closed on this (503).`);
}
const admitted = new Set(gate.rels);

// The exported sites, from the same registry `exportedSiteSlugs()` reads. Plain JSON on purpose:
// this script runs under bare node, with no TS loader.
const registry = JSON.parse(readFileSync(REGISTRY, "utf-8"));
const exported = registry.sites.filter((s) => s.selectable).map((s) => s.slug);

const publishedFor = (slug) => {
  const feed = join(BUNDLES, slug, "feeds", "documents.json");
  if (!existsSync(feed)) return null; // no committed bundle — nothing to expect from it
  const collections = JSON.parse(readFileSync(feed, "utf-8"));
  return collections.flatMap((c) => c.entries.filter((e) => e.published).map((e) => e.rel));
};

const missing = [];
const rows = [];
for (const slug of exported) {
  const own = publishedFor(slug);
  if (own === null) {
    rows.push(`${slug}: no committed bundle`);
    continue;
  }
  const reached = own.filter((rel) => admitted.has(rel)).length;
  rows.push(`${slug}: ${reached}/${own.length} admitted`);
  if (own.length > 0 && reached === 0) missing.push(slug);
}

console.log(`check-doc-gate: gate admits ${admitted.size} rel(s) · ${rows.join(" · ")}`);

if (missing.length > 0) {
  fail(
    `the shipped gate names NO published document from ${missing.join(", ")} — ` +
      "every one of that site's downloads will 404 before R2 is asked (#2149).",
  );
}
console.log("check-doc-gate: OK — every exported site reaches the publish gate.");
