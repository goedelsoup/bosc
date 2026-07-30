import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { runWithSite } from "./bundle";
import {
  abatement,
  abatementPerJob,
  keptByPublic,
  netSubsidyModel,
  netSubsidyPerJobModel,
  priceCorner,
  salesTaxExemption,
} from "./econLedger";
import {
  craProfilesFromFeed,
  economicScenarios,
  ledgerConstants,
  netSubsidyOutcomeFromFeed,
  priorsFromFeed,
  promisedJobs,
  scenarioAxis,
  scenarioLine,
} from "./econScenarios";
import { buildAbatementPerJob } from "./moneyFlow";
import { disclose, outcomeBand, tornado } from "./uncertainty";

// The whole point of #1665 is that these figures come off the `economics-scenarios` feed rather
// than from literals in this package, so this suite is bundle-backed. Pin WATERMARK_BUNDLE_DIR at
// the committed `web/sites` fixtures (absolute, CWD-independent) when the mise task env hasn't,
// so a bare `vitest` can't silently read a stale local `data/site/bundles/`.
process.env.WATERMARK_BUNDLE_DIR ??= resolve(fileURLToPath(new URL(".", import.meta.url)), "../../../sites");

const LIMA = "lima";
const PEERS = ["fort-wayne", "urbana", "findlay"];

function lima<T>(fn: () => T): T {
  return runWithSite(LIMA, fn);
}

describe("econScenarios — the feed is the source, not a second declaration (#1665)", () => {
  it("reads the site's what-if corners and constants off the bundle", () => {
    lima(() => {
      const scenarios = economicScenarios();
      expect(scenarios).not.toBeNull();
      expect(scenarios?.site).toBe(LIMA);
      expect(craProfilesFromFeed()).toHaveLength(4);
      const k = ledgerConstants();
      expect(k).not.toBeNull();
      // Read from the committed CRA extraction, not typed here: 75% / 15 years on a ~$500M build.
      expect(k?.abatePct).toBe(0.75);
      expect(k?.termYears).toBe(15);
      expect(k?.capexUsd).toBe(500_000_000);
      // effectiveRate must be the published product, not a re-derivation that could drift.
      expect(k?.effectiveRate).toBeCloseTo((k?.assessmentRatio ?? 0) * (k?.effectiveMills ?? 0), 9);
    });
  });

  it("the TS formulas reproduce the feed's priced corners exactly (no fork)", () => {
    lima(() => {
      const k = ledgerConstants();
      const corners = craProfilesFromFeed();
      const published = economicScenarios()?.profiles ?? [];
      if (!k || !corners) throw new Error("the reference bundle must carry the scenario feed");
      // Python prices the published corners; TypeScript re-prices them for the island's live
      // knobs. This is the pin that keeps the interactive recompute on the published band.
      for (const p of published) {
        const corner = corners.find((c) => c.key === p.key);
        if (!corner) throw new Error(`corner ${p.key} missing`);
        const priced = priceCorner(k, corner);
        expect(Math.round(priced.abatementUsd)).toBe(p.abatement_usd);
        expect(Math.round(priced.keptUsd)).toBe(p.kept_usd);
        expect(Math.round(priced.exemptionUsd)).toBe(p.exemption_usd);
        expect(Math.round(priced.netSubsidyUsd)).toBe(p.net_subsidy_usd);
        expect(priced.abatementPerJobUsd).toBe(p.abatement_per_job_usd);
      }
    });
  });

  it("abatement-per-job matches buildAbatementPerJob for every corner", () => {
    lima(() => {
      const pj = buildAbatementPerJob();
      expect(pj).not.toBeNull();
      const deployed = new Map((pj?.profiles ?? []).map((p) => [p.key, p.perJobUsd]));
      for (const p of economicScenarios()?.profiles ?? []) {
        expect(deployed.get(p.key)).toBe(p.abatement_per_job_usd);
      }
    });
  });

  it("reproduces the essay's headline figures from the feed's constants", () => {
    lima(() => {
      const k = ledgerConstants();
      if (!k) throw new Error("no constants");
      expect(Math.round(abatement(k, 0.35) / 1e6)).toBe(43); // stated ~$43M
      expect(Math.round(abatement(k, 0.25) / 1e6)).toBe(31); // equipment ~$31M
      expect(Math.round(abatement(k, 0.5) / 1e6)).toBe(62); // govcloud ~$62M
      expect(Math.round(keptByPublic(k, 0.35) / 1e6)).toBe(14); // the 25% kept, ~$14.5M
      expect(abatementPerJob(k, 0.35, 50)).toBe(Math.round(abatement(k, 0.35) / 50));
    });
  });

  it("the sales-tax exemption inverts the building share (more equipment ⇒ more exemption)", () => {
    lima(() => {
      const k = ledgerConstants();
      if (!k) throw new Error("no constants");
      expect(salesTaxExemption(k, 0.25, 1.5)).toBeGreaterThan(salesTaxExemption(k, 0.5, 1.5));
      expect(salesTaxExemption(k, 0.35, 2.0)).toBeGreaterThan(salesTaxExemption(k, 0.35, 1.0));
    });
  });
});

describe("econScenarios — the published bands", () => {
  it("the abatement line bands ~$31M–$62M (the essay's range)", () => {
    lima(() => {
      const ab = scenarioLine("abatement");
      expect(Math.round((ab?.band.low ?? 0) / 1e6)).toBe(31);
      expect(Math.round((ab?.band.high ?? 0) / 1e6)).toBe(62);
    });
  });

  it("every published band is a real range at low confidence, and never [verified]", () => {
    lima(() => {
      const scenarios = economicScenarios();
      const rows = [
        ...(scenarios?.lines ?? []),
        ...(scenarios?.withheld ?? []),
        ...(scenarios?.load_per_job ? [scenarios.load_per_job] : []),
      ];
      expect(rows.length).toBeGreaterThan(0);
      for (const row of rows) {
        expect(row.band.high).toBeGreaterThan(row.band.low);
        expect(row.band.central).toBeGreaterThanOrEqual(row.band.low);
        expect(row.band.central).toBeLessThanOrEqual(row.band.high);
        expect(row.confidence).toBe("low");
        expect(row.tag).not.toBe("verified");
      }
      expect(scenarios?.tag).toBe("open");
      expect(scenarios?.disclaimer).toBeTruthy();
    });
  });

  it("the GovCloud corner is the band's top and says it is not a finding", () => {
    lima(() => {
      const profiles = economicScenarios()?.profiles ?? [];
      const govcloud = profiles.find((p) => p.key === "govcloud");
      expect(govcloud).toBeDefined();
      expect(govcloud?.net_subsidy_usd).toBe(Math.max(...profiles.map((p) => p.net_subsidy_usd)));
      expect(govcloud?.note).toContain("not a finding");
    });
  });

  it("the cited industry axes carry their sources and their application stays open", () => {
    lima(() => {
      // The "~20–30% above commercial" the docs carried as prose, now sourced.
      const premium = scenarioAxis("govcloud_premium");
      expect(premium?.band?.low).toBe(0.2);
      expect(premium?.band?.high).toBe(0.3);
      expect(premium?.tag).toBe("reference");
      expect(premium?.site_status).toBe("open");
      expect(premium?.sources?.length).toBeGreaterThan(0);
      // A corroboration axis asserts no magnitude — it must stay band-less.
      expect(scenarioAxis("ai_rack_refresh")?.band ?? null).toBeNull();
    });
  });

  it("load-per-job bands the §3 figure with the stated headcount as its central", () => {
    lima(() => {
      const line = economicScenarios()?.load_per_job;
      expect(line?.band.unit).toBe("MW_per_job");
      expect(line?.band.central).toBe(5.5); // ~275 MW over the agreement's own ~50 jobs
      expect(line?.band.high).toBeGreaterThan(line?.band.central ?? 0);
    });
  });
});

describe("econScenarios — the engine moves (#269)", () => {
  it("the net-subsidy band is wide and brackets its central", () => {
    lima(() => {
      const o = netSubsidyOutcomeFromFeed();
      expect(o).not.toBeNull();
      expect(o?.low).toBeLessThan(o?.central ?? 0);
      expect(o?.central).toBeLessThan(o?.high ?? 0);
      expect(o?.register).toBe("open");
    });
  });

  it("the priors come from the feed's withheld inputs, each naming its resolving record", () => {
    lima(() => {
      const priors = priorsFromFeed();
      expect(priors?.map((p) => p.key)).toEqual([
        "building_share",
        "jobs",
        "equipment_refresh",
        "school_compensation",
      ]);
      for (const prior of priors ?? []) {
        expect(prior.resolvingRecord).toBeTruthy();
        expect(prior.source).toBeTruthy();
      }
      // The genuinely undisclosed one is a wide uniform screening range, not an estimate.
      const school = priors?.find((p) => p.key === "school_compensation");
      expect(school?.register).toBe("open");
      expect(school?.dist.kind).toBe("uniform");
    });
  });

  it("disclosing the school compensation tightens the band (cost-of-opacity)", () => {
    lima(() => {
      const k = ledgerConstants();
      const priors = priorsFromFeed();
      if (!k || !priors) throw new Error("no feed");
      const model = netSubsidyModel(k, true);
      const wide = outcomeBand(priors, model);
      const tight = outcomeBand(disclose(priors, "school_compensation", 0), model);
      expect(tight.high - tight.low).toBeLessThan(wide.high - wide.low);
    });
  });

  it("turning the DCTE off lowers the net subsidy", () => {
    lima(() => {
      const k = ledgerConstants();
      const priors = priorsFromFeed();
      if (!k || !priors) throw new Error("no feed");
      const central = Object.fromEntries(
        priors.map((p) => [
          p.key,
          p.dist.kind === "fixed"
            ? p.dist.value
            : p.dist.kind === "uniform"
              ? (p.dist.low + p.dist.high) / 2
              : p.dist.central,
        ]),
      );
      expect(netSubsidyModel(k, false)(central)).toBeLessThan(netSubsidyModel(k, true)(central));
    });
  });

  it("the tornado ranks the four withheld knobs by leverage (per-job: all four move it)", () => {
    lima(() => {
      const k = ledgerConstants();
      const priors = priorsFromFeed();
      if (!k || !priors) throw new Error("no feed");
      const bars = tornado(priors, netSubsidyPerJobModel(k, true));
      expect(bars.length).toBe(4);
      expect(bars.every((b) => b.swing > 0)).toBe(true);
      expect(bars[0].swing).toBeGreaterThanOrEqual(bars[bars.length - 1].swing);
    });
  });
});

// E4 (#1642), sharpened by #1665. Every constant behind this ledger is ONE county's abatement
// agreement — its abated percentage and term, its local effective mills, its county sales-and-use
// rate, its non-binding job estimate. The report page renders on `selectableSitePaths`, so the
// moment a second site was promoted a slug-gated model would have priced its build off that
// instrument under its own name. The gate is now the instrument itself: a peer's bundle carries no
// `economics-scenarios` feed, so there is nothing to inherit.
describe("econScenarios — the instrument answers only for its own site (#1642 E4 / #1665)", () => {
  it("the reference site resolves the full priced ledger", () => {
    lima(() => {
      expect(economicScenarios()?.profiles).toHaveLength(4);
      expect(economicScenarios()?.lines).toHaveLength(5);
      expect(netSubsidyOutcomeFromFeed()).not.toBeNull();
      expect(promisedJobs()).toBe(50);
      expect(buildAbatementPerJob()).not.toBeNull();
    });
  });

  it("another selectable site resolves nothing — it does not inherit those terms", () => {
    for (const peer of PEERS) {
      runWithSite(peer, () => {
        expect(economicScenarios()).toBeNull();
        expect(craProfilesFromFeed()).toBeNull();
        expect(ledgerConstants()).toBeNull();
        expect(priorsFromFeed()).toBeNull();
        expect(netSubsidyOutcomeFromFeed()).toBeNull();
        expect(promisedJobs()).toBeNull();
        expect(buildAbatementPerJob()).toBeNull();
      });
    }
  });
});
