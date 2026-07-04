import { describe, expect, it } from "vitest";
import { hasInteractive, INTERACTIVE_REPORTS, reportUrl } from "./reports";

describe("reports registry (#584)", () => {
  it("reportUrl builds the companion path for the given site (not Lima-pinned)", () => {
    expect(reportUrl("the-economic-ledger", "lima")).toBe(
      "/network/american-sugar-creek-allen-co/reports/the-economic-ledger",
    );
    expect(reportUrl("the-economic-ledger", "fort-wayne")).toBe(
      "/network/fort-wayne/reports/the-economic-ledger",
    );
  });

  it("hasInteractive is true only for registered slugs", () => {
    for (const r of INTERACTIVE_REPORTS) expect(hasInteractive(r.slug)).toBe(true);
    expect(hasInteractive("bigger-picture")).toBe(false);
    expect(hasInteractive("dossier")).toBe(false);
  });

  it("covers the slugs the balance sheet and index depend on", () => {
    const slugs = new Set(INTERACTIVE_REPORTS.map((r) => r.slug));
    for (const s of ["the-economic-ledger", "the-load-and-the-grid", "toxics-and-the-corridor"]) {
      expect(slugs.has(s)).toBe(true);
    }
  });
});
