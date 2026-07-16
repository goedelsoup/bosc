// Ambient shim for the one Astro coupling in @watermark/core: `stories.ts` lazily
// `await import("astro:content")` inside `loadStories()` — a build-time-only path (the
// Astro/MDX render context supplies the real virtual module; vitest and the Workers
// runtime never call it). Declaring the minimal surface here lets the package type-check
// standalone (DOM-free, no astro/client ambient types) without leaking a real astro
// dependency. Only visible to this package's own tsconfig — the site type-checks core
// files transitively against astro's real `astro:content` types, so there is no conflict.
declare module "astro:content" {
  export function getCollection(collection: string): Promise<Array<{ id: string; data: unknown }>>;
}
