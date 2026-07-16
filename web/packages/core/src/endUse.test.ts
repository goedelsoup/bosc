import { describe, expect, it } from "vitest";
import { IL_LADDER, buildEndUse } from "./endUse";

describe("endUse — the access ladder + benefit-capture (#266)", () => {
  const data = buildEndUse();
  const byKey = Object.fromEntries(data.types.map((t) => [t.key, t]));

  it("the IL ladder runs broad commercial → sealed IL-6 enclave", () => {
    expect(IL_LADDER.map((r) => r.key)).toEqual(["commercial", "fedramp", "il4", "il5", "il6"]);
  });

  it("each model's ladder reach narrows as access seals", () => {
    expect(byKey.bitcoin.ladderReach).toBeNull(); // self only — off the ladder
    expect(byKey.hyperscale.ladderReach?.[0]).toBe(0); // broad commercial up
    expect(byKey.enclave.ladderReach).toEqual([2, 4]); // IL4 → IL6, the sealed top
    // colocation's tenants are unnamed — the reach spans the whole ladder ([open]).
    expect(byKey.colocation.ladderReach).toEqual([0, 4]);
  });

  it("benefit-capture is register-encoded: hyperscale owns it, colocation can't say, enclave sealed", () => {
    expect(byKey.hyperscale.benefitCapture.register).toBe("inference");
    expect(byKey.colocation.benefitCapture.register).toBe("open");
    expect(byKey.enclave.benefitCapture.register).toBe("open");
    expect(byKey.bitcoin.benefitCapture.register).toBe("verified");
  });

  it("carries the two pointed silences as [open], not findings", () => {
    expect(data.silences).toHaveLength(2);
    expect(data.silences.every((s) => s.register === "open")).toBe(true);
    expect(data.silences.map((s) => s.label).join(" ")).toMatch(/Google.*Lima|no records|PRR/i);
  });

  it("keeps which-model-is-Lima open (only bitcoin ruled out)", () => {
    const ruledOut = data.types.filter((t) => t.limaStatus === "ruled-out");
    expect(ruledOut.map((t) => t.key)).toEqual(["bitcoin"]);
  });
});
