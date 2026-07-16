// Ambient shim for `import.meta.env` (a Vite/Astro build-time global) used by a handful of
// core modules to read PUBLIC_* build vars (base.ts, routes.ts, donate.ts, contactsFlag.ts,
// storiesFlag.ts). Vite injects the real values at build time; standalone `tsc` has no Vite
// ambient, so declare the surface. Merges with @types/node's `ImportMeta` (which supplies
// `import.meta.url`). Only visible to this package's tsconfig; the site type-checks these
// files against Astro's real `ImportMetaEnv` (src/env.d.ts), so there is no conflict.
interface ImportMetaEnv {
  readonly [key: string]: string | undefined;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
  // `import.meta.glob` (Vite build-time glob import) — used by stories.ts to read every chapter's
  // MDX frontmatter as `?raw` text at build. Vite provides the real, richly-typed overloads; this
  // is the minimal surface the callers use (both cast the result).
  glob(
    pattern: string | string[],
    options?: { eager?: boolean; query?: string; import?: string },
  ): Record<string, unknown>;
}
