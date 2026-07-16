import { describe, expect, it } from "vitest";
import {
  COUNTY_JOBS_2023,
  ECON_PRIORS,
  abatement,
  abatementPerJob,
  keptByPublic,
  ledgerLines,
  ledgerProfiles,
  netSubsidyModel,
  netSubsidyOutcome,
  netSubsidyPerJobModel,
  salesTaxExemption,
} from "./econLedger";
import { buildAbatementPerJob } from "./moneyFlow";
import { disclose, outcomeBand, tornado } from "./uncertainty";

describe("econLedger — no fork from the deployed model (#269)", () => {
  it("abatement-per-job matches buildAbatementPerJob for every profile", () => {
    const deployed = new Map(buildAbatementPerJob().profiles.map((p) => [p.key, p.perJobUsd]));
    for (const p of ledgerProfiles()) {
      expect(p.abatementPerJobUsd).toBe(deployed.get(p.key));
    }
  });

  it("reproduces the essay's headline figures", () => {
    expect(Math.round(abatement(0.35) / 1e6)).toBe(43); // stated ~$43M
    expect(Math.round(abatement(0.25) / 1e6)).toBe(31); // equipment ~$31M
    expect(Math.round(abatement(0.5) / 1e6)).toBe(62); // govcloud ~$62M
    expect(Math.round(keptByPublic(0.35) / 1e6)).toBe(14); // 25% kept ~$14.5M
    expect(COUNTY_JOBS_2023).toBe(49_577);
  });

  it("abatement-per-job round-trips the formula", () => {
    expect(abatementPerJob(0.35, 50)).toBe(Math.round(abatement(0.35) / 50));
    expect(abatementPerJob(0.5, 30)).toBe(Math.round(abatement(0.5) / 30));
  });
});

describe("econLedger — the ledger bands", () => {
  it("the abatement line bands ~$31M–$62M (the essay's range)", () => {
    const ab = ledgerLines().find((l) => l.key === "abatement");
    expect(Math.round((ab?.band.low ?? 0) / 1e6)).toBe(31);
    expect(Math.round((ab?.band.high ?? 0) / 1e6)).toBe(62);
  });

  it("the sales-tax exemption inverts the building share (more equipment ⇒ more exemption)", () => {
    expect(salesTaxExemption(0.25, 1.5)).toBeGreaterThan(salesTaxExemption(0.5, 1.5));
    expect(salesTaxExemption(0.35, 2.0)).toBeGreaterThan(salesTaxExemption(0.35, 1.0));
  });
});

describe("econLedger — the engine moves (#269)", () => {
  it("the net-subsidy band is wide and brackets its central", () => {
    const o = netSubsidyOutcome();
    expect(o.low).toBeLessThan(o.central);
    expect(o.central).toBeLessThan(o.high);
    expect(o.register).toBe("open");
  });

  it("disclosing the school compensation tightens the band (cost-of-opacity)", () => {
    const model = netSubsidyModel(true);
    const wide = outcomeBand(ECON_PRIORS, model);
    const disclosed = disclose(ECON_PRIORS, "school_comp", 0);
    const tight = outcomeBand(disclosed, model);
    expect(tight.high - tight.low).toBeLessThan(wide.high - wide.low);
  });

  it("turning the DCTE off lowers the net subsidy", () => {
    const central = Object.fromEntries(
      ECON_PRIORS.map((p) => [
        p.key,
        p.dist.kind === "fixed"
          ? p.dist.value
          : p.dist.kind === "uniform"
            ? (p.dist.low + p.dist.high) / 2
            : p.dist.central,
      ]),
    );
    expect(netSubsidyModel(false)(central)).toBeLessThan(netSubsidyModel(true)(central));
  });

  it("the tornado ranks the four withheld knobs by leverage (per-job: all four move it)", () => {
    const bars = tornado(ECON_PRIORS, netSubsidyPerJobModel(true));
    expect(bars.length).toBe(4); // building_share, jobs, refresh, school_comp
    expect(bars.every((b) => b.swing > 0)).toBe(true); // each knob has real leverage on per-job
    expect(bars[0].swing).toBeGreaterThanOrEqual(bars[bars.length - 1].swing);
  });
});
