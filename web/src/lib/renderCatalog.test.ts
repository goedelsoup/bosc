import { describe, expect, it } from "vitest";
import { loadCatalog } from "./catalogBuild";
import { buildRenderCatalog } from "./renderCatalog";

// Runs against the committed sample bundle (WATERMARK_BUNDLE_DIR=sample-bundle) — the same fixture
// the rest of the web suite uses. Confirms the hydrated render-catalog asset is a superset of the
// thin resolver catalog and never drops or fabricates a handle.
describe("buildRenderCatalog", () => {
  it("hydrates every addressable handle from the thin catalog (one HydratedAtom per handle)", () => {
    const thin = loadCatalog();
    const rendered = buildRenderCatalog();
    const thinHandles = [...thin.byHandle.keys()].sort();
    const renderedHandles = Object.keys(rendered).sort();
    expect(renderedHandles).toEqual(thinHandles);
    for (const [handle, atom] of Object.entries(rendered)) {
      expect(atom.handle).toBe(handle);
      expect(atom.kind).toBeTruthy();
      expect(typeof atom.title).toBe("string");
    }
  });

  it("emits a non-empty catalog for the reference site", () => {
    expect(Object.keys(buildRenderCatalog()).length).toBeGreaterThan(0);
  });
});
