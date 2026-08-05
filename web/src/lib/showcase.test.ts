// The component galleries' dev-only gate (#1894, epic #1884 phase 10).
//
// Worth its own test for a reason that isn't the arithmetic. The gate first shipped as a `const` in
// the page's frontmatter that `getStaticPaths` closed over — and Astro HOISTS `getStaticPaths` out
// of the component, so the binding wasn't defined when it ran. A production build was green and
// emitted zero showcase routes, which is exactly what a working gate looks like; the dev server
// 500'd on all three, because the `DEV` branch is the only one that ever touches the registry.
//
// So the registry lives in a module the route imports (imports hoist, frontmatter consts don't),
// and the two branches are asserted here rather than inferred from a build that agrees with them
// for the wrong reason.
import { afterEach, describe, expect, it, vi } from "vitest";
import { GALLERIES, showcaseGalleryPaths } from "./showcase";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("showcaseGalleryPaths", () => {
  it("emits every gallery in dev", () => {
    vi.stubEnv("DEV", true);
    expect(showcaseGalleryPaths().map((p) => p.params.gallery)).toEqual(["charts", "icons", "teardown"]);
  });

  it("emits nothing in a production build — the galleries are not part of the deployed site", () => {
    vi.stubEnv("DEV", false);
    expect(showcaseGalleryPaths()).toEqual([]);
  });

  it("passes each gallery's own copy through as props, not just its slug", () => {
    // The route renders `kicker` / `h1` from these; a path with only a param would render a page
    // with an empty heading, which the build would emit happily.
    vi.stubEnv("DEV", true);
    for (const path of showcaseGalleryPaths()) {
      expect(path.props.gallery).toBe(path.params.gallery);
      expect(path.props.title.length).toBeGreaterThan(0);
      expect(path.props.kicker.length).toBeGreaterThan(0);
      expect(path.props.h1.length).toBeGreaterThan(0);
    }
  });

  it("keeps the slugs the trail declares — the URLs are unchanged from three separate pages", () => {
    // `trail.ts` labels these segments by value ("Chart set", "Icon set", "Record Teardown"), and a
    // dev bookmark predates this refactor. Renaming one here is a silent trail regression.
    expect(GALLERIES.map((g) => g.gallery).sort()).toEqual(["charts", "icons", "teardown"]);
  });
});
