// Build-time internal-link validation (#178). `astro check` typechecks but never
// crawls output links, so an emitted href that 404s — e.g. a deep-link into a
// bundle-gated route that isn't generated in the CI sites build — passes
// CI silently. This walks the built `dist/`, collects every emitted internal
// (root-relative) href/src, and asserts each resolves to a generated page or a
// static asset. Exits non-zero on any unresolved link.
//
// Run after `astro build`:  node scripts/check-links.mjs  (npm run check:links)

import { readdirSync, statSync, readFileSync, existsSync } from "node:fs";
import { join, relative } from "node:path";

const DIST = "dist";
// Astro emits files at the dist root and prefixes hrefs with `base`; strip it
// back off before resolving against the on-disk tree.
const BASE = (process.env.BASE_PATH || "").replace(/\/+$/, "");

if (!existsSync(DIST)) {
  console.error(`check-links: no ${DIST}/ — run \`astro build\` first.`);
  process.exit(2);
}

/** Every .html file under dist/. */
function htmlFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    const s = statSync(p);
    if (s.isDirectory()) out.push(...htmlFiles(p));
    else if (entry.endsWith(".html")) out.push(p);
  }
  return out;
}

/** Does a root-relative site path resolve to a built file or directory index? */
function resolves(sitePath) {
  let p = sitePath;
  if (BASE && (p === BASE || p.startsWith(`${BASE}/`))) p = p.slice(BASE.length) || "/";
  const onDisk = join(DIST, decodeURIComponent(p));
  if (existsSync(onDisk)) {
    const s = statSync(onDisk);
    if (s.isFile()) return true;
    if (s.isDirectory() && existsSync(join(onDisk, "index.html"))) return true;
  }
  if (existsSync(`${onDisk}.html`)) return true; // /foo → foo.html
  return false;
}

const EXTERNAL = /^(https?:|mailto:|tel:|data:|javascript:|#)/i;
const broken = new Map(); // target → Set<source page>

for (const file of htmlFiles(DIST)) {
  const html = readFileSync(file, "utf8");
  const from = relative(DIST, file);
  for (const m of html.matchAll(/(?:href|src)="([^"]*)"/g)) {
    const raw = m[1].trim();
    if (!raw || EXTERNAL.test(raw) || raw.startsWith("//")) continue; // external / anchor-only
    if (!raw.startsWith("/")) continue; // document-relative — Astro emits root-relative; skip
    if (raw.startsWith("/api/")) continue; // runtime Pages Function route, not a static file
    const target = raw.split(/[?#]/)[0];
    if (!target || target === "/") continue;
    if (!resolves(target)) {
      if (!broken.has(target)) broken.set(target, new Set());
      broken.get(target).add(from);
    }
  }
}

if (broken.size === 0) {
  console.log(`check-links: OK — no broken internal links in ${DIST}/.`);
  process.exit(0);
}

console.error(`check-links: ${broken.size} broken internal target(s):`);
for (const [target, sources] of [...broken.entries()].sort()) {
  const list = [...sources].slice(0, 5);
  const more = sources.size > list.length ? ` (+${sources.size - list.length} more)` : "";
  console.error(`  ✗ ${target}\n      ← ${list.join("\n      ← ")}${more}`);
}
process.exit(1);
