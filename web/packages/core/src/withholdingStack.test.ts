import { describe, expect, it } from "vitest";
import { STACK_CLOSE, STACK_THESIS, WITHHOLDING_STACK } from "./withholdingStack";

describe("withholding stack (#224)", () => {
  it("has seven layers numbered 1-7 in lifecycle order", () => {
    expect(WITHHOLDING_STACK).toHaveLength(7);
    expect(WITHHOLDING_STACK.map((l) => l.n)).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it("every layer cites a statute, an instrument, a clause and a committed source", () => {
    for (const l of WITHHOLDING_STACK) {
      expect(l.statute.trim()).not.toBe("");
      expect(l.instrument.trim()).not.toBe("");
      expect(l.clause.trim()).not.toBe("");
      expect(l.effect.trim()).not.toBe("");
      // The source is a path into the committed corpus (a real extraction).
      expect(l.source).toMatch(/\.(yaml|md)$/);
    }
  });

  it("carries the front-end shield and the SWCD branch (the architecture's ends)", () => {
    expect(WITHHOLDING_STACK[0].statute).toContain("4582.58");
    expect(WITHHOLDING_STACK[6].statute).toContain("149.433");
  });

  it("keeps the “engineered system” framing explicit as argument", () => {
    expect(STACK_THESIS.toLowerCase()).toContain("argument");
    expect(STACK_THESIS).toContain("[verified]");
  });

  it("closes with the mandamus spine + Select-Committee links", () => {
    expect(STACK_CLOSE.links).toHaveLength(3);
    for (const link of STACK_CLOSE.links)
      expect(link.href).toContain("/network/american-sugar-creek-allen-co/site/legal/");
  });
});
