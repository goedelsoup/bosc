/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";

// Shared-root Vitest with per-package projects (Epic #1549, Phase 5 · #1555).
//
// One config and one `pnpm test` run, but each workspace package owns its test scope via
// `include`, so the run no longer straddles the trees the way the old single flat config did:
//   • site      → web/src            (basin, the search engine)
//   • core      → @watermark/core    (the DOM-free domain logic)
//   • charts    → @watermark/charts  (the SVG geometry builders)
//   • viz       → @watermark/viz     (the island layer/data models)
//   • functions → @watermark/functions route/store tests under functions/_test/
//
// Every test is plain-Node (no `astro:content`, no DOM), so no astro `getViteConfig` /
// browser environment is needed; workspace packages resolve through node_modules, so the
// old `@fn` path alias is retired (#1552).
const testTimeout = 15000; // pglite/WASM boot (the functions store tests) can exceed the 5s default

export default defineConfig({
  test: {
    projects: [
      { test: { name: "site", include: ["src/**/*.test.ts"], testTimeout } },
      { test: { name: "core", include: ["packages/core/**/*.test.ts"], testTimeout } },
      { test: { name: "charts", include: ["packages/charts/**/*.test.ts"], testTimeout } },
      { test: { name: "viz", include: ["packages/viz/**/*.test.ts"], testTimeout } },
      { test: { name: "functions", include: ["functions/**/*.test.ts"], testTimeout } },
    ],
  },
});
