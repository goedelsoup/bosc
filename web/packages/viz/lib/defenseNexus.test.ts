import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

// buildDefenseNexus reads geo/campus + geo/jsmc from the bundle; pin the sites
// (which carries both) so the test is deterministic regardless of a local export.
async function load(): Promise<typeof import("./defenseNexus")> {
  process.env.WATERMARK_BUNDLE_DIR = join(process.cwd(), "sites");
  vi.resetModules();
  return import("./defenseNexus");
}

describe("defenseNexus — map annotations (#267)", () => {
  beforeAll(() => {
    process.env.WATERMARK_BUNDLE_DIR = join(process.cwd(), "sites");
  });
  afterAll(() => {
    delete process.env.WATERMARK_BUNDLE_DIR;
  });

  it("produces one register-encoded annotation per fact tab", async () => {
    const { buildDefenseNexus } = await load();
    const dn = buildDefenseNexus();
    expect(dn.available).toBe(true);
    const byKey = Object.fromEntries(dn.annotations.map((a) => [a.key, a]));
    expect(byKey.geography.register).toBe("verified"); // the tank plant is on the ground
    expect(byKey.capability.register).toBe("inference"); // capability, not a Lima fact
    expect(byKey.silence.register).toBe("open"); // the absence
    expect(byKey.capability.label).toMatch(/not a Lima fact/i);
    expect(byKey.silence.label).toMatch(/No records/i);
  });

  it("places the 'No records' marker exactly at the measured-gap midpoint — where a line would go", async () => {
    const { buildDefenseNexus } = await load();
    const dn = buildDefenseNexus();
    const [a, b] = dn.metrics.nearestPair;
    const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    const silence = dn.annotations.find((x) => x.key === "silence");
    expect(silence?.position[0]).toBeCloseTo(mid[0]);
    expect(silence?.position[1]).toBeCloseTo(mid[1]);
  });

  it("never asserts a connection — the readout keeps it [open]", async () => {
    const { buildDefenseNexus } = await load();
    const dn = buildDefenseNexus();
    expect(dn.readout.open).toMatch(/connect|workload|authoriz/i);
  });
});
