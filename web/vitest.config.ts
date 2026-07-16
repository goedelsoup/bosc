/// <reference types="vitest/config" />
import { getViteConfig } from "astro/config";

// The Pages Functions (@watermark/functions) and the shared domain (@watermark/core) are now
// workspace packages resolved through node_modules — the old `@fn` path alias is retired (#1552).
export default getViteConfig({
  // The Stories store tests run against a real in-memory Postgres (pglite/WASM); its one-time boot
  // under parallel workers can exceed Vitest's 5s default, so lift the per-test ceiling.
  test: {
    testTimeout: 15000,
  },
});
