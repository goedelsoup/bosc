/// <reference types="vitest/config" />
import { getViteConfig } from "astro/config";
import { fileURLToPath } from "node:url";

export default getViteConfig({
  resolve: {
    alias: {
      "@fn": fileURLToPath(new URL("./functions", import.meta.url)),
    },
  },
  // The Stories store tests run against a real in-memory Postgres (pglite/WASM); its one-time boot
  // under parallel workers can exceed Vitest's 5s default, so lift the per-test ceiling.
  test: {
    testTimeout: 15000,
  },
});
