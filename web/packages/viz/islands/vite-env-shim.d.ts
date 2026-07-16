// Ambient shims for the Vite/Astro build-time surface the islands (and the @watermark/core
// modules they pull in) rely on, so @watermark/viz type-checks standalone without astro/client's
// ambient types. In the real site build Vite/Astro provide all of these. Only visible to this
// package's tsconfig.

// `import.meta.env` (Vite) — PUBLIC_* build vars read by islands and by core modules (base.ts …).
interface ImportMetaEnv {
  readonly [key: string]: string | undefined;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Vite asset-URL and CSS side-effect imports (e.g. pdfjs-dist worker `?url`, maplibre-gl CSS).
declare module "*?url" {
  const src: string;
  export default src;
}
declare module "*?raw" {
  const src: string;
  export default src;
}
declare module "*.css";
